"""
The deterministic pipeline stages.

Each stage is a function of explicit inputs; ``run_pipeline`` wires them in the
fixed order and assembles the backward-compatible API payload. The HMM/ADX
engines are module-level singletons because they are stateless (no fitted state
is retained between calls), which avoids per-request allocation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.logging import get_logger
from core.metrics import record_regime, record_signal
from engines.adx_engine import ADXRegimeEngine
from engines.hmm_regime_engine import HMMRegimeEngine
from engines.market_state_engine import build_market_state
from engines.signal_engine import calculate_signal_engine
from features.indicators import compute_indicators, structure_regime
from features.regimes import compute_adx, compute_hmm
from features.volatility import compute_garch, realized_volatility
from pipeline.context import PipelineContext, PipelineResult
from regime.transition_matrix import build_transition_model

logger = get_logger("pipeline.market")

_ADX_ENGINE = ADXRegimeEngine()
_HMM_ENGINE = HMMRegimeEngine()


def _bar_time(ts: pd.Timestamp, is_intraday: bool) -> int | str:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    if is_intraday:
        secs = int(t.timestamp())
        if secs <= 0:
            raise ValueError(f"Invalid bar timestamp: {ts!r}")
        return secs
    return t.strftime("%Y-%m-%d")


def _build_chart_data(
    ctx: PipelineContext,
    ema20_series: pd.Series,
    ema50_series: pd.Series,
    adx_series: pd.DataFrame,
    garch_series: pd.DataFrame,
    hmm_history: pd.DataFrame,
) -> list[dict]:
    df = ctx.engine_df
    chart_bars = min(ctx.display_bars, len(df))
    is_intraday = ctx.spec.is_intraday
    out: list[dict] = []

    for ts, row in df.tail(chart_bars).iterrows():
        bar: dict = {
            "time": _bar_time(ts, is_intraday),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "ema20": round(float(ema20_series.loc[ts]), 2),
            "ema50": round(float(ema50_series.loc[ts]), 2),
        }

        if ts in adx_series.index:
            arow = adx_series.loc[ts]
            if not pd.isna(arow.get("adx")):
                bar["adx"] = round(float(arow["adx"]), 2)
                bar["plus_di"] = round(float(arow["plus_di"]), 2)
                bar["minus_di"] = round(float(arow["minus_di"]), 2)
                bar["direction"] = arow["direction"]
                bar["trend_strength"] = arow["trend_strength"]

        if ts in garch_series.index:
            grow = garch_series.loc[ts]
            if not pd.isna(grow.get("garch_vol")):
                bar["garch_vol"] = round(float(grow["garch_vol"]), 4)
                bar["vol_regime"] = str(grow["vol_regime"])

        if not hmm_history.empty and ts in hmm_history.index:
            hrow = hmm_history.loc[ts]
            regime = hrow.get("hmm_regime")
            if regime is not None and not (isinstance(regime, float) and pd.isna(regime)):
                bar["hmm_regime"] = str(regime)
                bar["mean_revert_probability"] = round(float(hrow["mean_revert_probability"]), 4)
                bar["trend_probability"] = round(float(hrow["trend_probability"]), 4)
                bar["crisis_probability"] = round(float(hrow["crisis_probability"]), 4)

        out.append(bar)

    return out


def run_pipeline(ctx: PipelineContext) -> PipelineResult:
    df = ctx.engine_df
    close = df["Close"].astype(float)

    # -- indicators ---------------------------------------------------------
    ind = compute_indicators(df)

    # -- volatility ---------------------------------------------------------
    realized_vol = realized_volatility(close, ctx.spec.bars_per_year)
    garch = compute_garch(close, ctx.timeframe)

    # -- regime inference ---------------------------------------------------
    adx = compute_adx(df, _ADX_ENGINE)
    hmm = compute_hmm(df, _HMM_ENGINE, ctx.timeframe)
    hmm_label = hmm.snapshot.get("regime_label", "UNKNOWN")

    structure = structure_regime(ind.trend, ind.momentum, garch.vol_regime)

    market_state = build_market_state(
        adx_result=adx.latest,
        garch_result={"volatility": garch.garch_vol},
        hmm_result={"regime": hmm_label},
        risk_result={"risk_regime": "PENDING"},
    )

    # -- transition matrix (P1.4) ------------------------------------------
    regime_seq = (
        list(hmm.history["hmm_regime"].dropna().astype(str))
        if not hmm.history.empty and "hmm_regime" in hmm.history.columns
        else []
    )
    transition = build_transition_model(
        regime_seq, current_state=hmm_label if hmm_label != "UNKNOWN" else None
    ).to_payload()

    # -- signal generation --------------------------------------------------
    signal = calculate_signal_engine(
        trend=ind.trend,
        momentum=ind.momentum,
        volatility=realized_vol,
        hmm_data={
            "trend_probability": hmm.snapshot.get("trend_probability", 0.0),
            "crisis_probability": hmm.snapshot.get("crisis_probability", 0.0),
        },
        garch_data={"vol_regime": garch.vol_regime},
    )
    market_state["risk_state"] = signal["signal"]

    # observability: signal frequency + regime distribution drift
    record_signal(signal["signal"])
    record_regime(hmm_label, ctx.timeframe)

    # -- overlays (chart bars) ---------------------------------------------
    chart_data = _build_chart_data(
        ctx,
        ind.ema20_series,
        ind.ema50_series,
        adx.series,
        garch.series,
        hmm.history,
    )

    payload = {
        "symbol": ctx.asset.provider_symbol,
        "asset_id": ctx.asset.asset_id,
        "timeframe": ctx.timeframe,
        "feature_version": ctx.feature_version,
        "price": round(ind.price, 2),
        "trend": ind.trend,
        "market_state": market_state,
        "volatility": round(realized_vol * 100, 2),
        "ema20": round(ind.ema20, 2),
        "ema50": round(ind.ema50, 2),
        "momentum": round(ind.momentum, 2),
        "regime": hmm_label,
        "structure_regime": structure,
        "signal": signal["signal"],
        "signal_score": signal["signal_score"],
        "confidence": signal["confidence"],
        "bull_probability": signal["bull_probability"],
        "garch_vol": garch.garch_vol,
        "vol_regime": garch.vol_regime,
        "vol_slope": garch.vol_slope,
        "hmm_regime": hmm_label,
        "trend_probability": hmm.snapshot.get("trend_probability", 0.0),
        "crisis_probability": hmm.snapshot.get("crisis_probability", 0.0),
        "mean_revert_probability": hmm.snapshot.get("mean_revert_probability", 0.0),
        "regime_transition": transition,
        "chart_data": chart_data,
        "correlation": None,  # populated by the service for 1D
    }

    return PipelineResult(
        payload=payload,
        chart_data=chart_data,
        diagnostics={
            "bars": len(df),
            "chart_bars": len(chart_data),
            "regime_sequence_len": len(regime_seq),
        },
    )
