from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple, Union

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler

from engines.feature_engineering import build_hmm_features

# Minimum history before first expanding-window HMM inference
DEFAULT_MIN_TRAIN = 60


def _map_states_by_volatility(
    features: pd.DataFrame,
    hidden_states: np.ndarray,
) -> Tuple[int, int, int]:
    """
    Map HMM state indices to mean-revert / trending / crisis using only
    realized volatility of bars assigned to each state within this window.
    """
    state_volatility = []

    for state in range(3):
        mask = hidden_states == state
        if not np.any(mask):
            state_volatility.append(np.nan)
        else:
            state_volatility.append(
                float(features.loc[mask, "realized_vol"].mean())
            )

    # Unused states sort last; finite vol states ordered low -> high
    order = np.argsort(
        [v if np.isfinite(v) else np.inf for v in state_volatility]
    )

    return int(order[0]), int(order[1]), int(order[2])


def _regime_label_for_state(
    state: int,
    mean_revert_state: int,
    trending_state: int,
    crisis_state: int,
) -> str:
    if state == mean_revert_state:
        return "MEAN_REVERT"
    if state == trending_state:
        return "TRENDING"
    return "CRISIS"


class HMMRegimeEngine:

    def __init__(self, min_train: int = DEFAULT_MIN_TRAIN):

        self.min_train = min_train

    def _infer_at_position(
        self,
        features: pd.DataFrame,
        position: int,
    ) -> Dict:
        """Expanding-window inference at a single feature index (causal)."""
        window = features.iloc[: position + 1]
        scaler = StandardScaler()
        scaled = scaler.fit_transform(window)

        model = GaussianHMM(
            n_components=3,
            covariance_type="full",
            n_iter=200,
            random_state=42,
        )
        model.fit(scaled)

        hidden_states = model.predict(scaled)
        probabilities = model.predict_proba(scaled)

        latest_state = int(hidden_states[-1])
        latest_probs = probabilities[-1]

        mr_s, tr_s, cr_s = _map_states_by_volatility(window, hidden_states)

        return {
            "regime_state": latest_state,
            "hmm_regime": _regime_label_for_state(
                latest_state, mr_s, tr_s, cr_s
            ),
            "mean_revert_probability": round(
                float(latest_probs[mr_s] * 100), 4
            ),
            "trend_probability": round(
                float(latest_probs[tr_s] * 100), 4
            ),
            "crisis_probability": round(
                float(latest_probs[cr_s] * 100), 4
            ),
        }

    def compute_historical_regimes(
        self,
        df: pd.DataFrame,
        index: Optional[Union[pd.Index, Iterable]] = None,
    ) -> pd.DataFrame:
        """
        Expanding-window HMM inference: at each bar t, fit only on [0..t],
        infer state and posterior at t. No future bars used for bar t.

        Parameters
        ----------
        index : optional
            Datetime index values to infer. If None, infer every bar
            from min_train onward (full feature history; slower).
        """
        features = build_hmm_features(df)
        n = len(features)

        columns = [
            "regime_state",
            "hmm_regime",
            "mean_revert_probability",
            "trend_probability",
            "crisis_probability",
        ]

        if n == 0:
            return pd.DataFrame(columns=columns)

        if index is None:
            positions = list(range(self.min_train - 1, n))
            target_index = features.index[positions]
        else:
            target_index = pd.Index(index)
            positions = [
                features.index.get_loc(idx)
                for idx in target_index
                if idx in features.index
            ]

        records: Dict = {}

        for i in positions:
            if i < self.min_train - 1:
                continue

            ts = features.index[i]
            records[ts] = self._infer_at_position(features, i)

        return pd.DataFrame.from_dict(records, orient="index")

    @staticmethod
    def snapshot_from_history(history: pd.DataFrame) -> Dict:
        """Latest-bar API payload from an existing historical series."""
        if history.empty or history["hmm_regime"].dropna().empty:
            return {
                "regime_state": 0,
                "regime_label": "MEAN_REVERT",
                "mean_revert_probability": 0.0,
                "trend_probability": 0.0,
                "crisis_probability": 0.0,
            }

        latest = history.dropna(subset=["hmm_regime"]).iloc[-1]

        return {
            "regime_state": int(latest["regime_state"]),
            "regime_label": str(latest["hmm_regime"]),
            "mean_revert_probability": float(
                latest["mean_revert_probability"]
            ),
            "trend_probability": float(latest["trend_probability"]),
            "crisis_probability": float(latest["crisis_probability"]),
        }

    def classify_regimes(self, df: pd.DataFrame) -> Dict:
        """
        Latest-bar snapshot: one expanding-window fit on all history
        through the final bar (causal for the latest observation).
        """
        features = build_hmm_features(df)

        if len(features) < self.min_train:
            return HMMRegimeEngine.snapshot_from_history(
                pd.DataFrame()
            )

        return self._infer_at_position(features, len(features) - 1)
