# Binance Adapter

Standalone Python 3.12+ market-data package, version 0.1.0.
Extracted from backtest-engine commit 987795ab31c4554a6be07b8de33ec9fb989acea2.

Supports public spot and USD-M linear perpetual REST data, paginated candles,
aggregate trades, funding and mark prices; checksum-verified monthly archives;
canonical spot/perpetual bar, trade and quote normalization; closed-bar polling.
No credentials are needed for these public endpoints.

~~~python
from binance_adapter.download import download_klines, request_bounds
from binance_adapter.normalize import normalize_klines, symbol_metadata
from binance_adapter.transport import BinanceHttpTransport, endpoint

client = BinanceHttpTransport()
metadata = symbol_metadata(client.get("spot", endpoint("spot", "exchangeInfo")), "BTCUSDT")
start, end = request_bounds("2024-01-01", "2024-01-02")
rows = download_klines(client, product="spot", symbol="BTCUSDT",
                       timeframe="5m", start_ms=start, end_ms=end)
frame = normalize_klines(product="spot", symbol="BTCUSDT", timeframe="5m",
                         metadata=metadata, klines=rows)
frame.write_parquet("bars.parquet")
~~~

BinanceAdapterError represents expected failures. The transport accepts an
injected opener for proxies and offline fixtures. Dates are inclusive in
request_bounds; candle visibility follows the original close timestamps.
Current filters do not prove historical trading rules. Inverse/quanto contracts
and private order routing are outside this package.

This package imports no backtest engine, strategies, execution or UI. The host
retains its own catalog, approval gates, historical rule archives, dataset reuse
and raw-response publication. Canonical aliases and funding semantics remain
unchanged. Raw bytes can be obtained with BinanceHttpTransport.read_bytes;
archive hashes are verified before parsing.

## Independent installation and checks

~~~powershell
uv sync --locked
uv run pytest -q
uv run python tools/check_python_preferences.py
uv build
~~~

Default tests are deterministic and offline. Credentials, runtime data and
private strategies are excluded from Git.
