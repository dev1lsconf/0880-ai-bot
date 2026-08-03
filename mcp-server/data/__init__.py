"""
Data layer multi-activo.
- Yahoo Finance (API pública v8, sin keys) -> acciones, ETFs, índices
- Binance (API pública) -> crypto spot/futures
- Synth -> generador realista para demo offline / paper trading
"""
from __future__ import annotations

import json
import math
import random
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

# ----------------------------------------------------------------------------
# Tipos comunes
# ----------------------------------------------------------------------------

@dataclass
class Candle:
    ts: int            # epoch ms (UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float


def candles_to_dicts(candles: list[Candle]) -> list[dict]:
    return [
        {"ts": c.ts, "open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume}
        for c in candles
    ]


def _http_json(url: str, timeout: float = 15.0) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ----------------------------------------------------------------------------
# Yahoo Finance (acciones / ETFs / índices / futuros)
# ----------------------------------------------------------------------------

class YahooData:
    """Candles históricas desde Yahoo Finance v8 chart API (sin API key)."""

    RANGES = {"1d": "1d", "5d": "5d", "1mo": "1mo", "6mo": "6mo", "1y": "1y", "5y": "5y", "max": "max"}

    def __init__(self, symbol: str, interval: str = "1d"):
        self.symbol = symbol.upper()
        self.interval = interval

    def fetch(self, range_: str = "1y") -> list[Candle]:
        if range_ not in self.RANGES:
            raise ValueError(f"range debe ser uno de {list(self.RANGES)}")
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{urllib.parse.quote(self.symbol)}?range={range_}&interval={self.interval}"
        )
        data = _http_json(url)
        result = data["chart"]["result"][0]
        ts = result.get("timestamp") or []
        q = result["indicators"]["quote"][0]
        opens, highs, lows, closes, vols = q.get("open"), q.get("high"), q.get("low"), q.get("close"), q.get("volume")
        candles = []
        for i, t in enumerate(ts):
            try:
                candles.append(
                    Candle(
                        ts=int(t * 1000),
                        open=float(opens[i]) if opens and opens[i] is not None else float(closes[i]),
                        high=float(highs[i]) if highs and highs[i] is not None else float(closes[i]),
                        low=float(lows[i]) if lows and lows[i] is not None else float(closes[i]),
                        close=float(closes[i]),
                        volume=float(vols[i]) if vols and vols[i] is not None else 0.0,
                    )
                )
            except (TypeError, IndexError):
                continue
        return candles

    def quote(self) -> dict:
        """Precio en tiempo real (intraday)."""
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{urllib.parse.quote(self.symbol)}?range=1d&interval=1m"
        )
        data = _http_json(url)
        result = data["chart"]["result"][0]
        meta = result.get("meta", {})
        return {
            "symbol": self.symbol,
            "price": meta.get("regularMarketPrice"),
            "previous_close": meta.get("chartPreviousClose"),
            "change": meta.get("regularMarketPrice", 0) - (meta.get("chartPreviousClose") or 0),
            "currency": meta.get("currency"),
            "exchange": meta.get("exchangeName"),
            "ts": int(time.time() * 1000),
        }


# ----------------------------------------------------------------------------
# Binance (crypto)
# ----------------------------------------------------------------------------

class BinanceData:
    """Candles + precios desde la API pública de Binance (sin keys)."""

    BASE = "https://api.binance.com/api/v3"
    BASE_F = "https://fapi.binance.com/fapi/v1"
    INTERVALS = {"1m", "5m", "15m", "1h", "4h", "1d", "1w"}

    def __init__(self, symbol: str, market: str = "spot"):
        self.symbol = symbol.upper()
        self.market = market  # 'spot' | 'futures'

    def fetch(self, interval: str = "1h", limit: int = 1000) -> list[Candle]:
        if interval not in self.INTERVALS:
            raise ValueError(f"interval debe ser uno de {sorted(self.INTERVALS)}")
        base = self.BASE_F if self.market == "futures" else self.BASE
        url = f"{base}/klines?symbol={self.symbol}&interval={interval}&limit={limit}"
        rows = _http_json(url)
        return [
            Candle(
                ts=int(r[0]),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]),
            )
            for r in rows
        ]

    def ticker(self) -> dict:
        base = self.BASE_F if self.market == "futures" else self.BASE
        url = f"{base}/ticker/24hr?symbol={self.symbol}"
        t = _http_json(url)
        return {
            "symbol": self.symbol,
            "price": float(t["lastPrice"]),
            "change": float(t["priceChange"]),
            "change_pct": float(t["priceChangePercent"]),
            "high": float(t["highPrice"]),
            "low": float(t["lowPrice"]),
            "volume": float(t["volume"]),
            "ts": int(time.time() * 1000),
        }


# ----------------------------------------------------------------------------
# Synth — generador realista (demo offline, paper trading)
# ----------------------------------------------------------------------------

class SynthData:
    """Genera datos sintéticos de mercado con drift, volatilidad y régimen
    cambiante. Suficiente para probar el stack completo sin conexión."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        np.random.seed(seed)

    def candles(self, n: int = 600, base: float = 100.0, vol: float = 0.02, drift: float = 0.0002,
                interval_ms: int = 3600_000) -> list[Candle]:
        """Serie GBM (Geometric Brownian Motion) con volatilidad clustering."""
        prices = np.empty(n)
        prices[0] = base
        v = vol
        for i in range(1, n):
            # cambio de régimen ocasional
            if self.rng.random() < 0.02:
                v = vol * self.rng.uniform(0.4, 2.2)
            ret = drift + v * np.random.randn()
            prices[i] = prices[i - 1] * math.exp(ret)
        now = int(time.time() * 1000)
        candles = []
        for i in range(n):
            o = prices[i] * (1 + self.rng.uniform(-0.004, 0.004))
            c = prices[i]
            h = max(o, c) * (1 + abs(self.rng.gauss(0, 0.002)))
            l = min(o, c) * (1 - abs(self.rng.gauss(0, 0.002)))
            candles.append(Candle(now - (n - i) * interval_ms, o, h, l, c, self.rng.uniform(1e4, 1e6)))
        return candles

    @staticmethod
    def trades(n: int = 6000, win_rate: float = 0.60, seed: int = 42) -> list[dict]:
        """Lote de trades simulados con distribución de outcomes realista."""
        rng = random.Random(seed)
        trades = []
        equity = 0.0
        ts = int(time.time() * 1000) - n * 3600_000
        for i in range(n):
            win = rng.random() < win_rate
            # tamaño del outcome: colas gordas
            r = abs(rng.gauss(0.5, 0.9)) ** 1.6
            pnl = (r * 120 if win else -r * 165) + rng.gauss(0, 8)
            equity += pnl
            trades.append(
                {
                    "id": i + 1,
                    "ts": ts + i * 3600_000,
                    "symbol": rng.choice(["AAPL", "TSLA", "BTCUSDT", "ETHUSDT", "ES=F", "SPY", "NVDA"]),
                    "side": "LONG" if win or rng.random() < 0.5 else "SHORT",
                    "pnl": round(pnl, 2),
                    "equity": round(equity, 2),
                    "win": win,
                    "entry": round(rng.uniform(50, 5000), 2),
                    "exit": round(rng.uniform(50, 5000), 2),
                    "r_multiple": round(rng.uniform(0.2, 4.0), 2),
                }
            )
        return trades


# ----------------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------------

ASSET_CLASS_HINTS = {
    "STOCK": ("yahoo", {"interval": "1d"}),
    "CRYPTO": ("binance", {"market": "spot"}),
    "CONTRACT": ("yahoo", {"interval": "1d"}),  # futuros E-mini, opciones vía IBKR en ejecución
}


def get_data_source(asset_class: str, symbol: str, **kwargs):
    """Devuelve una instancia de fuente de datos según clase de activo."""
    ac = asset_class.upper()
    if ac == "CRYPTO":
        return BinanceData(symbol, market=kwargs.get("market", "spot"))
    if ac in ("STOCK", "CONTRACT"):
        return YahooData(symbol, interval=kwargs.get("interval", "1d"))
    raise ValueError(f"asset_class desconocido: {asset_class} (usa STOCK | CRYPTO | CONTRACT)")
