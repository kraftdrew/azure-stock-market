from __future__ import annotations

import base64
import hmac
import json
import os
from datetime import date
from typing import Any

import boto3

from stock_market_pipeline.athena import run_query

SYMBOL_LOOKUP = (
    (1, 0, "No Industry", "VOO", "https://upload.wikimedia.org/wikipedia/commons/8/81/Vanguard.svg"),
    (2, 1, "Tech", "AAPL", "https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg"),
    (3, 2, "Tech", "MSFT", "https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg"),
    (4, 3, "Tech", "NVDA", "https://upload.wikimedia.org/wikipedia/commons/2/21/Nvidia_logo.svg"),
    (5, 4, "Automotive", "TSLA", "https://upload.wikimedia.org/wikipedia/commons/b/bd/Tesla_Motors.svg"),
    (6, 5, "Automotive", "TM", "https://upload.wikimedia.org/wikipedia/commons/7/78/Toyota_Logo.svg"),
    (7, 6, "Automotive", "F", "https://upload.wikimedia.org/wikipedia/commons/3/3e/Ford_logo_flat.svg"),
    (8, 7, "Finance", "JPM", "https://upload.wikimedia.org/wikipedia/commons/0/07/J_P_Morgan_Chase_Logo_2008_1.svg"),
    (9, 8, "Finance", "GS", "https://upload.wikimedia.org/wikipedia/commons/6/61/Goldman_Sachs.svg"),
    (10, 9, "Finance", "MS", "https://upload.wikimedia.org/wikipedia/commons/3/34/Morgan_Stanley_Logo_1.svg"),
)

COLUMNS = {
    "/v1/prices": (
        "Symbol",
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ),
    "/v1/dim-symbol": (
        "SymbolSID",
        "Symbol",
        "ExchangeName",
        "Currency",
        "Type",
        "ExchangeTimeZone",
        "Sort",
        "Industry",
        "Logo",
    ),
    "/v1/dim-date": (
        "DateID",
        "Date",
        "Day",
        "DayOfWeek",
        "DayOfWeekNumber",
        "MonthName",
        "MonthNumber",
        "Year",
        "YearMonth",
    ),
    "/v1/fact-daily": (
        "TransactionSID",
        "SymbolSID",
        "Volume",
        "High",
        "Low",
        "Close",
        "Open",
        "DateID",
    ),
}

INTEGER_COLUMNS = {
    "SymbolSID",
    "Sort",
    "DateID",
    "Day",
    "DayOfWeekNumber",
    "MonthNumber",
    "Year",
    "YearMonth",
    "TransactionSID",
    "Volume",
}
NUMBER_COLUMNS = {"Open", "High", "Low", "Close"}
DATE_COLUMNS = {"Date"}


def _lookup_values() -> str:
    rows = []
    for sid, sort, industry, symbol, logo in SYMBOL_LOOKUP:
        escaped_logo = logo.replace("'", "''")
        rows.append(f"({sid},{sort},'{industry}','{symbol}','{escaped_logo}')")
    return ",".join(rows)


LATEST_CTE = """
with latest as (
    select *
    from (
        select p.*,
               row_number() over (
                   partition by symbol, price_date
                   order by extracted_at desc
               ) as row_num
        from prices p
    )
    where row_num = 1
)
"""


def _sql_literal(value: str, name: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must use YYYY-MM-DD") from exc
    return parsed.isoformat()


def build_query(path: str, parameters: dict[str, str]) -> str:
    lookup = _lookup_values()
    if path == "/v1/prices":
        predicates = []
        symbol = parameters.get("symbol")
        if symbol:
            allowed = {item[3] for item in SYMBOL_LOOKUP}
            symbol = symbol.upper()
            if symbol not in allowed:
                raise ValueError("unknown symbol")
            predicates.append(f"symbol = '{symbol}'")
        if start := parameters.get("start"):
            predicates.append(f"price_date >= date '{_sql_literal(start, 'start')}'")
        if end := parameters.get("end"):
            predicates.append(f"price_date <= date '{_sql_literal(end, 'end')}'")
        where = f"where {' and '.join(predicates)}" if predicates else ""
        return (
            LATEST_CTE
            + f"""
select symbol, cast(price_date as varchar), cast(open as double),
       cast(high as double), cast(low as double), cast(close as double), volume
from latest
{where}
order by symbol, price_date
"""
        )
    if path == "/v1/dim-symbol":
        return (
            LATEST_CTE
            + f""",
lookup(symbol_sid, sort, industry, symbol, logo) as (
    values {lookup}
),
metadata as (
    select symbol,
           max_by(exchange_name, extracted_at) exchange_name,
           max_by(currency, extracted_at) currency,
           max_by(instrument_type, extracted_at) instrument_type,
           max_by(exchange_timezone, extracted_at) exchange_timezone
    from latest group by symbol
)
select l.symbol_sid, l.symbol, m.exchange_name, m.currency, m.instrument_type,
       m.exchange_timezone, l.sort, l.industry, l.logo
from lookup l join metadata m on l.symbol = m.symbol
order by l.sort
"""
        )
    if path == "/v1/dim-date":
        return """
with dates as (
    select calendar_date
    from unnest(
        sequence(date '2021-01-01', date_add('year', 1, current_date), interval '1' day)
    ) generated(calendar_date)
)
select cast(date_format(calendar_date, '%Y%m%d') as bigint),
       cast(calendar_date as varchar), day(calendar_date),
       date_format(calendar_date, '%W'), mod(day_of_week(calendar_date), 7) + 1,
       date_format(calendar_date, '%b'), month(calendar_date), year(calendar_date),
       cast(date_format(calendar_date, '%Y%m') as bigint)
from dates order by calendar_date
"""
    if path == "/v1/fact-daily":
        return (
            LATEST_CTE
            + f""",
lookup(symbol_sid, sort, industry, symbol, logo) as (
    values {lookup}
)
select cast(l.symbol_sid * 100000000
            + cast(date_format(p.price_date, '%Y%m%d') as bigint) as bigint),
       l.symbol_sid, p.volume, cast(p.high as double), cast(p.low as double),
       cast(p.close as double), cast(p.open as double),
       cast(date_format(p.price_date, '%Y%m%d') as bigint)
from latest p join lookup l on p.symbol = l.symbol
order by p.price_date, l.symbol_sid
"""
        )
    raise KeyError(path)


def _response(status: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": (
            body
            if isinstance(body, str)
            else json.dumps(body, separators=(",", ":"))
        ),
    }


def _authorized(headers: dict[str, str] | None, secret: dict[str, str]) -> bool:
    normalized = {key.lower(): value for key, value in (headers or {}).items()}
    value = normalized.get("authorization", "")
    if not value.startswith("Basic "):
        return False
    try:
        username, password = (
            base64.b64decode(value[6:], validate=True).decode().split(":", 1)
        )
    except Exception:
        return False
    return hmac.compare_digest(
        username, secret["powerbi_username"]
    ) and hmac.compare_digest(
        password,
        secret["powerbi_password"],
    )


def _records(
    rows: list[list[str | None]], columns: tuple[str, ...]
) -> list[dict[str, Any]]:
    records = []
    for row in rows:
        record: dict[str, Any] = {}
        for index, column in enumerate(columns):
            value = row[index] if index < len(row) else None
            if value is not None and column in INTEGER_COLUMNS:
                value = int(value)
            elif value is not None and column in NUMBER_COLUMNS:
                value = float(value)
            elif value is not None and column in DATE_COLUMNS:
                value = value[:10]
            record[column] = value
        records.append(record)
    return records


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    secrets = boto3.client("secretsmanager")
    secret = json.loads(
        secrets.get_secret_value(SecretId=os.environ["APP_SECRET_ARN"])["SecretString"]
    )
    if not _authorized(event.get("headers"), secret):
        response = _response(401, {"error": "unauthorized"})
        response["headers"]["www-authenticate"] = 'Basic realm="stock-market"'
        return response

    path = event.get("rawPath", "")
    if path == "/v1/health":
        return _response(200, {"status": "ok"})
    if path not in COLUMNS:
        return _response(404, {"error": "not_found"})
    try:
        query = build_query(path, event.get("queryStringParameters") or {})
        rows = run_query(
            boto3.client("athena"),
            query,
            database=os.environ["ATHENA_DATABASE"],
            workgroup=os.environ["ATHENA_WORKGROUP"],
            timeout_seconds=22,
        )
        return _response(200, _records(rows, COLUMNS[path]))
    except ValueError as exc:
        return _response(400, {"error": str(exc)})
    except Exception as exc:
        print(type(exc).__name__, str(exc))
        return _response(500, {"error": "query_failed"})
