from __future__ import annotations

from pathlib import Path

from pz_agent.agents.simulation_planner import SimulationPlannerAgent
from pz_agent.state import RunState



def test_simulation_planner_uses_critique_requests(tmp_path: Path) -> None:
    state = RunState(
        config={"simulation_planner": {"enabled": True}},
        run_dir=tmp_path,
        shortlist=[{"id": "cand_1"}],
        critique_notes=[{"candidate_id": "cand_1", "decision": "simulate-next", "recommended_next_tier": 3, "signals": {}}],
        simulation_requests=[{"candidate_id": "cand_1", "requested_tier": 3, "reason": "critique_uncertainty_resolution"}],
    )
    updated = SimulationPlannerAgent(config=state.config).run(state)
    assert updated.simulation_requests is not None
    assert updated.simulation_requests[0]["planner_status"] == "planned"
    assert updated.simulation_requests[0]["requested_tier"] == 3
    assert updated.dft_queue == [{"candidate_id": "cand_1", "requested_tier": 3, "reason": "critique_uncertainty_resolution", "planner_status": "planned", "question": "Resolve solubility or aggregation uncertainty"}]



def test_simulation_planner_builds_request_from_critique_note(tmp_path: Path) -> None:
    state = RunState(
        config={"simulation_planner": {"enabled": True}},
        run_dir=tmp_path,
        shortlist=[{"id": "cand_2"}],
        critique_notes=[{"candidate_id": "cand_2", "decision": "simulate-next", "signals": {"multimodal_support_score": 1.0}}],
        simulation_requests=[],
    )
    updated = SimulationPlannerAgent(config=state.config).run(state)
    assert updated.simulation_requests is not None
    assert updated.simulation_requests[0]["requested_tier"] == 1
