from __future__ import annotations

from pz_agent.analysis.pareto import compute_measurement_hierarchy_adjustment


def test_measurement_hierarchy_prefers_tier_1_properties() -> None:
    bonus, rationale = compute_measurement_hierarchy_adjustment(
        {
            "properties": [
                "oxidation_potential",
                "reduction_potential",
                "groundState.homo",
                "sa_score",
            ]
        }
    )

    assert bonus > 0
    assert any("d3tales_tier1_bonus" in item for item in rationale)
    assert any("d3tales_tier2_bonus" in item for item in rationale)
    assert any("d3tales_tier3_bonus" in item for item in rationale)
