from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique_reranker import CritiqueRerankerAgent
from pz_agent.analysis.pareto import compute_tier_1_value_adjustment
from pz_agent.io import write_json
from pz_agent.state import RunState


def test_tier1_value_adjustment_rewards_good_measurements() -> None:
    bonus, rationale = compute_tier_1_value_adjustment(
        {
            "oxidation_potential": {"value": 1.8},
            "reduction_potential": {"value": 7.2},
            "groundState.solvation_energy": {"value": -0.5},
            "hole_reorganization_energy": {"value": 0.3},
        }
    )

    assert bonus > 0
    assert any("tier1_value_adjustment:oxidation_potential" in item for item in rationale)
    assert any("tier1_value_adjustment:groundState.solvation_energy" in item for item in rationale)



def test_tier1_value_adjustment_penalizes_bad_measurements() -> None:
    bonus, rationale = compute_tier_1_value_adjustment(
        {
            "oxidation_potential": {"value": 0.4},
            "reduction_potential": {"value": 4.5},
            "groundState.solvation_energy": {"value": 0.4},
            "hole_reorganization_energy": {"value": 1.6},
        }
    )

    assert bonus < 0
    assert any("normalized=-" in item for item in rationale)


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
                        "value": 1.8,
                    },
                },
                {
                    "id": "measurement::cand_1::groundState.solvation_energy",
                    "type": "Measurement",
                    "attrs": {
                        "record_id": "cand_1",
                        "property_name": "groundState.solvation_energy",
                        "value": -0.5,
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



def test_critique_reranker_uses_note_only_measurement_values_without_kg(tmp_path: Path) -> None:
    state = RunState(config={"screening": {"shortlist_size": 3}}, run_dir=tmp_path)
    state.ranked = [
        {
            "id": "cand_good",
            "predicted_priority": 0.5,
            "identity": {},
        },
        {
            "id": "cand_bad",
            "predicted_priority": 0.5,
            "identity": {},
        },
    ]
    state.critique_notes = [
        {
            "candidate_id": "cand_good",
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
            "measurement_context": {
                "properties": [
                    "oxidation_potential",
                    "reduction_potential",
                    "groundState.solvation_energy",
                    "hole_reorganization_energy",
                ]
            },
            "measurement_values": {
                "oxidation_potential": {"value": 1.8},
                "reduction_potential": {"value": 7.2},
                "groundState.solvation_energy": {"value": -0.5},
                "hole_reorganization_energy": {"value": 0.3},
            },
        },
        {
            "candidate_id": "cand_bad",
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
            "measurement_context": {
                "properties": [
                    "oxidation_potential",
                    "reduction_potential",
                    "groundState.solvation_energy",
                    "hole_reorganization_energy",
                ]
            },
            "measurement_values": {
                "oxidation_potential": {"value": 0.4},
                "reduction_potential": {"value": 4.5},
                "groundState.solvation_energy": {"value": 0.4},
                "hole_reorganization_energy": {"value": 1.6},
            },
        },
    ]

    updated = CritiqueRerankerAgent(config=state.config).run(state)
    assert updated.ranked[0]["id"] == "cand_good"
    assert updated.ranked[0]["predicted_priority_literature_adjusted"] > 0.5
    assert updated.ranked[1]["predicted_priority_literature_adjusted"] < 0.5
