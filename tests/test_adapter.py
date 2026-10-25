"""Offline public-provider contracts, independent of OHLCV Replay."""

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime

import polars as pl
import pytest

from binance_adapter.archive import read_zip_klines, verify_checksum
from binance_adapter.download import canonical_timeframe, download_klines
from binance_adapter.exceptions import BinanceAdapterError
from binance_adapter.funding import ordered_funding_events
from binance_adapter.normalize import normalize_klines
from binance_adapter.transport import BinanceHttpTransport, endpoint


def test_closed_perpetual_bar_keeps_funding_and_visibility():
    stamp = int(datetime(2024, 1, 2, tzinfo=UTC).timestamp() * 1000)
    raw = [stamp, '100', '105', '99', '102', '3', stamp + 59999, '306']
    frame = normalize_klines(
        product='perpetual',
        symbol='ETHUSDT',
        timeframe='1m',
        metadata={'baseAsset': 'ETH', 'quoteAsset': 'USDT'},
        klines=[raw],
        now_ms=stamp + 60000,
        funding=[
            {
                'symbol': 'ETHUSDT',
                'fundingTime': stamp,
                'fundingRate': '0.001',
                'markPrice': '101',
            }
        ],
    )
    row = frame.row(0, named=True)
    assert (row['open'], row['high'], row['low'], row['close']) == (
        100,
        105,
        99,
        102,
    )
    assert row['volume'] == 3 and row['value'] == 306
    assert row['funding_price_rate'] == pytest.approx(0.101)
    assert row['available_at'] == datetime.fromtimestamp(
        (stamp + 59999) / 1000, UTC
    )
    assert row['active_contract'] == row['symbol'] == 'ETHUSDT'
    assert row['currency'] == 'USDT'
    assert frame.schema['ts'] == pl.Datetime('us', 'UTC')
    with pytest.raises(BinanceAdapterError, match='no finalized'):
        normalize_klines(
            product='spot',
            symbol='ETHUSDT',
            timeframe='1m',
            metadata={'baseAsset': 'ETH', 'quoteAsset': 'USDT'},
            klines=[raw],
            now_ms=stamp,
        )


def test_archive_verifies_checksum_and_microsecond_timestamps():
    row = [
        '1735689600000000',
        '100',
        '102',
        '99',
        '101',
        '3',
        '1735689659999000',
        '303',
        '1',
        '1',
        '101',
        '0',
    ]
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('bars.csv', ','.join(row))
    payload = stream.getvalue()
    checksum = hashlib.sha256(payload).hexdigest().encode() + b' bars.zip'
    assert verify_checksum(payload, checksum, 'fixture')
    decoded = read_zip_klines(payload, 'fixture')
    assert decoded[0][0] == 1735689600000
    assert decoded[0][6] == 1735689659999
    with pytest.raises(BinanceAdapterError, match='checksum'):
        verify_checksum(payload + b'changed', checksum, 'fixture')


def test_pagination_advances_past_inclusive_close():
    class Transport:
        def __init__(self):
            self.requests = []

        def get(self, product, path, params):
            self.requests.append(params)
            if len(self.requests) == 1:
                return [
                    [i * 60000, 1, 1, 1, 1, 1, i * 60000 + 59999]
                    for i in range(1000)
                ]
            return [[60000000, 1, 1, 1, 1, 1, 60059999]]

    transport = Transport()
    rows = download_klines(
        transport,
        product='spot',
        symbol='BTCUSDT',
        timeframe='1m',
        start_ms=0,
        end_ms=60059999,
    )
    assert len(rows) == 1001
    assert transport.requests[1]['startTime'] == 60000000
    assert canonical_timeframe('1h') == '60m'


def test_client_accepts_injected_http_without_a_host():
    class Response(io.BytesIO):
        pass

    observed = []

    def opener(request, *, timeout):
        observed.append((request.full_url, timeout))
        return Response(json.dumps({'symbols': []}).encode())

    result = BinanceHttpTransport(opener=opener).get(
        'spot', endpoint('spot', 'exchangeInfo')
    )
    assert result == {'symbols': []}
    assert observed == [
        ('https://data-api.binance.vision/api/v3/exchangeInfo', 30)
    ]


def test_conflicting_funding_events_fail():
    event = {'fundingTime': 0, 'fundingRate': '.001', 'markPrice': '100'}
    assert ordered_funding_events([event, event], 'ETHUSDT') == [event]
    with pytest.raises(BinanceAdapterError, match='Conflicting'):
        ordered_funding_events(
            [event, {**event, 'fundingRate': '.002'}], 'ETHUSDT'
        )
