"""Canonical aliases for Binance spot and linear-perpetual observations."""

import polars as pl


def with_market_aliases(frame: pl.DataFrame) -> pl.DataFrame:
    aliases = {
        'continuous_symbol': pl.col('symbol'),
        'active_contract': pl.col('symbol'),
        'source_contract_symbol': pl.col('symbol'),
        'adjustment_mode': pl.lit('unadjusted'),
    }
    return frame.with_columns(
        [
            expression.alias(name)
            for name, expression in aliases.items()
            if name not in frame.columns
        ]
    )
