"""
Backtest engine vectorizado + métricas de rendimiento + Monte Carlo.
Soporta acciones, crypto y contratos (futuros) con el mismo API.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

# ----------------------------------------------------------------------------
# Estrategias (señales sobre arrays de closes)
# ----------------------------------------------------------------------------

def sma(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 0:
        return np.full_like(x, np.nan)
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = np.full_like(x, np.nan)
    if len(x) >= n:
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def ema(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 0:
        return np.full_like(x, np.nan)
    alpha = 2.0 / (n + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def rsi(x: np.ndarray, n: int = 14) -> np.ndarray:
    delta = np.diff(x, prepend=x[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    ag = ema(gain, n)
    al = ema(loss, n)
    rs = np.divide(ag, al, out=np.full_like(ag, 100.0), where=al != 0)
    return 100.0 - 100.0 / (1.0 + rs)


@dataclass
class StrategyResult:
    name: str
    positions: np.ndarray  # 1 = long, -1 = short, 0 = flat


def strategy_trend_follow(closes: np.ndarray, fast: int = 20, slow: int = 50) -> StrategyResult:
    """Cruce de medias móviles (trend). Long cuando fast>slow, short cuando <."""
    f, s = sma(closes, fast), sma(closes, slow)
    pos = np.zeros_like(closes)
    valid = ~(np.isnan(f) | np.isnan(s))
    diff = f - s
    pos[valid] = np.where(diff[valid] > 0, 1.0, -1.0)
    return StrategyResult("Trend (MA cross)", pos)


def strategy_mean_reversion(closes: np.ndarray, lookback: int = 20, buy_rsi: float = 30.0,
                            sell_rsi: float = 70.0) -> StrategyResult:
    """Mean reversion con RSI. Long en oversold, short en overbought."""
    r = rsi(closes, 14)
    pos = np.zeros_like(closes)
    pos[r < buy_rsi] = 1.0
    pos[r > sell_rsi] = -1.0
    # salir al cruzar 50
    pos[r > 50.0] = 0.0
    return StrategyResult("Mean Reversion (RSI)", pos)


def strategy_breakout(closes: np.ndarray, lookback: int = 20, atr_mult: float = 2.0) -> StrategyResult:
    """Breakout de máximo/mínimo de N barras (Donchian)."""
    n = len(closes)
    pos = np.zeros(n)
    for i in range(lookback, n):
        hi = np.max(closes[i - lookback:i])
        lo = np.min(closes[i - lookback:i])
        if closes[i] > hi:
            pos[i] = 1.0
        elif closes[i] < lo:
            pos[i] = -1.0
    return StrategyResult(f"Breakout Donchian({lookback})", pos)


STRATEGIES = {
    "trend": strategy_trend_follow,
    "mean_reversion": strategy_mean_reversion,
    "breakout": strategy_breakout,
}


# ----------------------------------------------------------------------------
# Backtest
# ----------------------------------------------------------------------------

@dataclass
class Trade:
    entry_ts: int
    exit_ts: int
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    pnl: float
    ret_pct: float
    bars: int


@dataclass
class BacktestResult:
    symbol: str
    asset_class: str
    strategy: str
    equity: np.ndarray
    returns: np.ndarray
    trades: list[Trade] = field(default_factory=list)
    params: dict = field(default_factory=dict)

    # ----- métricas derivadas -----
    @property
    def total_pnl(self) -> float:
        return float(self.equity[-1] - self.equity[0]) if len(self.equity) else 0.0

    @property
    def total_return_pct(self) -> float:
        return (self.equity[-1] / self.equity[0] - 1.0) * 100.0 if len(self.equity) and self.equity[0] else 0.0

    @property
    def win_rate(self) -> float:
        wins = [t for t in self.trades if t.pnl > 0]
        return (len(wins) / len(self.trades) * 100.0) if self.trades else 0.0

    @property
    def num_trades(self) -> int:
        return len(self.trades)

    @property
    def avg_trade(self) -> float:
        return float(np.mean([t.pnl for t in self.trades])) if self.trades else 0.0

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        return (gross_win / gross_loss) if gross_loss > 0 else math.inf

    @property
    def sharpe(self) -> float:
        r = self.returns
        if len(r) < 2 or np.std(r) == 0:
            return 0.0
        return float(np.mean(r) / np.std(r) * math.sqrt(len(r)))

    @property
    def max_drawdown(self) -> float:
        eq = self.equity
        if len(eq) < 2:
            return 0.0
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak
        return float(np.min(dd) * 100.0)


def run_backtest(candles, symbol: str, asset_class: str, strategy: str = "trend",
                 initial_capital: float = 10_000.0, fee_pct: float = 0.001,
                 leverage: float = 1.0, params: dict | None = None) -> BacktestResult:
    """Backtest de una sola pasada (in-sample). Para validación real usa walk_forward()."""
    closes = np.array([c.close for c in candles], dtype=float)
    ts = np.array([c.ts for c in candles], dtype=np.int64)
    if len(closes) < 60:
        raise ValueError("Se necesitan al menos 60 velas")

    fn = STRATEGIES.get(strategy)
    if fn is None:
        raise ValueError(f"estrategia desconocida: {strategy} (disponibles: {list(STRATEGIES)})")
    params = params or {}
    result = fn(closes, **params)
    pos = result.positions

    equity = np.empty_like(closes)
    equity[0] = initial_capital
    rets = np.zeros_like(closes)
    trades: list[Trade] = []
    in_trade = False
    entry_price = 0.0
    entry_ts = 0
    entry_side = ""
    entry_idx = 0
    position_value = 0.0  # PnL acumulado de trades CERRADOS (capital base)

    for i in range(1, len(closes)):
        prev_pos, cur_pos = pos[i - 1], pos[i]
        # cambio de posición -> cerrar trade anterior
        if in_trade and (cur_pos == 0 or cur_pos != prev_pos or i == len(closes) - 1):
            exit_price = closes[i]
            mult = 1.0 if entry_side == "LONG" else -1.0
            gross = (exit_price - entry_price) * mult
            ret_pct = gross / entry_price if entry_price else 0.0
            pnl = initial_capital * ret_pct * leverage - initial_capital * fee_pct * 2
            trades.append(Trade(entry_ts, int(ts[i]), symbol, entry_side, entry_price, exit_price, pnl, ret_pct * 100, i - entry_idx))
            position_value += pnl  # capital base acumulado tras cierre
            in_trade = False

        if cur_pos != 0 and not in_trade:
            in_trade = True
            entry_price = closes[i]
            entry_ts = int(ts[i])
            entry_side = "LONG" if cur_pos > 0 else "SHORT"
            entry_idx = i

        # equity: capital base acumulado + PnL marcado de posición abierta
        if in_trade:
            mult = 1.0 if entry_side == "LONG" else -1.0
            ret_pct = (closes[i] - entry_price) / entry_price * mult
            mark_pnl = initial_capital * ret_pct * leverage
            equity[i] = position_value + initial_capital + mark_pnl
        else:
            equity[i] = position_value + initial_capital

    rets = np.diff(equity, prepend=equity[0]) / np.maximum(equity[0], 1e-9)
    return BacktestResult(
        symbol=symbol, asset_class=asset_class, strategy=f"{result.name} (leverage {leverage}x)",
        equity=equity, returns=rets, trades=trades,
        params={"strategy": strategy, "initial_capital": initial_capital, "leverage": leverage, **params},
    )


# ----------------------------------------------------------------------------
# Walk-forward + Monte Carlo (validación honesta)
# ----------------------------------------------------------------------------

def walk_forward(candles, symbol: str, asset_class: str, strategy: str = "trend",
                 train_frac: float = 0.6, folds: int = 4, **bt_kwargs) -> list[BacktestResult]:
    """Walk-forward analysis: entrena en 60%, valida en 40%, desliza ventanas."""
    n = len(candles)
    step = (n - int(n * train_frac)) // max(folds, 1)
    results = []
    for k in range(folds):
        end_train = int(n * train_frac) + k * step
        end_test = min(end_train + step, n)
        if end_test - end_train < 50:
            break
        train = candles[:end_train]
        test = candles[end_train:end_test]
        # optimización rápida en train (elige lookback con mejor sharpe)
        best = None
        for lb in (10, 20, 50):
            try:
                r = run_backtest(train, symbol, asset_class, strategy, params={"lookback": lb}, **bt_kwargs)
                if best is None or r.sharpe > best.sharpe:
                    best = r
            except Exception:
                continue
        best_params = {"lookback": best.params.get("lookback", 20)} if best else {}
        r_test = run_backtest(test, symbol, asset_class, strategy, params=best_params, **bt_kwargs)
        results.append(r_test)
    return results


def monte_carlo(results: list[BacktestResult], n_sims: int = 2000, seed: int = 7) -> dict:
    """Simulación Monte Carlo sobre la distribución de returns por trade."""
    rng = random.Random(seed)
    all_trades = [t for r in results for t in r.trades]
    if not all_trades:
        return {"n_sims": 0, "prob_profit": 0.0, "expected_pnl": 0.0, "var95": 0.0, "max_drawdown_p95": 0.0}
    pnls = np.array([t.pnl for t in all_trades])
    eqs = []
    for _ in range(n_sims):
        sample = rng.choices(pnls.tolist(), k=len(pnls))
        eqs.append(np.cumsum(sample))
    eqs = np.array(eqs)
    final = eqs[:, -1]
    dd = []
    for e in eqs:
        peak = np.maximum.accumulate(e)
        dd.append(np.min((e - peak) / np.maximum(peak, 1e-9)))
    return {
        "n_sims": n_sims,
        "n_trades": len(pnls),
        "prob_profit": float(np.mean(final > 0) * 100.0),
        "expected_pnl": float(np.mean(final)),
        "median_pnl": float(np.median(final)),
        "var95": float(np.percentile(final, 5)),
        "max_drawdown_p95": float(np.percentile(dd, 95) * 100.0),
    }
