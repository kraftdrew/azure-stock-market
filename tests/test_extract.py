from datetime import UTC, date, datetime

import polars as pl
import pytest

from stock_market_pipeline import extract
from stock_market_pipeline.config import Settings
from stock_market_pipeline.extract import TwelveDataError, normalize_payload


def payload() -> dict:
    return {
        "status": "ok",
        "meta": {
            "symbol": "AAPL",
            "exchange": "NASDAQ",
            "currency": "USD",
            "type": "Common Stock",
            "exchange_timezone": "America/New_York",
        },
        "values": [
            {
                "datetime": "2026-07-28",
                "open": "210.100",
                "high": "212.500",
                "low": "209.750",
                "close": "211.300",
                "volume": "1234567",
            }
        ],
    }


def test_normalize_payload_uses_typed_polars_frame() -> None:
    frame = normalize_payload(payload(), datetime(2026, 7, 29, tzinfo=UTC))
    assert isinstance(frame, pl.DataFrame)
    assert frame.height == 1
    assert frame["symbol"][0] == "AAPL"
    assert frame["price_date"][0] == date(2026, 7, 28)
    assert frame["volume"].dtype == pl.Int64
    assert frame["close"].dtype == pl.Decimal(precision=18, scale=3)


def test_normalize_rejects_empty_values() -> None:
    value = payload()
    value["values"] = []
    with pytest.raises(TwelveDataError, match="no rows"):
        normalize_payload(value, datetime(2026, 7, 29, tzinfo=UTC))


def test_extraction_writes_only_raw_and_transformed_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    objects: list[dict] = []

    class S3:
        def put_object(self, **kwargs: object) -> None:
            objects.append(kwargs)

    def fake_fetch(
        _session: object,
        _api_key: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> dict:
        assert start_date < end_date
        value = payload()
        value["meta"]["symbol"] = symbol
        return value

    monkeypatch.setattr(extract, "fetch_symbol", fake_fetch)
    counts = extract.extract_to_s3(
        Settings(data_bucket="bucket", api_key="key"),
        s3_client=S3(),
        session=object(),
        now=datetime(2026, 7, 29, 12, tzinfo=UTC),
    )

    keys = [str(item["Key"]) for item in objects]
    assert len(counts) == 10
    assert len([key for key in keys if key.startswith("raw/")]) == 10
    transformed = [key for key in keys if key.startswith("transformed/")]
    assert len(transformed) == 1
    assert transformed[0].startswith(
        "transformed/prices/load_date=2026-07-29/part-20260729T120000Z-"
    )
    assert transformed[0].endswith(".parquet")
