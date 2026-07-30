import pytest

from stock_market_pipeline.api import _records, build_query


def test_prices_query_uses_validated_filters() -> None:
    query = build_query(
        "/v1/prices",
        {"symbol": "aapl", "start": "2026-01-01", "end": "2026-07-29"},
    )
    assert "symbol = 'AAPL'" in query
    assert "price_date >= date '2026-01-01'" in query
    assert "price_date <= date '2026-07-29'" in query


def test_prices_query_rejects_unknown_symbol() -> None:
    with pytest.raises(ValueError, match="unknown symbol"):
        build_query("/v1/prices", {"symbol": "BAD'; drop table prices; --"})


def test_prices_query_rejects_invalid_date() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_query("/v1/prices", {"start": "yesterday"})


def test_athena_rows_are_converted_to_rest_types() -> None:
    rows = [["120260728", "1", "12345", "12.5"]]
    records = _records(
        rows,
        ("TransactionSID", "SymbolSID", "Volume", "Close"),
    )
    assert records == [
        {
            "TransactionSID": 120260728,
            "SymbolSID": 1,
            "Volume": 12345,
            "Close": 12.5,
        }
    ]


def test_dim_date_preserves_legacy_iso_date_contract() -> None:
    records = _records(
        [["20210102", "2021-01-02 00:00:00.000000", "2"]],
        ("DateID", "Date", "Day"),
    )
    assert records == [{"DateID": 20210102, "Date": "2021-01-02", "Day": 2}]
