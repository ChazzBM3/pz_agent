from __future__ import annotations

from pathlib import Path

from pz_agent.kg.builder import build_graph_snapshot
from pz_agent.state import RunState



def test_build_graph_snapshot_includes_transitional_v3_nodes(tmp_path: Path) -> None:
    state = RunState(
        config={},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "identity": {"scaffold": "phenothiazine"}}],
        dossier_registry=[{"candidate_id": "cand_1", "hypothesis": {"text": "test"}, "bridge_hypothesis": {"source_family": "chem_qn::quinone_abstract", "target_family": "chem_pt::phenothiazine", "transferred_property": "redox_tuning", "transfer_hypothesis": "transfer useful redox behavior", "source_motif": "quinone_redox_pattern", "target_motif": "phenothiazine_redox_pattern", "transfer_preconditions": ["substituent_present"], "expected_transferred_effect": "partial_redox_behavior_transfer", "expected_failure_mode": "effect_not_transferred", "failure_rationale": "orbital mismatch", "template_id": "qn_to_pt_generic_redox_transfer", "transfer_confidence": 0.5}}],
        candidate_decision_registry=[{"candidate_decision_id": "decision::cand_1", "compound_id": "cand_1", "decision": "simulate-next", "decision_reason_codes": ["bridge_support_only"], "score_summary": {"support": 0.4}}],
        belief_state_registry=[{"belief_state_id": "belief_state::cand_1", "entity_type": "compound", "entity_id": "cand_1", "support_count": 1, "contradiction_count": 0, "source_mix": {"bridge": True}, "confidence": 0.6, "last_updated": "critique_agent"}],
        belief_registry=[{"candidate_id": "cand_1", "status": "open", "confidence": 0.6, "evidence_count": 1, "owner": "CritiqueAgent"}],
        ranking_registry=[{"candidate_id": "cand_1", "ranking_snapshot": {"predicted_priority": 1.0}}],
        simulation_requests=[{"candidate_id": "cand_1", "requested_tier": 1, "reason": "uncertainty"}],
        simulation_results=[{"candidate_id": "cand_1", "result": "pending"}],
    )
    graph = build_graph_snapshot(state)
    node_ids = {node["id"] for node in graph["nodes"]}
    assert "run::simulation_request::cand_1::1" in node_ids
    assert "run::simulation_result::cand_1" in node_ids
    assert "decision::cand_1" in node_ids
    assert "belief_state::cand_1" in node_ids
    assert "belief::cand_1" in node_ids
    assert "belief::dossier::cand_1" in node_ids
    assert "chem_pt::scaffold::phenothiazine" in node_ids
    assert any(node_id.startswith("chem_bridge::rule::") for node_id in node_ids)
    assert any(node_id.startswith("chem_bridge::case::") for node_id in node_ids)
    assert any(node_id.startswith("identity::compound::") for node_id in node_ids)
    assert any(node_id.startswith("identity::scaffold::") for node_id in node_ids)
    run_node = next(node for node in graph["nodes"] if node["id"].startswith("run::"))
    assert "kg_layers" in run_node["attrs"]
