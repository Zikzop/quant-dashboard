# Dashboard Validation Report — Institutional Audit Mode

**Audit date:** 2026-05-25  
**Auditor role:** Quantitative systems auditor (read-only)  
**Scope:** Full dashboard UI + `GET /market` + `GET /correlation` + all engines in `backend/engines/`  
**Method:** Source-code trace from displayed label → frontend binding → API field → engine function → stated formula. No architecture changes performed.

**Classification tags used (only):** `REAL_ENGINE_DRIVEN` | `HEURISTIC` | `PLACEHOLDER` | `COSMETIC_ONLY` | `STATISTICALLY_INVALID` | `NEEDS_CALIBRATION`

---

## Executive Summary

| Category | Count (approx.) | Severity |
|----------|-----------------|----------|
| REAL_ENGINE_DRIVEN | ~35 metrics | Core price/EMA/GARCH/ADX/corr math is real but often mis-labeled or mis-scaled |
| HEURISTIC | ~28 metrics | Rule-based labels and scores dominate “intelligence” |
| PLACEHOLDER | ~7 metrics | Risk panel + intelligence feed + dead transition matrix |
| COSMETIC_ONLY | ~12 UI elements | Timeline, styling thresholds, static copy |
| STATISTICALLY_INVALID | ~8 metrics | Per-bar chart intelligence broadcast, HMM in-sample misuse, broken transition_risk gate |
| NEEDS_CALIBRATION | ~10 metrics | HMM posteriors, bull_probability, ADX/GARCH/vol thresholds, correlation instability cutoffs |

**Critical finding:** The terminal *looks* fully backend-driven, but several panels still show **undefined**, **hardcoded**, or **syntactically invalid** backend bindings. Chart `chart_data` repeats **latest-only** engine outputs across all 30 bars, which invalidates historical regime overlays and transition markers.

---

## Master Metric Registry

Columns: **Component** | **Label** | **API field** | **Engine** | **Formula (as implemented)** | **Backend-driven** | **Tag**

### TopBar

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| TopBar | BTC price | `price` | `main.py` | `close.iloc[-1]` from yfinance BTC-USD | Yes | REAL_ENGINE_DRIVEN |
| TopBar | Trend | `trend` | `main.py` | BULLISH if price>EMA20>EMA50; BEARISH if price<EMA20<EMA50; else RANGING | Yes | HEURISTIC |
| TopBar | Volatility | `volatility` | `main.py` | `returns.std() * sqrt(252) * 100` (annualized realized vol, %) | Yes | REAL_ENGINE_DRIVEN |
| TopBar | Signal | `signal` | `signal_engine` | Score from weighted rules; buckets at ±25/±60 | Yes | HEURISTIC |
| TopBar | Title copy | — | — | Static React strings | No | COSMETIC_ONLY |

### MarketIntelligenceStrip

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| Strip | Regime | `market_state.market_regime` | `market_state_engine` | `hmm_data["regime_label"].upper()` | Yes | HEURISTIC |
| Strip | Strength | `market_state.trend_strength` | `adx_engine` | ADX strength enum from fixed ADX thresholds (20/25/40/60) | Yes | HEURISTIC |
| Strip | Direction | `market_state.direction` | `adx_engine` | BULLISH/BEARISH/NEUTRAL from ±DI spread vs `di_neutral_band` | Yes | HEURISTIC |
| Strip | ADX | `market_state.adx` | `adx_engine` | Wilder ADX(14) on OHLC | Yes | REAL_ENGINE_DRIVEN |
| Strip | +DI | `market_state.plus_di` | `adx_engine` | Wilder +DI(14) | Yes | REAL_ENGINE_DRIVEN |
| Strip | −DI | `market_state.minus_di` | `adx_engine` | Wilder −DI(14) | Yes | REAL_ENGINE_DRIVEN |

### MainChart — Price & Structure

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| MainChart | Candles OHLC | `chart_data[].open/high/low/close` | yfinance + `main.py` | Raw daily OHLC | Yes | REAL_ENGINE_DRIVEN |
| MainChart | EMA 20 | `chart_data[].ema20` | `main.py` | `close.ewm(span=20).mean()` per bar | Yes | REAL_ENGINE_DRIVEN |
| MainChart | EMA 50 | `chart_data[].ema50` | `main.py` | `close.ewm(span=50).mean()` per bar | Yes | REAL_ENGINE_DRIVEN |
| MainChart | Header symbol | `symbol` (fallback hardcoded) | `main.py` | `BTC-USD` fixed in endpoint | Partial | HEURISTIC |
| MainChart | PERPETUAL tag | — | — | Static label | No | COSMETIC_ONLY |
| MainChart | ADX-14 · GARCH · HMM-3S | — | — | Static legend text | No | COSMETIC_ONLY |

### MainChart — Regime Intelligence Overlay (left)

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| Overlay | Primary strength headline | `market_state.trend_strength` | `adx_engine` | Mapped in UI: CHOPPY→"RANGING" | Yes | HEURISTIC + COSMETIC_ONLY (label map) |
| Overlay | Sub regime | `market_state.market_regime` | `market_state_engine` | HMM label uppercased | Yes | HEURISTIC |
| Overlay | REGIME | `market_state.market_regime` | same | same | Yes | HEURISTIC |
| Overlay | TREND STR. | `market_state.trend_strength` | `adx_engine` | Threshold buckets | Yes | HEURISTIC |
| Overlay | DIRECTION | `market_state.direction` | `adx_engine` | DI spread rules | Yes | HEURISTIC |
| Overlay | ADX | `market_state.adx` | `adx_engine` | Wilder ADX | Yes | REAL_ENGINE_DRIVEN |
| Overlay | +DI / −DI | `market_state.plus_di/minus_di` | `adx_engine` | Wilder DI | Yes | REAL_ENGINE_DRIVEN |
| Overlay | DI SPREAD | derived | `adx_engine` | `plus_di - minus_di` in frontend | Yes | REAL_ENGINE_DRIVEN |
| Overlay | MEAN-REVERT bar | `mean_revert_probability` | `hmm_regime_engine` | `predict_proba[-1][mean_revert_state]*100` | Yes | NEEDS_CALIBRATION |
| Overlay | TRENDING bar | `trend_probability` | `hmm_regime_engine` | `predict_proba[-1][trending_state]*100` | Yes | NEEDS_CALIBRATION |
| Overlay | CRISIS bar | `crisis_probability` | `hmm_regime_engine` | `predict_proba[-1][crisis_state]*100` | Yes | NEEDS_CALIBRATION |
| Overlay | RegimeDot pulse | `market_state.trend_strength` | frontend rule | Pulse if TRENDING/STRONG/EXTREME | Partial | COSMETIC_ONLY |
| Overlay | Regime colors | `market_state.market_regime` | frontend `regimeColor()` | String substring color map | Partial | COSMETIC_ONLY |

### MainChart — Volatility Overlay (right)

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| Vol overlay | Headline vol regime | `market_state.volatility_regime` | `market_state_engine` | if garch_vol<0.01 COMPRESSED elif <0.025 NORMAL else EXPANDING | Yes | HEURISTIC + STATISTICALLY_INVALID (scale mismatch; see risks) |
| Vol overlay | σ (GARCH) display | `market_state.volatility` | `market_state_engine` | `garch_vol * 100` rounded (%) label on GARCH conditional vol | Yes | STATISTICALLY_INVALID (mislabeled units) |
| Vol overlay | TRANS. RISK | `market_state.transition_risk` | `market_state_engine` | ELEVATED if `regime=="volatile"` and adx<20 else LOW | Yes | HEURISTIC + STATISTICALLY_INVALID (regime string never matches HMM labels) |
| Vol overlay | PERSISTENCE | `market_state.trend_persistence` | `market_state_engine` | WEAK/MODERATE/STRONG from ADX 20/35 cutoffs | Yes | HEURISTIC |
| Vol overlay | RISK STATE | `market_state.risk_state` | `signal_engine` | Same as `signal` string | Yes | HEURISTIC |
| Vol overlay | CONFIDENCE | `market_state.confidence` | `market_state_engine` | `(min(adx/50,1)+min(volatility*20,1))/2` where volatility is raw garch_vol | Yes | HEURISTIC |
| Vol overlay | Confidence color | frontend | thresholds 0.75/0.5 | UI-only | Partial | COSMETIC_ONLY |

### MainChart — Series derived from `chart_data`

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| Chart | GARCH vol histogram | `chart_data[].garch_vol` | `garch_engine` | **Same latest** `garch_vol` copied to every bar in loop | Yes | STATISTICALLY_INVALID |
| Chart | HMM area overlays | `chart_data[].hmm_regime` | `hmm_regime_engine` | **Same latest** label on all 30 bars | Yes | STATISTICALLY_INVALID |
| Chart | Transition spikes | `chart_data` direction/hmm | frontend | Fires on bar-to-bar change; constant fields → no HMM transitions | Partial | STATISTICALLY_INVALID |
| Chart | Regime markers | `chart_data[].direction` | `adx_engine` (broadcast) | **Same latest** direction on all bars | Yes | STATISTICALLY_INVALID |

### ProbabilityPanel

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| ProbabilityPanel | Bull Probability | `bull_probability` | `signal_engine` | `clamp(50 + signal_score*0.5, 1, 99)` — not a probability model | Yes | HEURISTIC + STATISTICALLY_INVALID |
| ProbabilityPanel | Trend Probability | `trend_probability` | `hmm_regime_engine` | HMM filter posterior ×100 | Yes | NEEDS_CALIBRATION |
| ProbabilityPanel | Crisis Probability | `crisis_probability` | `hmm_regime_engine` | HMM filter posterior ×100 | Yes | NEEDS_CALIBRATION |

**Note:** `mean_revert_probability` exists in API but is **not** shown in this panel.

### RiskPanel

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| RiskPanel | VaR 95% | `var_95` | **None** | Field absent from `/market` → renders `undefined` | No | PLACEHOLDER |
| RiskPanel | Expected Shortfall | `expected_shortfall` | **None** | Absent | No | PLACEHOLDER |
| RiskPanel | Max Drawdown | `max_drawdown` | **None** | Absent | No | PLACEHOLDER |
| RiskPanel | Risk Regime | `risk_regime` | **None** | API has `signal` and `market_state.risk_state`, not `risk_regime` | No | PLACEHOLDER |

### RegimePanel

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| RegimePanel | Market Regime | `regime` | `hmm_regime_engine` | `regime_label` (MEAN_REVERT/TRENDING/CRISIS) | Yes | HEURISTIC |
| RegimePanel | HMM Regime | `hmm_regime` | `hmm_regime_engine` | Duplicate of above | Yes | HEURISTIC |
| RegimePanel | Volatility Regime | `vol_regime` | `garch_engine` | EXPANDING_VOL if 5-day vol slope > 0 else CONTRACTING_VOL | Yes | HEURISTIC |

### StructurePanel

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| StructurePanel | Trend | `trend` | `main.py` | EMA stack rule | Yes | HEURISTIC |
| StructurePanel | Momentum | `momentum` | `main.py` | `(price/close[-20]-1)*100` | Yes | REAL_ENGINE_DRIVEN |
| StructurePanel | Signal Score | `signal_score` | `signal_engine` | Linear combo of trend/momentum/HMM/GARCH rules | Yes | HEURISTIC |
| StructurePanel | Confidence | `confidence` | `signal_engine` | `clamp(abs(signal_score), 5, 95)` — **not** `market_state.confidence` | Yes | HEURISTIC |

### VolatilityPanel

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| VolatilityPanel | Realized Volatility | `volatility` | `main.py` | Annualized realized vol % | Yes | REAL_ENGINE_DRIVEN |
| VolatilityPanel | GARCH Volatility | `garch_vol` | `garch_engine` | GARCH(1,1) conditional σ on `100*log returns` | Yes | REAL_ENGINE_DRIVEN |
| VolatilityPanel | Volatility Regime | `vol_regime` | `garch_engine` | Sign of 5-day change in conditional vol | Yes | HEURISTIC |
| VolatilityPanel | Volatility Slope | `vol_slope` | `garch_engine` | `cond_vol[-1] - cond_vol[-5]` | Yes | REAL_ENGINE_DRIVEN |

### CrossAssetHeatmap / HeatmapPanel

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| Heatmap | Correlation matrix cells | `correlation.matrix_values` | `correlation_engine` | Rolling 60d Pearson ρ on log returns | Yes | REAL_ENGINE_DRIVEN |
| Heatmap | Cell background color | `correlation.zscore_matrix_values` | frontend | Thresholds ±0.5, ±1.5 on z-score | Partial | COSMETIC_ONLY |
| Heatmap | Cov Instability | `correlation.covariance_instability` | `correlation_engine` | ‖Cov_recent−Cov_prior‖_F / ‖Cov_prior‖_F; labels at 0.18/0.35 | Yes | REAL_ENGINE_DRIVEN + HEURISTIC (thresholds) |
| Heatmap | Regime Shift | `correlation.regime_correlation_shift.sensitivity` | `correlation_engine` | Mean abs(ρ_short−ρ_long); HIGH if HMM label in {CRISIS,MEAN_REVERT} and magnitude≥0.12 | Yes | HEURISTIC |
| Heatmap | HMM Regime (shift header) | `correlation.regime_correlation_shift.current_regime` | passed from HMM | Label only, not used in ρ estimation | Yes | HEURISTIC |
| Heatmap | Asset daily return | `correlation.heatmap_cells[].daily_return_pct` | `correlation_engine` | Last log return ×100 per asset | Yes | REAL_ENGINE_DRIVEN |
| Heatmap | β BTC | `correlation.heatmap_cells[].beta_vs_btc` | `correlation_engine` | `Cov(r_i,r_BTC)/Var(r_BTC)` rolling 60d | Yes | REAL_ENGINE_DRIVEN |
| Heatmap | ρz BTC | `correlation.heatmap_cells[].correlation_zscore_vs_btc` | `correlation_engine` | z-score of rolling ρ vs 252d history | Yes | NEEDS_CALIBRATION |
| Heatmap | Pair shift list | `correlation.regime_correlation_shift.largest_shifts` | `correlation_engine` | Top \|ρ_20d−ρ_60d\| pairs | Yes | HEURISTIC (not true regime-conditional) |

### RegimeTimeline

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| RegimeTimeline | TREND / VOLATILE / CRISIS / RECOVERY / CHOP | **Ignored** (`market` prop unused) | frontend array | Static 5-column decorative strip | No | COSMETIC_ONLY |

### MarketFeed (Intelligence Feed)

| Component | Label | API field | Engine | Formula | Backend-driven | Tag |
|-----------|-------|-----------|--------|---------|----------------|-----|
| MarketFeed | All headlines + impact | **None** | frontend `news[]` | Hardcoded strings | No | PLACEHOLDER |

**Dead code note:** `interpretMarketState()` in `marketStateInterpreter.ts` could generate alerts from `market_state` but is **not wired** to MarketFeed.

### Unused frontend modules (not displayed)

| Path | Content | Tag |
|------|---------|-----|
| `intelligence/transitions/regimeTransitionMatrix.ts` | Static transition probabilities (0.42, 0.17, 0.63) | PLACEHOLDER |
| `state/stores/useMarketStore.ts` | Store not used by `page.tsx` | PLACEHOLDER |

---

# VALIDATED METRICS

Metrics where the **numeric computation matches a standard definition** and is **bound to live backend data** without fabrication:

1. **BTC OHLC, EMA20, EMA50** — yfinance + pandas (`main.py`).
2. **Realized volatility (TopBar, VolatilityPanel)** — `std(returns)*sqrt(252)*100`.
3. **Momentum** — 20-day price return %.
4. **GARCH(1,1) conditional volatility & vol_slope** — `arch` package on scaled log returns (`garch_engine.py`).
5. **ADX, +DI, −DI** — Wilder smoothing pipeline (`adx_engine.py`), latest bar via `compute_latest`.
6. **DI spread** — arithmetic difference (overlay).
7. **Rolling correlation matrix** — 60-day Pearson on aligned log returns (`correlation_engine.py`).
8. **Rolling beta vs BTC** — `Cov/Var` rolling 60d.
9. **Cross-asset daily return %** — last log return per asset.
10. **Covariance instability score** — Frobenius norm ratio (formula real; regime labels heuristic).

---

# HEURISTIC METRICS

Rule-based or score-based outputs **not derived from a formal statistical model** (thresholds documented in code):

| Metric | Location | Rule summary |
|--------|----------|----------------|
| Trend (BULLISH/BEARISH/RANGING) | `main.py` | EMA20/EMA50/price ordering |
| Structure regime | `main.py` | VOLATILE if GARCH expanding; TRENDING_BULL/BEAR if trend + momentum ±5% |
| Signal / signal_score | `signal_engine.py` | ±25 trend, vol-adjusted momentum, HMM % × 0.3/0.4, GARCH expansion ±10 |
| Signal labels (BUY/SELL/AVOID…) | `signal_engine.py` | Score cutoffs ±25, ±60 |
| Bull probability | `signal_engine.py` | `50 + 0.5*signal_score` |
| Signal confidence | `signal_engine.py` | `abs(signal_score)` clamped to [5,95] |
| ADX strength / direction labels | `adx_engine.py` | Fixed ADX/DI thresholds |
| GARCH vol_regime (EXPANDING/CONTRACTING) | `garch_engine.py` | Sign of 5-day vol change |
| HMM regime_label | `hmm_regime_engine.py` | Post-hoc state sorting by mean realized vol |
| market_state persistence | `market_state_engine.py` | ADX <20 / <35 |
| market_state volatility_regime | `market_state_engine.py` | garch_vol vs 0.01, 0.025 |
| market_state transition_risk | `market_state_engine.py` | Broken string compare to `"volatile"` |
| market_state confidence | `market_state_engine.py` | ADX and garch_vol linear caps |
| Correlation instability regime | `correlation_engine.py` | score ≥0.18 / ≥0.35 |
| Correlation shift sensitivity | `correlation_engine.py` | magnitude + HMM label gate |
| Frontend strengthLabel map | `MainChart.tsx` | CHOPPY→"RANGING" display |
| Frontend overlay color thresholds | `MainChart.tsx`, `CrossAssetHeatmap.tsx` | Hardcoded color breakpoints |

---

# FAKE / PLACEHOLDER METRICS

| Item | Evidence |
|------|----------|
| RiskPanel VaR / ES / MaxDD | API fields never populated |
| RiskPanel Risk Regime | Expects `risk_regime`; API uses `signal` / `market_state.risk_state` |
| MarketFeed all items | Hardcoded `news[]` in `MarketFeed.tsx` |
| RegimeTimeline states | Static array; `market` prop ignored |
| `regimeTransitionMatrix.ts` | Static probabilities, unused in UI |
| `useMarketStore` | Not connected to dashboard fetch path |

---

# CALIBRATION REQUIRED

| Metric | Why |
|--------|-----|
| HMM trend/crisis/mean-revert probabilities | In-sample `predict_proba` after full-sample refit each request; no walk-forward, no calibration to realized outcomes |
| Bull probability | Affine transform of signal score; not a calibrated P(bull) |
| ADX regime thresholds | Documented as non-default institutional cutoffs but not empirically fitted to BTC |
| market_state garch vol thresholds (0.01, 0.025) | Applied to wrong scale (GARCH σ on 100× log returns) |
| Correlation ρ z-scores | Assumes stationary correlation distribution over 252d |
| Correlation instability cutoffs (0.18, 0.35) | Arbitrary |
| HMM → correlation “regime-sensitive” sensitivity | Uses global short/long windows, not regime-conditioned sample |

---

# ARCHITECTURAL RISKS

1. **Single-symbol endpoint** — `/market` hardcodes `BTC-USD`; cross-asset correlation is a second yfinance pass (latency, consistency).
2. **Per-request HMM refit** — `fit()` on full history every API call → non-stationary, non-reproducible intraday if features change.
3. **Dual confidence semantics** — `signal_engine.confidence` (score magnitude) vs `market_state.confidence` (ADX/GARCH blend) shown in different panels without disclosure.
4. **Dual volatility regime semantics** — `garch_data.vol_regime` (slope) vs `market_state.volatility_regime` (level thresholds) vs UI conflation in overlays.
5. **chart_data intelligence broadcast** — Historical chart cannot support true regime archaeology until per-bar engine outputs are computed.
6. **market_state.transition_risk** — Compares HMM label to `"volatile"` (lowercase); HMM returns `MEAN_REVERT`/`TRENDING`/`CRISIS` → branch never triggers.
7. **Interpreter / feed disconnect** — Real alert logic exists in `marketStateInterpreter.ts` but feed uses mock copy.
8. **RegimePanel `regime` vs `structure_regime`** — Panel shows HMM label as “Market Regime”; `structure_regime` from EMA/momentum not surfaced here.

---

# STATISTICAL RISKS

1. **HMM posteriors presented as probabilities** — Filter probabilities ≠ calibrated event probabilities; sum to 100% on latest bar only; mislead if read as forward risk.
2. **In-sample regime labeling** — State-to-label mapping by sorted vol means uses full sample including future bars relative to each t (label assignment uses all hidden states).
3. **GARCH / realized vol scale mix** — Comparing annualized realized % with GARCH conditional vol on 100-scaled returns in overlays/panels without unit harmonization.
4. **Chart transition detection** — With constant `hmm_regime`/`direction`/`adx` on all `chart_data` rows, transition series and markers do not reflect historical regime changes.
5. **Correlation matrix alignment** — `dropna(how="any")` on all assets may shorten sample; mixed macro/crypto vol regimes not adjusted.
6. **β and ρ on 60d window** — Unstable for macro series (TNX, DXY); non-stationary betas not flagged.
7. **Signal engine vol-adjusted momentum** — Divides by annualized vol then ×100; dimensionally ad hoc.

---

# FRONTEND HARDCODE DETECTION

Search targets: `frontend/src/components`, `frontend/src/visualization`, `frontend/src/analytics` (analytics dir **empty / missing**).

| File | Hardcoded / static content | Tag |
|------|---------------------------|-----|
| `MarketFeed.tsx` | `news[]` titles + HIGH/MEDIUM/LOW impact | PLACEHOLDER |
| `RegimeTimeline.tsx` | `regimes = ["TREND","VOLATILE","CRISIS","RECOVERY","CHOP"]` | COSMETIC_ONLY |
| `regimeTransitionMatrix.ts` | probabilities 0.42, 0.17, 0.63 | PLACEHOLDER |
| `MainChart.tsx` | Color palette `C`, pulse rules, `strengthLabel` map, vol/confidence color cutoffs 0.75/0.5 | COSMETIC_ONLY |
| `CrossAssetHeatmap.tsx` | `cellColor()` thresholds ±0.5, ±1.5, ±0.25, ±0.6 | COSMETIC_ONLY |
| `MainChart.tsx` | Default header `BTC / USD` if symbol missing | COSMETIC_ONLY |
| `MainChart.tsx` | `PERPETUAL`, `INSTITUTIONAL ANALYTICS` copy | COSMETIC_ONLY |
| `page.tsx` | Loading string only | COSMETIC_ONLY |
| `TopBar.tsx` | Static titles | COSMETIC_ONLY |

**No hardcoded fake percentages found in:** `HeatmapPanel`, `ProbabilityPanel`, `VolatilityPanel`, `StructurePanel`, `RegimePanel`, `MarketIntelligenceStrip` (all bind to `market` when data present).

**RiskPanel:** Not hardcoded numbers — displays **undefined** backend fields (worse than cosmetic).

---

## Component-Level Verdict

| Component | Backend-driven? | Production-ready quant? | Primary tag |
|-----------|-----------------|-------------------------|-------------|
| MainChart (OHLC/EMA) | Yes | Acceptable for visualization | REAL_ENGINE_DRIVEN |
| MainChart (overlays) | Partial | Latest-bar only; chart history invalid | STATISTICALLY_INVALID |
| Regime overlays | Yes (latest) | Heuristic labels | HEURISTIC |
| Volatility overlays | Yes | Scale/threshold bugs | HEURISTIC + STATISTICALLY_INVALID |
| ProbabilityPanel | Yes | HMM + fake bull % | NEEDS_CALIBRATION |
| RiskPanel | **No** | Empty bindings | PLACEHOLDER |
| Correlation heatmap | Yes | Real math; heuristic labels | REAL_ENGINE_DRIVEN |
| Intelligence feed | **No** | Mock news | PLACEHOLDER |
| Regime timeline | **No** | Decorative | COSMETIC_ONLY |
| Structure analytics | Yes | Heuristic signal | HEURISTIC |
| Volatility analytics | Yes | Real GARCH/realized | REAL_ENGINE_DRIVEN |

---

## Recommended Validation Actions (audit-only; not implemented)

1. Wire RiskPanel to computed VaR/ES/MDD or remove labels.  
2. Replace MarketFeed mock with `interpretMarketState(market.market_state)` or remove panel.  
3. Drive RegimeTimeline from historical `chart_data` or HMM state series.  
4. Fix `market_state_engine` vol threshold units and `transition_risk` regime string.  
5. Compute per-bar ADX/HMM/GARCH in `chart_data` loop.  
6. Rename or document `bull_probability` as **ScoreIndex**, not probability.  
7. Add walk-forward / frozen HMM model artifact for calibrated posteriors.

---

*End of report. No code, architecture, or UI was modified during this audit.*
