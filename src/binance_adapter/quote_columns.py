"""
Native projection for canonical quotes; legacy coercion stays in its caller.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

import polars as pl

from binance_adapter.exceptions import (
    BinanceAdapterError as DatasetValidationError,
)
from binance_adapter.schema import (
    with_market_aliases as normalize_intraday_asset_frame,
)


def normalize_canonical_quotes(
    *,
    product: str,
    symbol: str,
    metadata: dict[str, Any],
    frame: pl.DataFrame,
    base_row: Callable[
        [str, str, dict[str, Any], datetime, float], dict[str, Any]
    ],
) -> pl.DataFrame | None:
    if not canonical_quote_schema(frame, metadata):
        return None
    names = [
        name
        for name in ('ts', 'bid', 'ask', 'bid_size', 'ask_size', 'event_id')
        if name in frame.columns
    ]
    ordered = frame.select(names).sort('ts').with_row_index('_quote_index')
    invalid = ordered.filter(
        (pl.col('bid') <= 0)
        | (pl.col('ask') <= 0)
        | (pl.col('bid') > pl.col('ask'))
    ).head(1)
    if invalid.height:
        item = invalid.row(0, named=True)
        index, bid, ask = (
            item['_quote_index'],
            float(item['bid']),
            float(item['ask']),
        )
        raise DatasetValidationError(
            f'Invalid quote at row {index}: bid={bid}, ask={ask}'
        )
    ordered = ordered.with_columns(
        pl.col('bid', 'ask').cast(pl.Float64),
        *[
            (pl.col(name) if name in names else pl.lit(None))
            .cast(pl.Float64)
            .alias(name)
            for name in ('bid_size', 'ask_size')
        ],
    ).with_columns(((pl.col('bid') + pl.col('ask')) / 2.0).alias('_midpoint'))
    first = ordered.row(0, named=True)
    base = base_row(product, symbol, metadata, first['ts'], first['_midpoint'])
    projection = {name: pl.lit(value) for name, value in base.items()}
    projection.update(
        {
            name: pl.col('ts')
            for name in ('ts', 'bar_open_ts', 'bar_close_ts', 'available_at')
        }
    )
    projection.update(
        {name: pl.col('_midpoint') for name in ('open', 'high', 'low', 'close')}
    )
    bid_size, ask_size = pl.col('bid_size'), pl.col('ask_size')
    size = (
        pl.when(bid_size.is_null())
        .then(ask_size)
        .when(ask_size.is_null() | (bid_size <= ask_size))
        .then(bid_size)
        .otherwise(ask_size)
        .fill_null(0.0)
    )
    identifier = pl.col('_quote_index').cast(pl.String)
    if 'event_id' in names and ordered.schema['event_id'] != pl.Null:
        present = pl.col('event_id').is_not_null()
        present &= pl.col('event_id') != (
            '' if ordered.schema['event_id'] == pl.String else 0
        )
        identifier = (
            pl.when(present)
            .then(pl.col('event_id').cast(pl.String))
            .otherwise(identifier)
        )
    projection.update(
        {
            'event_id': identifier,
            'bid': pl.col('bid'),
            'ask': pl.col('ask'),
            'bid_size': bid_size,
            'ask_size': ask_size,
            'quote_size': size,
            'volume': size,
            'value': pl.lit(0.0),
            'data_kind': pl.lit('quotes'),
        }
    )
    # The generic record constructor infers Null for a wholly absent side.
    for name in ('bid_size', 'ask_size'):
        if ordered[name].null_count() == ordered.height:
            projection[name] = pl.lit(None)
    return normalize_intraday_asset_frame(
        ordered.select(
            [expression.alias(name) for name, expression in projection.items()]
        )
    )


def canonical_quote_schema(
    frame: pl.DataFrame, metadata: dict[str, Any]
) -> bool:
    if not frame.height or not {'baseAsset', 'quoteAsset'} <= metadata.keys():
        return False
    timestamp = frame.schema['ts']
    if (
        not isinstance(timestamp, pl.Datetime)
        or timestamp.time_unit != 'us'
        or timestamp.time_zone not in (None, 'UTC')
        or frame['ts'].null_count()
    ):
        return False
    for name in ('bid', 'ask', 'bid_size', 'ask_size'):
        if name not in frame.columns:
            continue
        values = frame[name]
        if values.dtype == pl.Null and name.endswith('_size'):
            continue
        if not (values.dtype.is_integer() or values.dtype.is_float()):
            return False
        if name in ('bid', 'ask') and values.null_count():
            return False
        if not values.drop_nulls().is_finite().all():
            return False
    identifier = frame.schema.get('event_id')
    return (
        identifier is None
        or identifier in (pl.String, pl.Null)
        or identifier.is_integer()
    )
