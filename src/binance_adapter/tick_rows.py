"""Common immutable-input fields for trade and quote observations."""

from datetime import datetime
from typing import Any


def tick_base_row(
    product: str,
    symbol: str,
    metadata: dict[str, Any],
    ts: datetime,
    price: float,
) -> dict[str, Any]:
    base = str(metadata['baseAsset'])
    quote = str(metadata['quoteAsset'])
    settlement = str(metadata.get('marginAsset') or quote)
    return {
        'source': 'binance_archive',
        'exchange': 'BINANCE',
        'engine': product,
        'market': 'crypto',
        'board': 'SPOT' if product == 'spot' else 'USD_M_PERPETUAL',
        'symbol': symbol,
        'timeframe': '1m',
        'ts': ts,
        'bar_open_ts': ts,
        'bar_close_ts': ts,
        'available_at': ts,
        'is_final': True,
        'open': price,
        'high': price,
        'low': price,
        'close': price,
        'currency': quote,
        'dataset_type': 'spot' if product == 'spot' else 'perpetual',
        'asset_class': 'crypto',
        'instrument_type': 'spot' if product == 'spot' else 'perpetual',
        'base_currency': base,
        'quote_currency': quote,
        'settlement_currency': settlement,
        'funding_rate': 0.0,
        'funding_event': False,
    }
