from datetime import date

from stock_market_pipeline.config import Settings


def test_daily_window_uses_overlap() -> None:
    settings = Settings(data_bucket="bucket", api_key="key", overlap_days=10)
    assert settings.extraction_window(date(2026, 7, 29)) == (
        date(2026, 7, 19),
        date(2026, 7, 30),
    )


def test_backfill_window_starts_at_configured_date() -> None:
    settings = Settings(
        data_bucket="bucket",
        api_key="key",
        job_mode="backfill",
        backfill_start_date=date(2021, 1, 1),
    )
    assert settings.extraction_window(date(2026, 7, 29)) == (
        date(2021, 1, 1),
        date(2026, 7, 30),
    )
