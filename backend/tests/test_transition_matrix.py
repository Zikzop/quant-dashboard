"""Regime transition-matrix engine tests (P1.4)."""

from __future__ import annotations

from regime.transition_matrix import build_transition_model


def test_perfectly_persistent_chain():
    labels = ["TRENDING"] * 50
    model = build_transition_model(labels)
    assert model.matrix["TRENDING"]["TRENDING"] == 1.0
    assert model.persistence["TRENDING"] == 1.0
    assert model.instability_score == 0.0
    assert model.expected_duration["TRENDING"] is None  # 1/(1-1) -> inf -> None


def test_known_two_state_transitions():
    # Alternating chain: every transition switches state.
    labels = ["TRENDING", "CRISIS"] * 25
    model = build_transition_model(labels)
    assert model.matrix["TRENDING"]["CRISIS"] == 1.0
    assert model.matrix["CRISIS"]["TRENDING"] == 1.0
    assert model.persistence["TRENDING"] == 0.0
    assert model.instability_score == 1.0
    assert model.is_unstable is True


def test_counts_sum_to_transitions():
    labels = ["MEAN_REVERT", "TRENDING", "TRENDING", "CRISIS", "MEAN_REVERT"]
    model = build_transition_model(labels)
    total = sum(
        model.counts[a][b] for a in model.counts for b in model.counts[a]
    )
    assert total == model.n_transitions == len(labels) - 1


def test_rows_are_stochastic():
    labels = ["MEAN_REVERT", "TRENDING", "CRISIS", "TRENDING", "MEAN_REVERT", "CRISIS"] * 10
    model = build_transition_model(labels)
    for src in model.states:
        row_sum = sum(model.matrix[src].values())
        assert abs(row_sum - 1.0) < 1e-9


def test_low_confidence_flag_on_short_sequence():
    model = build_transition_model(["TRENDING", "CRISIS", "TRENDING"])
    assert model.low_confidence is True


def test_ignores_unknown_labels():
    model = build_transition_model(["UNKNOWN", "TRENDING", None, "TRENDING", "nan"])
    assert "UNKNOWN" not in model.states
    assert model.n_transitions == 1
