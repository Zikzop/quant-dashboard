# Quant Dashboard — Project Brief

Institutional-style quantitative trading terminal (monorepo). Use this document to onboard AI assistants, collaborators, or future you.

**Repository:** `github.com:Zikzop/quant-dashboard`

---

## 1. What this project is

**Quant Dashboard** combines:

- **Backend** — Python **FastAPI** API that ingests market data, runs a deterministic intelligence pipeline (indicators → regimes → volatility → signals → correlation), and returns a strict JSON contract.
- **Frontend** — **Next.js 16** + **React 19** single-page terminal UI with multi-timeframe (MTF) controls, charts, regime visualization, and a **client-side decision engine** that fuses backend data into trade/no-trade guidance.

**Design goal:** Bloomberg / CQG / Quantower-like density — dark terminal chrome, mono typography, tactical controls — not retail crypto UI.

---

## 2. Repository layout

```
quant-dashboard/
├── docs/
│   └── PROJECT_BRIEF.md     # this file
├── backend/                 # FastAPI + quant engines + research stacks
│   ├── main.py              # HTTP entry (routes only)
│   ├── pipeline/            # Market intelligence orchestration
│   ├── engines/             # HMM, ADX, GARCH, signal, correlation
│   ├── data/                # Data access layer + providers (yahoo, mock)
│   ├── schemas/             # Pydantic API contract
│   ├── assets/              # Asset + timeframe registry
│   ├── alpha_engine/        # research (mostly backend-only)
│   ├── portfolio_engine/
│   ├── risk_engine/
│   ├── backtesting/
│   ├── execution_engine/
│   └── tests/
└── frontend/                # Next.js App Router
    ├── app/                 # layout.tsx, page.tsx, globals.css
    └── src/
        ├── components/      # UI (quant, mtf, controls, workspace, …)
        ├── engines/         # Client decision fusion
        ├── state/stores/    # Zustand
        ├── lib/             # api.ts, colors, chart helpers
        └── types/           # TypeScript domain types
```

**Not included today:** root README, Docker, `pyproject.toml`.

---

## 3. How to run locally

### Backend (port 8000)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional; defaults work with yahoo/mock
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Verify: `curl http://127.0.0.1:8000/health`

For offline/fast tests: `MARKET_DATA_PROVIDER=mock` in `.env`.

### Frontend (port 3000)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open **http://localhost:3000** — requires backend on **8000**.

### Optional: data pipeline & notebooks

```bash
cd backend
pip install -r requirements-data.txt -r requirements-research.txt
python run_data_pipeline.py --symbol "GC=F" --interval 1d --period 2y
# See backend/notebooks/README.md
```

### Tests

```bash
cd backend && pytest
```

---

## 4. Environment variables

### Backend (`backend/.env.example` → `backend/.env`)

| Variable | Notes |
|----------|-------|
| `MARKET_DATA_PROVIDER` | `yahoo` \| `mock` \| `databento` (stub) |
| `REDIS_URL` | Empty → disk cache under `CACHE_DIR` |
| `CACHE_DIR` | `.cache` |
| `CACHE_ENABLED` | `true` |
| `CACHE_TTL_RAW` / `FEATURE` / `REGIME` | 300 / 600 / 900 |
| `PROVIDER_TIMEOUT` | `20` |
| `LOG_LEVEL` | `INFO` |
| `LOG_JSON` | `true` |
| `FEATURE_VERSION` | `v1` (cache invalidation) |

### Frontend (`frontend/.env.example` → `frontend/.env.local`)

| Variable | Default |
|----------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` |

---

## 5. Backend architecture

### Request flow

```
HTTP (main.py)
  → MarketIntelligenceService (pipeline/service.py)
    → MarketDataAccess (data/access.py)     # provider, cache, validation
    → run_pipeline (pipeline/market_pipeline.py)
      → indicators → ADX/HMM → GARCH → market_state → signal
      → regime_transition → chart bars
    → correlation overlay (on 1D responses)
  → Pydantic MarketPayload validation → JSON
```

### HTTP API (`backend/main.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Status, provider, timeframes, ranges |
| GET | `/metrics` | Prometheus latency metrics |
| GET | `/assets` | Asset registry metadata |
| GET | `/market` | Default 1D market payload |
| GET | `/market/timeframe/{tf}` | Per-timeframe payload (`?symbol=&range=`) |
| GET | `/correlation` | Standalone cross-asset correlation |
| GET | `/validation/{tf}` | Walk-forward validation report |
| POST | `/admin/cache/invalidate` | Clear regime cache |

### Tradable universe (`backend/assets/registry.py`)

| asset_id | provider_symbol | class |
|----------|-----------------|-------|
| BTC | BTC-USD | crypto |
| GOLD | GC=F | future |
| ES | ES=F | future |
| NQ | NQ=F | future |
| DXY | DX-Y.NYB | index |

### Timeframes & ranges (`backend/assets/timeframes.py`)

- **Timeframes:** `1m`, `5m`, `15m`, `1H`, `4H`, `1D` (some resampled from 1h)
- **Ranges:** `1D`, `1W`, `1M`, `3M`, `6M`, `1Y`, `2Y`

### Core engines (`backend/engines/`)

| Engine | Role |
|--------|------|
| `hmm_regime_engine.py` | 3-state Gaussian HMM: MEAN_REVERT / TRENDING / CRISIS |
| `adx_engine.py` | Trend strength, direction, DI |
| `garch_engine.py` | Volatility regime |
| `market_state_engine.py` | Fuses ADX + GARCH + HMM + risk |
| `signal_engine.py` | Score → STRONG BUY / BUY / NEUTRAL / SELL / AVOID |
| `correlation_engine.py` | Rolling corr, BTC betas, covariance instability, regime shifts |

### API contract (`backend/schemas/market.py`)

Top-level **`MarketPayload`** (strict `extra="forbid"`):

- `symbol`, `asset_id`, `timeframe`, `feature_version`
- `price`, `trend`, `regime`, `signal`, `volatility`, `garch_vol`, `vol_regime`, `hmm_regime`
- `market_state` — regime, vol regime, ADX, risk_state, direction, confidence, etc.
- `chart_data[]` — OHLCV + EMAs + per-bar `hmm_regime`, `crisis_probability`, `adx`, etc.
- `regime_transition` — Markov matrix, persistence, instability
- `correlation` — cross-asset intelligence (embedded on 1D responses)

### Research stacks (backend only; not all exposed in UI)

| Package | Role |
|---------|------|
| `alpha_engine/` | Momentum, mean reversion, signal combination |
| `portfolio_engine/` | Allocation, HRP, mean-variance |
| `risk_engine/` | VaR, drawdown, stress, governance |
| `backtesting/` | Event-driven sim, purged CV, deflated Sharpe |
| `execution_engine/` | Routing, slippage, quality metrics |

### WebSocket

**No live WebSocket in `main.py` today.** `risk_engine/realtime/` is preparatory. Frontend has `lib/ws.ts` but it is **not wired**.

---

## 6. Frontend architecture

### Stack

| Package | Version (approx.) |
|---------|-------------------|
| next | 16.2.6 |
| react | 19.2.4 |
| typescript | 5.x |
| tailwindcss | 4 |
| zustand | 5 |
| zod | 4 |
| lightweight-charts | 5 |

### Single page (`frontend/app/page.tsx`)

One route `/` — workspaces are in-app tabs, not separate routes.

**Layout stack (top → bottom):**

1. `TopBar` — brand, price, TF/RNG display, regime/vol/signal, PnL/WS status
2. `MarketIntelligenceStrip` — regime, crisis %, risk
3. `WorkspaceNav` — 7 workspaces (Alt+1–7)
4. **Chart workspace:**
   - `MarketControlLayer` — ASSET / TF / RANGE institutional controls
   - `PrimaryDecisionLayer` — Level-1 fused decision tiles
   - `MainChart` + `RegimeTimeline` | `MTFRegimeMatrix`
   - `AnalyticsLayer` (L2) → `ResearchLayer` (L3)

### State (Zustand)

| Store | File | Role |
|-------|------|------|
| `useMarketStore` | `state/stores/useMarketStore.ts` | Active `MarketPayload`, workspace, loading, WS fields |
| `useTimeframeStore` | `state/stores/useTimeframeStore.ts` | MTF cache (`tf\|range` keys), alignment, regimes |
| `useRiskStore` | `state/stores/useRiskStore.ts` | **Simulated** risk metrics |
| `usePortfolioStore` | `state/stores/usePortfolioStore.ts` | **Simulated** positions/PnL |
| `useExecutionStore` | `state/stores/useExecutionStore.ts` | **Simulated** execution events |
| `useAlphaStore` | `state/stores/useAlphaStore.ts` | Alpha diagnostics state |
| `useDisclosureStore` | `state/stores/useDisclosureStore.ts` | Panel expand/collapse |

### API client (`frontend/src/lib/api.ts`)

- `fetchMarketTimeframe(tf, symbol, range?)` → `GET /market/timeframe/{tf}`
- `fetchAssets()` → `GET /assets`
- Zod `MarketPayloadSchema` mirrors backend Pydantic (warns on drift in console)

### Client engines (`frontend/src/engines/`)

**`decisionEngine.ts`** composes:

| Engine | File | Input |
|--------|------|-------|
| Probability | `probability/probabilityEngine.ts` | HMM probs, calibration |
| Regime | `regime/regimeEngine.ts` | Micro/macro decomposition |
| Uncertainty | `uncertainty/uncertaintyEngine.ts` | Model uncertainty score |
| Correlation | `correlation/correlationEngine.ts` | `market.correlation` |
| Transition | `transition/transitionEngine.ts` | `regime_transition` payload |
| Risk | `risk/riskEngine.ts` | Tail risk, vol state |
| Execution | `execution/executionEngine.ts` | Execution risk |

Hook: `hooks/useDecision.ts` → `computeDecisionState(market, alignment)` → `DecisionState`.

### UI component map

```
frontend/src/components/
├── controls/          MarketControlLayer, AssetSelector, TimeframeSelector, RangeSelector
│                      ControlGroup, SegmentedControl, system context tints
├── quant/             MainChart, TopBar, RegimePanel, RegimeTimeline, heatmaps
├── mtf/               MTFRegimeMatrix, MTFAlignmentOverlay, selector re-exports
├── primary/           PrimaryDecisionLayer
├── analytics/         AnalyticsLayer, CalibratedProbBar
├── research/          ResearchLayer
├── workspace/         RiskCommandCenter, MarketOverview, ExecutionMonitor, …
└── ui/                Panel primitives, Collapsible

frontend/src/visualization/intelligence/MarketIntelligenceStrip.tsx
frontend/src/intelligence/transitions/, interpreters/
```

### Design system

| File | Role |
|------|------|
| `lib/colors.ts` | Terminal palette (`C.t1`, `C.cyan`, regime colors) |
| `lib/tokens.ts` | Typography `T`, chrome heights `CHROME`, spacing `SP` |
| `app/globals.css` | Dark theme, scrollbar, control-layer styles |
| Fonts | IBM Plex Mono/Sans, Geist |

### Workspaces (`WorkspaceId`)

| ID | Component | Data source |
|----|-----------|-------------|
| `chart` | Main terminal | **Live API** |
| `risk` | RiskCommandCenter | Simulated store |
| `market` | MarketOverview | Simulated |
| `execution` | ExecutionMonitor | Simulated |
| `alpha` | AlphaDiagnostics | Simulated |
| `portfolio` | PortfolioAnalytics | Simulated |
| `terminal` | LiveTerminal | Simulated |

---

## 7. Data flow (end-to-end)

```
User selects ASSET / TF / RANGE (MarketControlLayer)
  → useTimeframeStore.setActiveAsset / setActiveRange / setActiveTimeframe
  → fetchMarketTimeframe() → backend pipeline
  → MarketPayload returned
  → useMarketStore.setMarket + useTimeframeStore.setTimeframeData
  → Prefetch other timeframes into MTF cache
  → computeAlignment() + per-TF regimes
  → useDecision(market) → computeDecisionState()
  → PrimaryDecisionLayer + chart overlays update
```

**MTF alignment** (`useTimeframeStore`): compares regimes across timeframes → `ALIGNED` | `PARTIAL` | `CONFLICT`, HTF/LTF divergence flags.

**System context on controls:** crisis / uncertainty / alignment subtly tint `MarketControlLayer` via `useControlContext`.

---

## 8. Frontend source file index

```
frontend/app/
  layout.tsx, page.tsx, globals.css

frontend/src/
  types/market.ts
  lib/api.ts, colors.ts, tokens.ts, format.ts, ws.ts
  lib/assets/registry.ts
  lib/chart/sanitizeBars.ts, buildSeriesData.ts
  hooks/useDecision.ts
  state/stores/
    useMarketStore.ts, useTimeframeStore.ts, useRiskStore.ts,
    usePortfolioStore.ts, useExecutionStore.ts, useAlphaStore.ts, useDisclosureStore.ts
  engines/
    decisionEngine.ts, types.ts
    probability/, regime/, uncertainty/, correlation/, transition/, risk/, execution/
  components/
    controls/     (MarketControlLayer, selectors, SegmentedControl, …)
    quant/        (MainChart, TopBar, RegimePanel, …)
    mtf/          (MTFRegimeMatrix, MTFAlignmentOverlay, re-exports)
    primary/, analytics/, research/, workspace/, ui/
    CandlestickChart.tsx, PriceChart.tsx
```

---

## 9. Backend source file index

```
backend/
  main.py
  run_data_pipeline.py
  requirements.txt, requirements-data.txt, requirements-research.txt
  assets/registry.py, timeframes.py, sessions.py
  schemas/market.py
  pipeline/service.py, market_pipeline.py, context.py
  data/access.py, providers/yahoo_provider.py, mock_provider.py
  engines/              (hmm, adx, garch, signal, correlation, market_state, …)
  features/             (indicators, regimes, volatility)
  regime/transition_matrix.py
  cache/, core/, validation/, ingestion/, storage/, models/
  alpha_engine/, portfolio_engine/, risk_engine/, backtesting/, execution_engine/
  research/, statistical_testing/, feature_analysis/, experiments/
  tests/
  notebooks/
```

### Key files quick reference

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app & routes |
| `backend/pipeline/service.py` | Orchestration + regime cache |
| `backend/pipeline/market_pipeline.py` | Deterministic compute pipeline |
| `backend/data/access.py` | Provider-agnostic OHLCV DAL |
| `backend/assets/registry.py` | Tradable universe |
| `backend/schemas/market.py` | API contract |
| `frontend/app/page.tsx` | Terminal shell & workspace routing |
| `frontend/src/lib/api.ts` | HTTP + Zod validation |
| `frontend/src/state/stores/useTimeframeStore.ts` | MTF state machine |
| `frontend/src/engines/decisionEngine.ts` | Client decision fusion |
| `backend/tests/test_contract_api.py` | API contract regression tests |

---

## 10. Tech stack versions

### Backend (`requirements.txt` highlights)

| Package | Version |
|---------|---------|
| fastapi | 0.136.3 |
| uvicorn | 0.48.0 |
| pydantic | 2.13.4 |
| pandas | 3.0.3 |
| numpy | 2.4.6 |
| hmmlearn | 0.3.3 |
| arch | 8.0.0 |
| scikit-learn | 1.8.0 |
| yfinance | 1.4.0 |

### Frontend (`package.json`)

See `frontend/package.json` for pinned versions.

---

## 11. Market control layer (recent)

Refactored ASSET / TF / RANGE into `frontend/src/components/controls/`:

- **`MarketControlLayer`** — unified shell + crisis/alignment/uncertainty tints
- **Tiered hierarchy** — primary asset (36px) → secondary TF (32px) → tertiary range (30px)
- **Asset groups** — CRYPTO | MACRO | IDX with micro-labels and dividers
- **`SegmentedControl`** — active underline + glow, fast transitions
- **`page.tsx`** uses `<MarketControlLayer decision={decision} />`

Asset display groups are defined in `frontend/src/lib/assets/registry.ts` as `ASSET_DISPLAY_GROUPS`.

---

## 12. Gaps & caveats

- No monorepo README or Docker compose (this doc fills part of that gap)
- WebSocket client exists but is **not connected** end-to-end
- Risk / portfolio / execution workspaces use **mock Zustand data**, not live API
- `/correlation` and `/validation` exist on backend but are not called from `lib/api.ts` (correlation is embedded in 1D `MarketPayload`)
- Databento provider is a stub in `data/providers/`
- Legacy `regime_engine.py` demo routes are not mounted on `main.py`

---

## 13. Sharing full source with an AI assistant

The repo is too large to paste in one message. Options:

1. **Clone the repo** and attach folders in the chat tool.
2. **Zip source** (exclude build artifacts):
   ```bash
   cd quant-dashboard
   zip -r quant-src.zip backend frontend docs \
     -x "*/node_modules/*" "*/.next/*" "*/.venv/*" "*/__pycache__/*"
   ```
3. **Paste specific files** for the task at hand (see key files table above).
4. **Sample API response:**
   ```bash
   curl "http://127.0.0.1:8000/market/timeframe/1D?symbol=BTC-USD&range=3M"
   ```

### Suggested prompt for ChatGPT / other assistants

> You are helping me on **quant-dashboard**, an institutional quant terminal (FastAPI backend + Next.js frontend). Read `docs/PROJECT_BRIEF.md` in the repo. The backend computes market intelligence (HMM regimes, ADX, GARCH, signals, correlation) and returns `MarketPayload`. The frontend MTF-caches timeframes, fuses a client `DecisionState`, and renders a dense terminal UI. Ask me for specific files or assume I can paste them. Do not assume retail/crypto UI patterns — target Bloomberg-terminal density.

---

*Last updated: reflects `feature/correlation-engine` branch including institutional market control layer.*
