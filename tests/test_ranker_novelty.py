from __future__ import annotations

from pathlib import Path

from pz_agent.agents.ranker import RankerAgent
from pz_agent.state import RunState


def test_ranker_produces_parallel_novelty_shortlist(tmp_path: Path) -> None:
    graph = {
        "nodes": [
            {"id": "cand-supported", "type": "Molecule", "attrs": {}},
            {"id": "cand-novel", "type": "Molecule", "attrs": {}},
            {"id": "scaffold::dense", "type": "Scaffold", "attrs": {"smiles": "c1ccccc1"}},
            {"id": "scaffold::sparse", "type": "Scaffold", "attrs": {"smiles": "c1ccncc1"}},
        ],
        "edges": [
            {"source": "cand-supported", "target": "scaffold::dense", "type": "HAS_SCAFFOLD"},
            {"source": "cand-novel", "target": "scaffold::sparse", "type": "HAS_SCAFFOLD"},
        ]
        + [
            {"source": f"dense-member-{i}", "target": "scaffold::dense", "type": "HAS_SCAFFOLD"}
            for i in range(120)
        ]
        + [
            {"source": f"dense-meas-{i}", "target": "cand-supported", "type": "MEASURED_FOR"}
            for i in range(12)
        ]
        + [
            {"source": f"sparse-member-{i}", "target": "scaffold::sparse", "type": "HAS_SCAFFOLD"}
            for i in range(3)
        ],
    }
    graph_path = tmp_path / "kg.json"
    graph_path.write_text(__import__("json").dumps(graph), encoding="utf-8")

    state = RunState(
        config={"screening": {"shortlist_size": 1}},
        run_dir=tmp_path,
        knowledge_graph_path=graph_path,
        predictions=[
            {"id": "cand-supported", "predicted_priority": 0.78, "predicted_synthesizability": 0.80, "predicted_solubility": 0.76},
            {"id": "cand-novel", "predicted_priority": 0.68, "predicted_synthesizability": 0.70, "predicted_solubility": 0.66},
        ],
        critique_notes=[
            {
                "candidate_id": "cand-novel",
                "support_mix": {"adjacent_scaffold_support": 0.5},
                "signals": {"exact_match_hits": 0},
            },
            {
                "candidate_id": "cand-supported",
                "support_mix": {},
                "signals": {
                    "exact_match_hits": 4,
                    "property_aligned_hits": 3,
                    "measurement_count": 12,
                    "property_count": 5,
                    "support_score": 8,
                },
            },
        ],
    )

    new_state = RankerAgent(config={}).run(state)

    assert new_state.shortlist is not None
    assert new_state.novelty_shortlist is not None
    assert new_state.novelty_ranked is not None
    assert new_state.ranked is not None
    ranked_by_id = {row["id"]: row for row in new_state.ranked}
    novelty_by_id = {row["id"]: row for row in new_state.novelty_ranked}
    assert novelty_by_id["cand-novel"]["novelty_adjustment"] > novelty_by_id["cand-supported"]["novelty_adjustment"]
    assert novelty_by_id["cand-novel"]["predicted_priority_novelty_adjusted"] > novelty_by_id["cand-novel"]["predicted_priority"]
    assert ranked_by_id["cand-supported"]["ranking_rationale"].get("scaffold_context")
    assert novelty_by_id["cand-novel"]["ranking_rationale"].get("novelty_adjustment")
