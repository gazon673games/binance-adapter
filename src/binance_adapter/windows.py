"""
Build large histories one calendar month at a time into a single Parquet
file.
"""

from __future__ import annotations

from datetime import UTC, datetime


def month_windows(start_ms: int, end_ms: int):
    cursor = start_ms
    while cursor <= end_ms:
        stamp = datetime.fromtimestamp(cursor / 1000, UTC)
        next_month = datetime(
            stamp.year + (stamp.month == 12),
            stamp.month % 12 + 1,
            1,
            tzinfo=UTC,
        )
        boundary = int(next_month.timestamp() * 1000)
        yield (
            stamp.strftime('%Y-%m'),
            cursor,
            min(end_ms, boundary - 1),
            boundary,
        )
        cursor = boundary
