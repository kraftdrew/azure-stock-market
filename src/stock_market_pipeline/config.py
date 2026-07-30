from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

SYMBOLS = ("VOO", "TSLA", "TM", "F", "AAPL", "MSFT", "NVDA", "JPM", "GS", "MS")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    data_bucket: str
    api_key: str
    aws_region: str = "us-east-1"
    job_mode: str = "daily"
    backfill_start_date: date = date(2021, 1, 1)
    overlap_days: int = 10

    @classmethod
    def from_env(cls) -> Settings:
        job_mode = os.getenv("JOB_MODE", "daily").lower()
        if job_mode not in {"daily", "backfill"}:
            raise ValueError("JOB_MODE must be 'daily' or 'backfill'")
        return cls(
            data_bucket=require_env("DATA_BUCKET"),
            api_key=require_env("TWELVE_DATA_API_KEY"),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            job_mode=job_mode,
            backfill_start_date=date.fromisoformat(
                os.getenv("BACKFILL_START_DATE", "2021-01-01")
            ),
            overlap_days=int(os.getenv("OVERLAP_DAYS", "10")),
        )

    def extraction_window(self, today: date | None = None) -> tuple[date, date]:
        current = today or datetime.now(UTC).date()
        if self.job_mode == "backfill":
            return self.backfill_start_date, current + timedelta(days=1)
        return current - timedelta(days=self.overlap_days), current + timedelta(days=1)
