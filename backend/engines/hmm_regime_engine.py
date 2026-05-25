import numpy as np
import pandas as pd

from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler

from engines.feature_engineering import build_hmm_features


class HMMRegimeEngine:

    def __init__(self):

        self.model = GaussianHMM(
            n_components=3, covariance_type="full", n_iter=1000, random_state=42
        )

        self.scaler = StandardScaler()

    def classify_regimes(self, df):

        features = build_hmm_features(df)

        scaled_features = self.scaler.fit_transform(features)

        self.model.fit(scaled_features)

        hidden_states = self.model.predict(scaled_features)

        probabilities = self.model.predict_proba(scaled_features)

        latest_state = int(hidden_states[-1])

        latest_probs = probabilities[-1]

        state_volatility = []

        for state in range(3):

            state_returns = features[hidden_states == state]["realized_vol"]

            state_volatility.append(state_returns.mean())

        sorted_states = np.argsort(state_volatility)

        mean_revert_state = sorted_states[0]
        trending_state = sorted_states[1]
        crisis_state = sorted_states[2]

        if latest_state == mean_revert_state:
            regime_label = "MEAN_REVERT"

        elif latest_state == trending_state:
            regime_label = "TRENDING"

        else:
            regime_label = "CRISIS"

        return {
            "regime_state": latest_state,
            "regime_label": regime_label,
            "mean_revert_probability": round(
                float(latest_probs[mean_revert_state] * 100), 2
            ),
            "trend_probability": round(float(latest_probs[trending_state] * 100), 2),
            "crisis_probability": round(float(latest_probs[crisis_state] * 100), 2),
        }
