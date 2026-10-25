from __future__ import annotations

from typing import Any


def optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def instrument_payload(
    product: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    filters = {item['filterType']: item for item in metadata.get('filters', [])}
    lot = filters.get('LOT_SIZE', {})
    price = filters.get('PRICE_FILTER', {})
    minimum_filter = filters.get('NOTIONAL', filters.get('MIN_NOTIONAL', {}))
    minimum_notional = minimum_filter.get(
        'minNotional', minimum_filter.get('notional')
    )
    quote = str(metadata['quoteAsset'])
    return {
        'symbol': str(metadata['symbol']),
        'asset_class': 'crypto',
        'instrument_type': 'spot' if product == 'spot' else 'perpetual',
        'contract_type': 'spot' if product == 'spot' else 'linear',
        'price_currency': quote,
        'pnl_currency': str(metadata.get('marginAsset') or quote),
        'base_currency': str(metadata['baseAsset']),
        'quote_currency': quote,
        'settlement_currency': str(metadata.get('marginAsset') or quote),
        'tick_size': optional_positive(price.get('tickSize')),
        'quantity_step': optional_positive(lot.get('stepSize')),
        'minimum_quantity': optional_positive(lot.get('minQty')),
        'minimum_notional': optional_positive(minimum_notional),
    }


def optional_positive(value: Any) -> float | None:
    if value is None:
        return None
    parsed = float(value)
    return parsed if parsed > 0.0 else None
