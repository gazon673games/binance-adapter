from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from binance_adapter.exceptions import (
    BinanceAdapterError as DatasetValidationError,
)


def timestamp_value(raw: int) -> datetime:
    divisor = 1_000_000.0 if raw >= 10**15 else 1_000.0
    return datetime.fromtimestamp(raw / divisor, tz=UTC)


def as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    if hasattr(value, 'to_pydatetime'):
        return value.to_pydatetime()
    raise DatasetValidationError(
        f'Quote timestamp must be datetime, got {value!r}'
    )
