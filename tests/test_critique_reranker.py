from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique_reranker import CritiqueRerankerAgent
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
