"""
Probabilistic alpha combiner — regime-aware, confidence-weighted blending.

Avoids naive averaging and majority voting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine.alpha_base import AlphaOutput, AlphaSeriesOutput, RegimeContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProbabilisticCombinerConfig:
    min_confidence: float = 0.1
    disagreement_penalty: float = 0.3
    vol_scale: float = 1.0


@dataclass(frozen=True)
class CombinedAlphaOutput:
    alpha_score: float
    confidence: float
    component_scores: dict[str, float]
    component_weights: dict[str, float]
    disagreement: float
    regime_context: RegimeContext
    timestamp: pd.Timestamp
    summary: str
    warnings: tuple[str, ...]


class ProbabilisticCombiner:
    """
    Combine multiple alpha series via confidence-weighted Bayesian-style fusion.

    Weight_i = confidence_i / (uncertainty_i + disagreement_penalty)
    """

    def __init__(self, config: ProbabilisticCombinerConfig | None = None) -> None:
        self.config = config or ProbabilisticCombinerConfig()

    def combine(
        self,
        alpha_outputs: dict[str, AlphaSeriesOutput],
        *,
        vol_series: pd.Series | None = None,
        feature_stability: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """
        Combine aligned alpha output DataFrames.

        Parameters
        ----------
        alpha_outputs : dict
            alpha_name -> AlphaSeriesOutput
        vol_series : optional
            Realized vol for uncertainty scaling.
        feature_stability : optional
            alpha_name -> stability score in [0,1] from feature_stability module.
        """
        cfg = self.config
        if not alpha_outputs:
            raise ValueError("No alpha outputs to combine")

        names = list(alpha_outputs.keys())
        frames = {n: alpha_outputs[n].outputs for n in names}
        idx = frames[names[0]].index
        for n in names[1:]:
            idx = idx.intersection(frames[n].index)
        if idx.empty:
            raise ValueError("No overlapping timestamps across alphas")

        combined_rows: list[dict] = []
        warnings: list[str] = []
        max_disagreement = 0.0

        for ts in idx:
            scores: dict[str, float] = {}
            confidences: dict[str, float] = {}
            for n in names:
                row = frames[n].loc[ts]
                scores[n] = float(row["alpha_score"])
                confidences[n] = float(row["confidence"])

            stab = feature_stability or {}
            weights: dict[str, float] = {}
            for n in names:
                conf = max(confidences[n], cfg.min_confidence)
                stab_factor = stab.get(n, 1.0)
                vol_unc = 1.0
                if vol_series is not None and ts in vol_series.index:
                    vol_unc = 1.0 + float(vol_series.loc[ts]) * cfg.vol_scale
                weights[n] = conf * stab_factor / vol_unc

            w_sum = sum(weights.values()) or 1.0
            norm_w = {n: weights[n] / w_sum for n in names}

            weighted_score = sum(scores[n] * norm_w[n] for n in names)
            score_values = list(scores.values())
            disagreement = float(np.std(score_values)) if len(score_values) > 1 else 0.0
            max_disagreement = max(max_disagreement, disagreement)
            weighted_score *= 1.0 - cfg.disagreement_penalty * disagreement

            agg_conf = sum(confidences[n] * norm_w[n] for n in names) * (
                1.0 - cfg.disagreement_penalty * disagreement
            )
            agg_conf = float(np.clip(agg_conf, 0, 1))

            ref = frames[names[0]].loc[ts]
            combined_rows.append(
                {
                    "timestamp": ts,
                    "alpha_score": float(np.clip(weighted_score, -1, 1)),
                    "confidence": agg_conf,
                    "disagreement": disagreement,
                    "trend_regime": ref["trend_regime"],
                    "vol_regime": ref["vol_regime"],
                    "regime_confidence": float(ref["regime_confidence"]),
                    **{f"score_{n}": scores[n] for n in names},
                    **{f"weight_{n}": norm_w[n] for n in names},
                }
            )

        if max_disagreement > 0.5:
            warnings.append("High alpha disagreement — composite confidence penalized.")

        result = pd.DataFrame(combined_rows).set_index("timestamp")
        result.attrs["warnings"] = tuple(warnings)
        return result

    def combine_latest(
        self,
        outputs: dict[str, AlphaOutput],
        *,
        feature_stability: dict[str, float] | None = None,
    ) -> CombinedAlphaOutput:
        """Combine latest single-bar AlphaOutput instances."""
        cfg = self.config
        names = list(outputs.keys())
        scores = {n: outputs[n].alpha_score for n in names}
        confidences = {n: outputs[n].confidence for n in names}
        stab = feature_stability or {}

        weights = {}
        for n in names:
            conf = max(confidences[n], cfg.min_confidence)
            weights[n] = conf * stab.get(n, 1.0)
        w_sum = sum(weights.values()) or 1.0
        norm_w = {n: weights[n] / w_sum for n in names}

        disagreement = float(np.std(list(scores.values()))) if len(scores) > 1 else 0.0
        combined = sum(scores[n] * norm_w[n] for n in names)
        combined *= 1.0 - cfg.disagreement_penalty * disagreement
        agg_conf = float(
            np.clip(
                sum(confidences[n] * norm_w[n] for n in names)
                * (1.0 - cfg.disagreement_penalty * disagreement),
                0,
                1,
            )
        )

        ref = outputs[names[0]]
        return CombinedAlphaOutput(
            alpha_score=float(np.clip(combined, -1, 1)),
            confidence=agg_conf,
            component_scores=scores,
            component_weights=norm_w,
            disagreement=disagreement,
            regime_context=ref.regime_context,
            timestamp=ref.timestamp,
            summary=f"Combined {len(names)} alphas disagreement={disagreement:.3f}",
            warnings=(),
        )
