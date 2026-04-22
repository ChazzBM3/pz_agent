from __future__ import annotations

from pz_agent.analysis.pareto import compute_scaffold_support_adjustment


def test_scaffold_support_adjustment_rewards_supported_families() -> None:
    bonus, rationale = compute_scaffold_support_adjustment(
        {
            "scaffold_family_size": 127,
            "scaffold_family_avg_measurements": 15.7,
            "scaffold_measurement_density": 12,
        }
    )
    assert bonus > 0
    assert any("scaffold_family_support_bonus" in item for item in rationale)
    assert any("scaffold_family_measurement_bonus" in item for item in rationale)


def test_scaffold_support_adjustment_penalizes_isolated_unmeasured_candidate() -> None:
    bonus, rationale = compute_scaffold_support_adjustment(
        {
            "scaffold_family_size": 2,
            "scaffold_family_avg_measurements": 12.0,
            "scaffold_measurement_density": 0,
        }
    )
    assert bonus < 0.03
    assert any("scaffold_family_sparse_penalty" in item for item in rationale)
    assert any("candidate_without_local_measurements_penalty" in item for item in rationale)
