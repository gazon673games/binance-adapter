"""
Explicit funding valuation estimates from preserved opening mark observations.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from binance_adapter.download import download_mark_klines
from binance_adapter.exceptions import (
    BinanceAdapterError as DatasetValidationError,
)
from binance_adapter.funding import ordered_funding_events
from binance_adapter.transport import BinanceTransport


def recover_funding_prices(
    transport: BinanceTransport,
    *,
    symbol: str,
    events: list[dict[str, Any]],
    marks: list[list[Any]],
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep API prices; estimate missing nonzero events at their minute's open.

    A kline's opening price is an estimate of the funding settlement price, even
    when the funding timestamp equals its open. Never claim historical approval
    or use the minute's close, which incorporates observations after the event.
    """
    events = ordered_funding_events(events, symbol)
    wanted = {}
    for event in events:
        if (
            event.get('markPrice') in (None, '')
            and Decimal(str(event['fundingRate'])) != 0
        ):
            timestamp = int(event['fundingTime'])
            wanted[timestamp] = timestamp // 60_000 * 60_000
    if not wanted:
        return events
    openings = _funding_openings(transport, symbol, set(wanted.values()), marks)
    recovered, estimates, unresolved = _recover_events(
        events, wanted, openings, symbol
    )
    sources.append(
        {
            'resource': 'fundingRate',
            'symbol': symbol,
            'policy': 'minute_mark_open_estimate',
            'estimated_events': estimates,
            'unresolved_events': unresolved,
            'approval_status': 'warning',
        }
    )
    return recovered


def _funding_openings(
    transport: BinanceTransport,
    symbol: str,
    wanted_minutes: set[int],
    marks: list[list[Any]],
) -> dict[int, Any]:
    openings = {
        int(row[0]): row[1] for row in marks if int(row[0]) in wanted_minutes
    }
    for timestamp in sorted(wanted_minutes - openings.keys()):
        rows = download_mark_klines(
            transport,
            symbol=symbol,
            timeframe='1m',
            start_ms=timestamp,
            end_ms=timestamp + 59_999,
        )
        for row in rows:
            if int(row[0]) == timestamp and int(row[6]) == timestamp + 59_999:
                openings[timestamp] = row[1]
    return openings


def _recover_events(
    events: list[dict[str, Any]],
    wanted: dict[int, int],
    openings: dict[int, Any],
    symbol: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[int]]:
    recovered = []
    estimates = []
    unresolved = []
    for event in events:
        timestamp = int(event['fundingTime'])
        minute = wanted.get(timestamp)
        if minute is None:
            recovered.append(event)
            continue
        price = openings.get(minute)
        if price is None:
            unresolved.append(timestamp)
            recovered.append(event)
            continue
        try:
            parsed = Decimal(str(price))
            if not parsed.is_finite() or parsed <= 0:
                raise ValueError('nonpositive or nonfinite mark')
        except (InvalidOperation, ValueError) as error:
            raise DatasetValidationError(
                'Invalid Binance opening funding mark for '
                f'{symbol}'
                ' at '
                f'{timestamp}'
            ) from error
        recovered.append(
            {**event, 'markPrice': str(price), 'fundingPriceEstimated': True}
        )
        estimates.append(
            {
                'funding_time': timestamp,
                'mark_open_time': minute,
                'mark_open': str(price),
            }
        )
    return recovered, estimates, unresolved
