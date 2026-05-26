"""
Distribution diagnostics for return series.

Financial returns typically exhibit fat tails, skewness, and non-normality.
Gaussian assumptions should never be applied without verification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

TailLabel = Literal["thin", "normal", "fat", "extreme_fat"]
AsymmetryLabel = Literal["left_skewed", "symmetric", "right_skewed"]
NormalityLabel = Literal["normal", "non_normal", "insufficient_data"]


@dataclass(frozen=True)
class JarqueBeraResult:
    statistic: float
    p_value: float
    rejects_normality: bool
    interpretation: str


@dataclass(frozen=True)
class TailDiagnostics:
    left_tail_ratio: float
    right_tail_ratio: float
    tail_index: float
    tail_assessment: TailLabel
    interpretation: str


@dataclass(frozen=True)
class DistributionDiagnostics:
    n_obs: int
    mean: float
    std: float
    skewness: float
    excess_kurtosis: float
    asymmetry: AsymmetryLabel
    jarque_bera: JarqueBeraResult
    tails: TailDiagnostics
    normality: NormalityLabel
    summary: str
    warnings: tuple[str, ...]


def run_distribution_diagnostics(
    series: pd.Series,
    *,
    significance: float = 0.05,
    tail_threshold: float = 2.0,
) -> DistributionDiagnostics:
    """
    Comprehensive distribution analysis for a return-like series.

    Parameters
    ----------
    series : pd.Series
        Return or log-return series.
    significance : float
        Alpha for Jarque-Bera normality test.
    tail_threshold : float
        Multiple of standard deviation defining tail events.
    """
    clean = pd.Series(series).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    warnings: list[str] = []

    if len(clean) < 8:
        jb = JarqueBeraResult(
            statistic=float("nan"),
            p_value=float("nan"),
            rejects_normality=False,
            interpretation="Insufficient data for Jarque-Bera test.",
        )
        tails = TailDiagnostics(
            left_tail_ratio=float("nan"),
            right_tail_ratio=float("nan"),
            tail_index=float("nan"),
            tail_assessment="normal",
            interpretation="Insufficient data for tail diagnostics.",
        )
        return DistributionDiagnostics(
            n_obs=len(clean),
            mean=float("nan"),
            std=float("nan"),
            skewness=float("nan"),
            excess_kurtosis=float("nan"),
            asymmetry="symmetric",
            jarque_bera=jb,
            tails=tails,
            normality="insufficient_data",
            summary="Insufficient observations for reliable distribution inference.",
            warnings=("Need at least 8 observations.",),
        )

    mean = float(clean.mean())
    std = float(clean.std(ddof=1))
    skew = float(stats.skew(clean, bias=False))
    kurt = float(stats.kurtosis(clean, fisher=True, bias=False))

    asymmetry = _classify_asymmetry(skew)
    jb = _jarque_bera(clean, significance)
    tails = _tail_diagnostics(clean, std, tail_threshold)

    if jb.rejects_normality:
        normality: NormalityLabel = "non_normal"
        logger.warning("Jarque-Bera rejects normality (p=%.4f)", jb.p_value)
    else:
        normality = "normal"
        if tails.tail_assessment in ("fat", "extreme_fat"):
            warnings.append(
                "Jarque-Bera did not reject normality but tail diagnostics suggest fat tails. "
                "Normality tests have low power with small samples."
            )

    if abs(skew) > 1.0:
        warnings.append(f"Strong skewness ({skew:.2f}); symmetric risk models may misprice tails.")

    if kurt > 3.0:
        warnings.append(f"Excess kurtosis ({kurt:.2f}); Gaussian VaR will understate tail risk.")

    summary = (
        f"n={len(clean)}, skew={skew:.3f} ({asymmetry}), "
        f"excess_kurtosis={kurt:.3f}, tails={tails.tail_assessment}, "
        f"normality={normality}."
    )

    return DistributionDiagnostics(
        n_obs=len(clean),
        mean=mean,
        std=std,
        skewness=skew,
        excess_kurtosis=kurt,
        asymmetry=asymmetry,
        jarque_bera=jb,
        tails=tails,
        normality=normality,
        summary=summary,
        warnings=tuple(warnings),
    )


def _classify_asymmetry(skew: float, threshold: float = 0.5) -> AsymmetryLabel:
    if skew < -threshold:
        return "left_skewed"
    if skew > threshold:
        return "right_skewed"
    return "symmetric"


def _jarque_bera(clean: pd.Series, significance: float) -> JarqueBeraResult:
    stat, p_value = stats.jarque_bera(clean)
    rejects = p_value < significance
    if rejects:
        interp = (
            f"Reject normality at {significance:.0%} (JB={stat:.2f}, p={p_value:.4f}). "
            "Returns deviate from Gaussian."
        )
    else:
        interp = (
            f"Fail to reject normality (p={p_value:.4f}). "
            "Does not prove Gaussianity—only insufficient evidence against it."
        )
    return JarqueBeraResult(
        statistic=float(stat),
        p_value=float(p_value),
        rejects_normality=rejects,
        interpretation=interp,
    )


def _tail_diagnostics(clean: pd.Series, std: float, threshold: float) -> TailDiagnostics:
    if std <= 0:
        return TailDiagnostics(
            left_tail_ratio=0.0,
            right_tail_ratio=0.0,
            tail_index=float("nan"),
            tail_assessment="normal",
            interpretation="Zero variance; tail analysis not applicable.",
        )

    z = clean / std
    left = (z < -threshold).mean()
    right = (z > threshold).mean()
    gaussian_tail = 2 * (1 - stats.norm.cdf(threshold))
    observed = left + right
    ratio = observed / gaussian_tail if gaussian_tail > 0 else float("inf")

    if ratio > 2.5:
        assessment: TailLabel = "extreme_fat"
        interp = f"Tail mass {ratio:.1f}x Gaussian at ±{threshold}σ; extreme fat tails."
    elif ratio > 1.5:
        assessment = "fat"
        interp = f"Tail mass {ratio:.1f}x Gaussian; fat tails detected."
    elif ratio < 0.7:
        assessment = "thin"
        interp = f"Tail mass {ratio:.1f}x Gaussian; thinner than normal tails."
    else:
        assessment = "normal"
        interp = f"Tail mass roughly consistent with Gaussian at ±{threshold}σ."

    tail_index = float(ratio)
    return TailDiagnostics(
        left_tail_ratio=float(left),
        right_tail_ratio=float(right),
        tail_index=tail_index,
        tail_assessment=assessment,
        interpretation=interp,
    )
