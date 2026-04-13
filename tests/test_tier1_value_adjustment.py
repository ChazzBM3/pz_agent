from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique_reranker import CritiqueRerankerAgent
from pz_agent.analysis.pareto import compute_tier_1_value_adjustment
from pz_agent.io import write_json
from pz_agent.state import RunState


def test_tier1_value_adjustment_rewards_good_measurements() -> None:
    bonus, rationale = compute_tier_1_value_adjustment(
        {
            "oxidation_potential": {"value": 1.2},
            "reduction_potential": {"value": 0.8},
            "groundState.solvation_energy": {"value": -0.6},
            "hole_reorganization_energy": {"value": 0.2},
        }
    )

    assert bonus > 0
    assert any("tier1_value_adjustment:oxidation_potential" in item for item in rationale)
    assert any("tier1_value_adjustment:groundState.solvation_energy" in item for item in rationale)


def test_critique_reranker_uses_tier1_measurement_values(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    write_json(
        graph_path,
        {
            "nodes": [
                {"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1"}},
                {
                    "id": "measurement::cand_1::oxidation_potential",
                    "type": "Measurement",
                    "attrs": {
                        "record_id": "cand_1",
                        "property_name": "oxidation_potential",
                        "value": 1.5,
                    },
                },
                {
                    "id": "measurement::cand_1::groundState.solvation_energy",
                    "type": "Measurement",
                    "attrs": {
                        "record_id": "cand_1",
                        "property_name": "groundState.solvation_energy",
                        "value": -0.8,
                    },
                },
            ],
            "edges": [
                {"source": "measurement::cand_1::oxidation_potential", "target": "cand_1", "type": "MEASURED_FOR"},
                {"source": "measurement::cand_1::oxidation_potential", "target": "property::oxidation_potential", "type": "HAS_PROPERTY"},
                {"source": "measurement::cand_1::groundState.solvation_energy", "target": "cand_1", "type": "MEASURED_FOR"},
                {"source": "measurement::cand_1::groundState.solvation_energy", "target": "property::groundState.solvation_energy", "type": "HAS_PROPERTY"},
            ],
        },
    )

    state = RunState(config={"screening": {"shortlist_size": 3}}, run_dir=tmp_path)
    state.knowledge_graph_path = graph_path
    state.ranked = [
        {
            "id": "cand_1",
            "predicted_priority": 0.5,
            "identity": {},
        }
    ]
    state.critique_notes = [
        {
            "candidate_id": "cand_1",
            "signals": {
                "supports_solubility": False,
                "supports_synthesizability": False,
                "warns_instability": False,
                "exact_match_hits": 0,
                "analog_match_hits": 0,
                "support_score": 0.0,
                "contradiction_score": 0.0,
                "measurement_count": 0,
                "property_count": 0,
            },
        }
    ]

    agent = CritiqueRerankerAgent(config=state.config)
    updated = agent.run(state)

    row = updated.ranked[0]
    assert row["predicted_priority_literature_adjusted"] > 0.5
    assert "measurement_values" in row["ranking_rationale"]
    assert any(
        "tier1_value_adjustment:oxidation_potential" in item
        for item in row["ranking_rationale"]["literature_adjustment"]
    )
