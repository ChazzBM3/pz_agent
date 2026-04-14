from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique_reranker import CritiqueRerankerAgent
from pz_agent.analysis.pareto import apply_literature_adjustment
from pz_agent.io import write_json
from pz_agent.state import RunState


def test_critique_reranker_uses_kg_summary(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    write_json(
        graph_path,
        {
            "nodes": [
                {"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1"}},
                {
                    "id": "claim::cand_1",
                    "type": "Claim",
                    "attrs": {
                        "summary": "Solubility support for cand_1.",
                        "signals": {
                            "exact_match_hits": 1,
                            "analog_match_hits": 3,
                            "support_score": 4.0,
                            "contradiction_score": 0.0,
                        },
                    },
                },
            ],
            "edges": [
                {"source": "claim::cand_1", "target": "cand_1", "type": "ABOUT_MOLECULE"},
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
                "supports_solubility": True,
                "supports_synthesizability": False,
                "warns_instability": False,
                "exact_match_hits": 0,
                "analog_match_hits": 0,
                "support_score": 0.0,
                "contradiction_score": 0.0,
            },
        }
    ]

    agent = CritiqueRerankerAgent(config=state.config)
    updated = agent.run(state)

    assert updated.ranked is not None
    row = updated.ranked[0]
    assert row["predicted_priority_literature_adjusted"] > 0.5
    assert row["ranking_rationale"]["kg_summary"]["exact_match_hits"] >= 1
    assert "support_mix" in row["ranking_rationale"]


def test_critique_reranker_preserves_base_priority_without_note(tmp_path: Path) -> None:
    state = RunState(config={"screening": {"shortlist_size": 3}}, run_dir=tmp_path)
    state.ranked = [
        {
            "id": "cand_2",
            "predicted_priority": 0.61,
            "identity": {},
        }
    ]
    state.critique_notes = []

    agent = CritiqueRerankerAgent(config=state.config)
    updated = agent.run(state)

    row = updated.ranked[0]
    assert row["predicted_priority_literature_adjusted"] == 0.61
    assert row["literature_adjustment"] == 0.0



def test_apply_literature_adjustment_rewards_specific_evidence_and_penalizes_off_target() -> None:
    row = {"id": "cand_3", "predicted_priority": 0.5, "ranking_rationale": {}, "identity": {}}

    specific = apply_literature_adjustment(
        row,
        {
            "candidate_id": "cand_3",
            "evidence_tier": "candidate",
            "signals": {
                "supports_solubility": False,
                "supports_synthesizability": False,
                "warns_instability": False,
                "exact_match_hits": 1,
                "analog_match_hits": 1,
                "support_score": 0.0,
                "contradiction_score": 0.0,
            },
            "evidence": [
                {"match_type": "exact", "title": "Phenothiazine redox solubility study", "snippet": "Exact candidate redox and solubility evidence."},
                {"match_type": "analog", "title": "Analog phenothiazine electrolyte paper", "snippet": "Electrolyte and voltammetry behavior."},
            ],
        },
    )
    noisy = apply_literature_adjustment(
        row,
        {
            "candidate_id": "cand_3",
            "evidence_tier": "candidate",
            "signals": {
                "supports_solubility": False,
                "supports_synthesizability": False,
                "warns_instability": False,
                "exact_match_hits": 0,
                "analog_match_hits": 0,
                "support_score": 0.0,
                "contradiction_score": 0.0,
            },
            "evidence": [
                {"match_type": "unknown", "title": "Organophotoredox catalyst paper", "snippet": "Photocatalyst rearrangement chemistry."},
                {"match_type": "unknown", "title": "Redox polymers for nanomedicine", "snippet": "Polymer and nanomedicine discussion."},
            ],
        },
    )

    assert specific["predicted_priority_literature_adjusted"] > noisy["predicted_priority_literature_adjusted"]
    assert any("property_specific_evidence_bonus" in item or "exact_hits_bonus" in item for item in specific["ranking_rationale"]["literature_adjustment"])
    assert any("off_target_evidence_penalty" in item for item in noisy["ranking_rationale"]["literature_adjustment"])



def test_apply_literature_adjustment_rewards_bridge_transferability() -> None:
    row = {"id": "cand_bridge", "predicted_priority": 0.5, "ranking_rationale": {}, "identity": {}}
    bridged = apply_literature_adjustment(
        row,
        {
            "candidate_id": "cand_bridge",
            "evidence_tier": "analog",
            "signals": {
                "support_score": 0.0,
                "contradiction_score": 0.0,
                "exact_match_hits": 0,
                "analog_match_hits": 1,
            },
            "support_mix": {
                "adjacent_scaffold_support": 0.4,
                "quinone_bridge_support": 0.0,
                "transferability_score": 0.8,
            },
            "evidence": [{"match_type": "analog", "title": "Adjacent scaffold study", "snippet": "Redox solubility evidence."}],
        },
    )
    assert bridged["predicted_priority_literature_adjusted"] > 0.5
    assert any("bridge_transferability_bonus" in item for item in bridged["ranking_rationale"]["literature_adjustment"])
