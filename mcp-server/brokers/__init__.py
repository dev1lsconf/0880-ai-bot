"""
Broker abstraction: paper (simulado), binance (crypto real), ibkr (acciones/futuros/opciones).
Todos exponen la misma interfaz para que el MCP server y el dashboard sean agnósticos.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from data import SynthData


@dataclass
class Order:
    id: str
    symbol: str
    asset_class: str
    side: str            # BUY | SELL
    qty: float
    order_type: str = "MARKET"
    price: float | None = None
    status: str = "NEW"
    filled_price: float | None = None
    ts: int = field(default_factory=lambda: int(time.time() * 1000))


@dataclass
class Position:
    symbol: str
    asset_class: str
    qty: float
    avg_entry: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    leverage: float = 1.0


class PaperBroker:
    """Ejecución simulada con datos del mercado (o sintéticos si no hay red)."""

    def __init__(self, initial_cash: float = 100_000.0, seed: int = 42):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self.closed_trades: list[dict] = []
        self.rng = random.Random(seed)
        self.synth = SynthData(seed=seed)
        self._prices: dict[str, float] = {}

    def _price(self, symbol: str) -> float:
        if symbol not in self._prices:
            self._prices[symbol] = self.rng.uniform(20, 5000)
        # random walk suave
        self._prices[symbol] *= 1 + self.rng.gauss(0, 0.004)
        return self._prices[symbol]

    def place_order(self, symbol: str, asset_class: str, side: str, qty: float,
                    order_type: str = "MARKET", price: float | None = None) -> Order:
        fill = self._price(symbol) if price is None else price
        oid = f"PAPER-{int(time.time()*1000)}-{self.rng.randint(100,999)}"
        order = Order(oid, symbol, asset_class, side.upper(), qty, order_type, price, "FILLED", fill)
        self.orders.append(order)
        pos = self.positions.get(symbol)
        if pos is None:
            self.positions[symbol] = Position(symbol, asset_class, 0.0, fill, leverage=1.0)
            pos = self.positions[symbol]
        if side.upper() == "BUY":
            self.cash -= fill * qty
            total_cost = pos.avg_entry * abs(pos.qty) + fill * qty
            pos.qty += qty
            pos.avg_entry = total_cost / abs(pos.qty) if pos.qty else fill
        else:
            realized = (fill - pos.avg_entry) * qty
            self.cash += fill * qty
            pos.qty -= qty
            pos.realized_pnl += realized
            if pos.qty <= 0:
                self.closed_trades.append({
                    "symbol": symbol, "side": "SELL", "pnl": realized,
                    "ts": int(time.time() * 1000), "asset_class": asset_class,
                })
                self.positions.pop(symbol, None)
        return order

    def close_position(self, symbol: str) -> dict:
        """Cierra la posición abierta de un símbolo (vende toda la cantidad)."""
        pos = self.positions.get(symbol)
        if pos is None or pos.qty == 0:
            return {"ok": False, "error": f"no hay posicion abierta en {symbol}"}
        px = self._price(symbol)
        realized = (px - pos.avg_entry) * pos.qty
        self.cash += px * pos.qty
        self.closed_trades.append({
            "symbol": symbol, "side": "SELL", "pnl": round(realized, 2),
            "ts": int(time.time() * 1000), "asset_class": pos.asset_class,
        })
        self.positions.pop(symbol, None)
        return {"ok": True, "symbol": symbol, "realized_pnl": round(realized, 2), "cash": round(self.cash, 2)}

    def positions_list(self) -> list[dict]:
        out = []
        for sym, p in self.positions.items():
            px = self._price(sym)
            p.unrealized_pnl = (px - p.avg_entry) * p.qty
            out.append({
                "symbol": sym, "asset_class": p.asset_class, "qty": p.qty,
                "avg_entry": round(p.avg_entry, 4), "mark": round(px, 4),
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "realized_pnl": round(p.realized_pnl, 2),
                "leverage": p.leverage,
            })
        return out

    def account(self) -> dict:
        pos_value = sum(p.qty * self._price(s) for s, p in self.positions.items())
        realized = sum(t["pnl"] for t in self.closed_trades)
        return {
            "cash": round(self.cash, 2),
            "positions_value": round(pos_value, 2),
            "equity": round(self.cash + pos_value, 2),
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": round(pos_value - sum(p.qty * p.avg_entry for p in self.positions.values()), 2),
            "open_positions": len(self.positions),
            "closed_trades": len(self.closed_trades),
            "broker": "paper",
        }


class BinanceBroker:
    """Ejecución real en Binance spot/futures. Requiere API keys en config."""

    def __init__(self, api_key: str | None = None, api_secret: str | None = None, testnet: bool = True):
        if not api_key or not api_secret:
            raise ValueError("BinanceBroker necesita API_KEY/API_SECRET (o usa testnet con PAPER mode)")
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base = "https://testnet.binancefuture.com" if testnet else "https://fapi.binance.com"

    def place_order(self, symbol: str, asset_class: str, side: str, qty: float,
                    order_type: str = "MARKET", price: float | None = None) -> dict:
        # TODO: firmar petición HMAC-SHA256 (ver README). Placeholder para no exponer keys.
        return {"error": "Requiere firma HMAC; implementación en broker/binance_live.py (documentada en README)"}

    def positions_list(self) -> list[dict]:
        return []

    def account(self) -> dict:
        return {"broker": "binance", "note": "requiere keys y firma HMAC"}


class IBKRBroker:
    """Interactive Brokers: acciones, futuros, opciones, forex.
    Usa la API Python oficial (ib_insync/ibapi) — ver README para conectar paper account."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        # 7497 = paper, 7496 = live. Requiere TWS/Gateway corriendo.
        self.host, self.port, self.client_id = host, port, client_id

    def connect(self):
        try:
            from ib_insync import IB  # type: ignore
            self.ib = IB()
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            return {"status": "connected", "port": self.port}
        except ImportError:
            return {"error": "ib_insync no instalado. pip install ib_insync. TWS/IB Gateway debe estar abierto."}
        except Exception as e:
            return {"error": f"no se pudo conectar: {e}"}

    def place_order(self, symbol: str, asset_class: str, side: str, qty: float,
                    order_type: str = "MARKET", price: float | None = None) -> dict:
        if not hasattr(self, "ib"):
            return {"error": "no conectado. Llama connect() primero (requiere TWS paper)."}
        return {"note": "Implementación ib_insync en README §IBKR — orden no enviada por seguridad"}


def get_broker(name: str = "paper", **kwargs):
    name = (name or "paper").lower()
    if name == "paper":
        return PaperBroker(**kwargs)
    if name == "binance":
        return BinanceBroker(**kwargs)
    if name == "ibkr":
        return IBKRBroker(**kwargs)
    raise ValueError(f"broker desconocido: {name} (paper | binance | ibkr)")
