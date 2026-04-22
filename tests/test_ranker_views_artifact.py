from __future__ import annotations

import json
from pathlib import Path

from pz_agent.agents.ranker import RankerAgent
from pz_agent.state import RunState


def test_ranker_writes_parallel_views_artifact(tmp_path: Path) -> None:
    graph = {
        "nodes": [
            {"id": "cand-a", "type": "Molecule", "attrs": {}},
            {"id": "cand-b", "type": "Molecule", "attrs": {}},
            {"id": "scaffold::a", "type": "Scaffold", "attrs": {"smiles": "c1ccccc1"}},
            {"id": "scaffold::b", "type": "Scaffold", "attrs": {"smiles": "c1ccncc1"}},
        ],
        "edges": [
            {"source": "cand-a", "target": "scaffold::a", "type": "HAS_SCAFFOLD"},
            {"source": "cand-b", "target": "scaffold::b", "type": "HAS_SCAFFOLD"},
        ],
    }
    graph_path = tmp_path / "kg.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")

    state = RunState(
        config={"screening": {"shortlist_size": 1}},
        run_dir=tmp_path,
        knowledge_graph_path=graph_path,
        predictions=[
            {"id": "cand-a", "predicted_priority": 0.70, "predicted_synthesizability": 0.71, "predicted_solubility": 0.69},
            {"id": "cand-b", "predicted_priority": 0.68, "predicted_synthesizability": 0.68, "predicted_solubility": 0.68},
        ],
        critique_notes=[
            {"candidate_id": "cand-b", "support_mix": {"adjacent_scaffold_support": 0.5}, "signals": {"exact_match_hits": 0}},
        ],
    )

    RankerAgent(config={}).run(state)

    artifact = tmp_path / "ranker_views.json"
    assert artifact.exists()
    payload = json.loads(artifact.read_text())
    assert isinstance(payload.get("ranked"), list)
    assert isinstance(payload.get("novelty_ranked"), list)
    assert isinstance(payload.get("shortlist"), list)
    assert isinstance(payload.get("novelty_shortlist"), list)
