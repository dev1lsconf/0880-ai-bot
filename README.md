# 0880 AI BOT — Multi-Market Trading Dashboard

A **MCP-server-driven**, locally-running trading dashboard that bridges AI agents (Claude / Claude Code) with real market data from **Binance** (crypto) and **Yahoo Finance** (stocks), a paper trading broker, and statistical backtesting/Monte Carlo engines.

No API keys required for public data. No proprietary backend. Runs 100% local on Windows/Linux.

---

## 🚀 Quick Start

```bash
# 1. Run dashboard server (HTTP + WebSocket en puertos 8787/8788)
cd ~/trading-stack/mcp-server
python -u run_server.py

# 2. Abrir en browser
http://127.0.0.1:8787
```

> Server runs in background. Pestañas: **LIVE** (gráficos), **MARKET** (rankings reales), **POSITIONS** (paper broker).

---

## 🧩 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Claude (LLM)  ──►  MCP Server (stdio / JSON-RPC 2.0)        │
│                        ↓ /api/snapshot + /ws                 │
│                  Dashboard (HTTP + WebSocket)                 │
│                        ↓                                    │
│  ┌──────────┬──────────┬──────────┬────────────────────┐   │
│  │ Yahoo    │ Binance  │  Backtest│  Paper Broker      │   │
│  │ Finance  │ Public   │  Engine  │  (paper/simulated) │   │
│  └──────────┴──────────┴──────────┴────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Tech Stack
| Component | Stack |
|---|---|
| **Protocol** | Model Context Protocol (MCP) v2024-02-02, stdio/JSON-RPC 2.0 |
| **Backend** | Python 3.11 stdlib (`http.server`, `json`, `urllib`) — **0 dependencias externas** |
| **Frontend** | HTML5 + CSS3 (custom properties light theme) + Canvas 2D vanilla JS |
| **WebSocket** | `websockets` v12 (streaming snapshot cada 3s) |
| **Data Sources** | Binance REST (`/api/v3/ticker/24hr`) + Yahoo Finance (`/v1/finance/trending`) — públicas, sin API key |
| **Backtest** | Moving-average crossover + random-walk Monte Carlo (2,000 sims) |
| **Broker** | Paper broker (saldo $100k virtual, órdenes simuladas) |

---

## 📊 Dashboard Views

### LIVE — Gráficos analíticos
1. **Probability Lattice** — scatter multi-activo (AAPL/TSLA/BTCUSDT) + distribución de PnL
2. **Equity Curve** — curva de equity real del backtest + simulaciones Monte Carlo
3. **Asset Correlation Heatmap** — matriz de correlación multi-activo (rojo=negativo, verde=positivo)
4. **Return Distribution** — histograma de 2,000 simulaciones + curva normal superpuesta (VaR 95%)

### MARKET — Rankings en vivo (10 ítems cada sección)
| Sección | Fuente | Datos |
|---|---|---|
| **Top Movers — Acciones** | Yahoo Finance (trending) | Símbolos reales + variación |
| **Doldrums — Acciones** | Yahoo Finance | Bottom 10 por cambio 24h |
| **Top Movers — Criptomonedas** | Binance Public API | **Precios + % cambio + volumen reales** |

### POSITIONS — Paper broker
- Saldo disponible, valor cartera, posiciones abiertas con PnL no realizado
- Botones COMPRAR/CERRAR → ejecuta via POST `/api/snapshot` → `place_order`/`close_position`

---

## 🔧 MCP Tools (para agentes Claude)

El server expone 11 tools sobre protocol stdio:

| Tool | Parámetros | Descripción |
|---|---|---|
| `get_quote` | `asset_class, symbol` | Precio + cambio de un activo |
| `get_candles` | `asset_class, symbol, interval, limit` | Serie temporal OHLCV |
| `scan_markets` | `symbols, asset_class` | Barrido multi-activo simultáneo |
| `run_backtest` | `asset_class, symbol, strategy, params, leverage` | Backtest con métricas PnL/Sharpe/DD |
| `walk_forward` | `asset_class, symbol, strategy` | Walk-forward out-of-sample (4 folds) |
| `monte_carlo` | `asset_class, symbol, strategy` | 2,000 simulaciones, P(profit)/VaR |
| `analyze_strategy` | `asset_class, symbol` | Análisis completo + snapshot |
| `place_order` | `symbol, asset_class, side, qty` | Orden simulada en paper broker |
| `get_positions` | — | Posiciones abiertas del broker |
| `get_account` | — | Estado de cuenta (cash, equity, PnL) |
| `get_dashboard_snapshot` | — | JSON completo del dashboard |

---

## 📁 Project Structure

```
trading-stack/
├── mcp-server/           # MCP Server principal
│   ├── server.py          # Protocolo MCP + 11 tools + snapshot builder
│   ├── run_server.py      # Launcher HTTP+WS (puertos 8787/8788)
│   ├── brokers/__init__.py # PaperBroker (place_order, close_position, positions_list, account)
│   ├── data/__init__.py    # YahooData / BinanceData / SynthData
│   ├── backtest/__init__.py# engine (MovingAvg, MonteCarlo, WalkForward)
│   └── api/
│       └── ws_server.py    # HTTP estático + WS streaming + POST acciones
├── dashboard/             # Frontend del dashboard
│   ├── index.html         # Estructura light-theme (brand 0880 AI BOT)
│   ├── style.css          # Paleta foto: #F8F9FA / #28A745 / #DC3545
│   └── app.js             # Canvas renderers + tab switcher + polling WS
├── pine-templates/        # Plantillas TradingView Pine Script
│   └── strategies.pine    # 3 estrategias listas
├── docker-compose.yml     # Despliegue Docker (opcional)
└── Dockerfile             # Imagen container (opcional)
```

---

## 🎨 Style Guide

| Elemento | Color | Hex |
|---|---|---|
| Fondo general | Off-white | `#F8F9FA` |
| Paneles/card | Blanco | `#FFFFFF` |
| Texto principal | Near-black | `#212529` |
| Títulos/dim | Gray | `#495057` |
| **Profit / verde** | Emerald | `#28A745` |
| **Loss / rojo** | Alert red | `#DC3545` |
| Acento/cian | Bootstrap blue | `#0D6EFD` |
| Bordes | Light gray | `#DEE2E6` |
| Monospace | Consolas/SF Mono | — |

---

## 🐳 Docker

```bash
cd ~/trading-stack
docker-compose up --build -d
# → Dashboard en http://localhost:8787
```

---

## 🏦 Broker Modes

| Mode | Config | Execution | Price Feed |
|---|---|---|---|
| **Paper (default)** | `BROKER=paper` | Simulada (saldo $100k) | Binance público + SynthData |
| **Binance** | `BROKER=binance API_KEY=***` | Real (requiere API key con firma HMAC) | Binance Spot/futures |
| **IBKR** | `BROKER=ibkr` | Real (requiere TWS/IB gateway) | IBKR API |

---

## 📡 Endpoints

| Endpoint | Method | Descripción |
|---|---|---|
| `/` | GET | Dashboard HTML |
| `/app.js`, `/style.css` | GET | Assets estáticos |
| `/api/snapshot` | GET | JSON snapshot completo (PnL, rankings, account, monte_carlo) |
| `/api/snapshot` | POST | Ejecuta `place_order` / `close_position` en paper broker |
| `/ws` | WS | Streaming snapshot en vivo cada 3s (msg `{"type":"snapshot","data":{...}}`) |

---

## 💡 Use Cases

1. **AI trading agent**: Claude escanea rankings, backtestea estrategias, ejecuta órdenes paper
2. **Research**: Walk-forward + Monte Carlo validan edge de forma honesta
3. **Live PnL monitoring**: WS streaming refleja cambios de broker tick-a-tick
4. **Risk dashboard**: Heatmap de correlación + VaR/return distribution

---

*Built with ❤️ on Windows (Python 3.11) — zero external Python deps para el server, 100% stdlib.*