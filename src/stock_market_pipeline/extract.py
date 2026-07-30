from __future__ import annotations

import io
import json
import os
import random
import time
import uuid
from datetime import UTC, date, datetime
from typing import Any

import boto3
import polars as pl
import requests

from stock_market_pipeline.config import SYMBOLS, Settings

TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"
MAX_ATTEMPTS = 5


class TwelveDataError(RuntimeError):
    pass


def fetch_symbol(
    session: requests.Session,
    api_key: str,
    symbol: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    params = {
        "symbol": symbol,
        "interval": "1day",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "outputsize": 5000,
        "order": "ASC",
        "apikey": api_key,
    }
    last_error = "unknown error"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = session.get(TWELVE_DATA_URL, params=params, timeout=(10, 60))
            payload = response.json()
            if response.ok and payload.get("status") == "ok" and "meta" in payload:
                return payload
            last_error = str(payload.get("message") or f"HTTP {response.status_code}")
            retryable = (
                response.status_code in {429, 500, 502, 503, 504}
                or payload.get("code") in {429, 500}
            )
            if not retryable:
                break
        except (requests.RequestException, ValueError) as exc:
            last_error = str(exc)
        if attempt < MAX_ATTEMPTS:
            minute_limit = "current minute" in last_error.lower()
            delay = 65.0 if minute_limit else min(
                60, (2 ** (attempt - 1)) + random.random()
            )
            print(f"{symbol}: attempt {attempt} failed; retrying in {delay:.1f}s")
            time.sleep(delay)
    raise TwelveDataError(f"{symbol}: Twelve Data request failed: {last_error}")


def normalize_payload(payload: dict[str, Any], extracted_at: datetime) -> pl.DataFrame:
    meta = payload["meta"]
    values = payload.get("values") or []
    rows = [
        {
            "symbol": str(meta["symbol"]),
            "exchange_name": meta.get("exchange"),
            "currency": meta.get("currency"),
            "instrument_type": meta.get("type"),
            "exchange_timezone": meta.get("exchange_timezone"),
            "volume": value.get("volume"),
            "high": value.get("high"),
            "low": value.get("low"),
            "close": value.get("close"),
            "open": value.get("open"),
            "price_date": value.get("datetime"),
            "extracted_at": extracted_at,
        }
        for value in values
    ]
    if not rows:
        symbol = meta.get("symbol", "unknown")
        raise TwelveDataError(f"{symbol}: response contained no rows")
    return pl.from_dicts(rows).with_columns(
        pl.col("price_date").str.to_date("%Y-%m-%d", strict=True),
        pl.col("volume").cast(pl.Int64, strict=False),
        *[
            pl.col(column).cast(pl.Decimal(precision=18, scale=3), strict=False)
            for column in ("high", "low", "close", "open")
        ],
        pl.col("extracted_at").cast(pl.Datetime("us", time_zone="UTC")),
    )


def extract_to_s3(
    settings: Settings,
    *,
    s3_client: Any | None = None,
    session: requests.Session | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    s3 = s3_client or boto3.client("s3", region_name=settings.aws_region)
    http = session or requests.Session()
    extracted_at = now or datetime.now(UTC)
    start_date, end_date = settings.extraction_window(extracted_at.date())
    run_id = f"{extracted_at:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    load_date = extracted_at.date().isoformat()
    counts: dict[str, int] = {}
    frames: list[pl.DataFrame] = []

    for symbol in SYMBOLS:
        payload = fetch_symbol(
            http, settings.api_key, symbol, start_date=start_date, end_date=end_date
        )
        raw_key = f"raw/twelvedata/load_date={load_date}/{run_id}/{symbol}.json"
        s3.put_object(
            Bucket=settings.data_bucket,
            Key=raw_key,
            Body=json.dumps(payload, separators=(",", ":")).encode(),
            ContentType="application/json",
        )

        frame = normalize_payload(payload, extracted_at)
        frames.append(frame)
        counts[symbol] = len(frame)

    combined = (
        pl.concat(frames)
        .sort(["symbol", "price_date", "extracted_at"])
        .unique(subset=["symbol", "price_date"], keep="last", maintain_order=True)
    )
    buffer = io.BytesIO()
    combined.write_parquet(buffer, compression="zstd")
    transformed_key = (
        f"transformed/prices/load_date={load_date}/part-{run_id}.parquet"
    )
    s3.put_object(
        Bucket=settings.data_bucket,
        Key=transformed_key,
        Body=buffer.getvalue(),
        ContentType="application/vnd.apache.parquet",
    )
    print(
        f"Wrote {len(combined)} transformed rows to "
        f"s3://{settings.data_bucket}/{transformed_key}"
    )
    return counts


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if not os.getenv("TWELVE_DATA_API_KEY"):
        secret_arn = os.environ["APP_SECRET_ARN"]
        secret = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
        value = json.loads(secret["SecretString"])
        os.environ["TWELVE_DATA_API_KEY"] = value["twelve_data_api_key"]

    mode = str(event.get("mode", "daily")).lower()
    os.environ["JOB_MODE"] = mode
    counts = extract_to_s3(Settings.from_env())
    return {
        "status": "ok",
        "mode": mode,
        "symbols": len(counts),
        "rows": sum(counts.values()),
    }


def main() -> None:
    counts = extract_to_s3(Settings.from_env())
    row_count = sum(counts.values())
    print(f"Extraction complete: {row_count} rows across {len(counts)} symbols")


if __name__ == "__main__":
    main()
