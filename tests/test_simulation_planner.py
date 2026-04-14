from __future__ import annotations

from pathlib import Path

from pz_agent.agents.simulation_planner import SimulationPlannerAgent
from pz_agent.state import RunState



def test_simulation_planner_uses_critique_requests(tmp_path: Path) -> None:
    state = RunState(
        config={"simulation_planner": {"enabled": True}},
        run_dir=tmp_path,
        shortlist=[{"id": "cand_1"}],
        critique_notes=[{"candidate_id": "cand_1", "decision": "simulate-next", "recommended_next_tier": 3, "signals": {}, "bridge_hypothesis": {"expected_failure_mode": "solubility_regression"}}],
        candidate_decision_registry=[{"compound_id": "cand_1", "decision": "simulate-next", "score_summary": {"bridge_score": 0.6}}],
        belief_state_registry=[{"entity_id": "cand_1", "confidence": 0.4}],
        simulation_requests=[{"candidate_id": "cand_1", "requested_tier": 3, "reason": "critique_uncertainty_resolution"}],
    )
    updated = SimulationPlannerAgent(config=state.config).run(state)
    assert updated.simulation_requests is not None
    assert updated.simulation_requests[0]["planner_status"] == "planned"
    assert updated.simulation_requests[0]["requested_tier"] == 3
    assert updated.simulation_requests[0]["tier"] == 3
    assert updated.simulation_requests[0]["priority"] > 0.5
    assert updated.dft_queue[0]["question"] == "Can we resolve the risk of solubility_regression?"



def test_simulation_planner_builds_request_from_critique_note(tmp_path: Path) -> None:
    state = RunState(
        config={"simulation_planner": {"enabled": True}},
        run_dir=tmp_path,
        shortlist=[{"id": "cand_2"}],
        critique_notes=[{"candidate_id": "cand_2", "decision": "simulate-next", "signals": {"multimodal_support_score": 1.0}, "bridge_hypothesis": {"transferred_property": "redox_tuning"}}],
        candidate_decision_registry=[{"compound_id": "cand_2", "decision": "simulate-next", "score_summary": {"bridge_score": 0.4}}],
        belief_state_registry=[{"entity_id": "cand_2", "confidence": 0.6}],
        simulation_requests=[],
    )
    updated = SimulationPlannerAgent(config=state.config).run(state)
    assert updated.simulation_requests is not None
    assert updated.simulation_requests[0]["requested_tier"] == 2
    assert updated.simulation_requests[0]["requested_by"] == "simulation_planner"
    assert "redox_tuning" in updated.simulation_requests[0]["question"]
