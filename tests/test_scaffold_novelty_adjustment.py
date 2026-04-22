from __future__ import annotations

from pz_agent.analysis.pareto import compute_scaffold_novelty_adjustment


def test_scaffold_novelty_adjustment_rewards_sparse_high_priority_family() -> None:
    bonus, rationale = compute_scaffold_novelty_adjustment(
        {"predicted_priority": 0.72},
        {"support_mix": {"adjacent_scaffold_support": 0.4}, "signals": {"exact_match_hits": 0}},
        {
            "scaffold_family_size": 4,
            "scaffold_family_avg_measurements": 2.0,
            "scaffold_measurement_density": 0,
        },
    )
    assert bonus > 0.10
    assert any("novel_sparse_family_bonus" in item for item in rationale)
    assert any("high_priority_underexplored_family_bonus" in item for item in rationale)
    assert any("analog_bridge_novelty_bonus" in item for item in rationale)


def test_scaffold_novelty_adjustment_penalizes_dense_family() -> None:
    bonus, rationale = compute_scaffold_novelty_adjustment(
        {"predicted_priority": 0.72},
        None,
        {
            "scaffold_family_size": 250,
            "scaffold_family_avg_measurements": 20.0,
            "scaffold_measurement_density": 12,
        },
    )
    assert bonus < 0
    assert any("novel_dense_family_penalty" in item for item in rationale)
