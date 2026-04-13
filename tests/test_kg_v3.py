from __future__ import annotations

from pathlib import Path

from pz_agent.kg.builder import build_graph_snapshot
from pz_agent.state import RunState



def test_build_graph_snapshot_includes_transitional_v3_nodes(tmp_path: Path) -> None:
    state = RunState(
        config={},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "identity": {"scaffold": "phenothiazine"}}],
        dossier_registry=[{"candidate_id": "cand_1", "hypothesis": {"text": "test"}}],
        belief_registry=[{"candidate_id": "cand_1", "status": "open", "confidence": 0.6, "evidence_count": 1, "owner": "CritiqueAgent"}],
        ranking_registry=[{"candidate_id": "cand_1", "ranking_snapshot": {"predicted_priority": 1.0}}],
        simulation_requests=[{"candidate_id": "cand_1", "requested_tier": 1, "reason": "uncertainty"}],
        simulation_results=[{"candidate_id": "cand_1", "result": "pending"}],
    )
    graph = build_graph_snapshot(state)
    node_ids = {node["id"] for node in graph["nodes"]}
    assert "run::simulation_request::cand_1::1" in node_ids
    assert "run::simulation_result::cand_1" in node_ids
    assert "belief::cand_1" in node_ids
    assert "belief::dossier::cand_1" in node_ids
    run_node = next(node for node in graph["nodes"] if node["id"].startswith("run::"))
    assert "kg_layers" in run_node["attrs"]
