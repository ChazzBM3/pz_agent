from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState



def _infer_tier_from_note(note: dict) -> int:
    requested = note.get("recommended_next_tier")
    if requested is not None:
        return int(requested)
    signals = note.get("signals", {}) or {}
    if signals.get("multimodal_support_score"):
        return 1
    if signals.get("warns_instability"):
        return 4
    if signals.get("supports_solubility") is False:
        return 3
    return 2


def _question_for_request(tier: int, scientific_question: str | None, note: dict) -> str:
    if scientific_question:
        return scientific_question
    bridge_hypothesis = note.get("bridge_hypothesis") or {}
    failure_mode = bridge_hypothesis.get("expected_failure_mode")
    transferred_property = bridge_hypothesis.get("transferred_property")
    if transferred_property:
        return f"Does the proposed bridge transfer hold for {transferred_property}?"
    if failure_mode:
        return f"Can we resolve the risk of {failure_mode}?"
    return {
        0: "Fast filter validation",
        1: "Resolve low-cost structural/electronic uncertainty",
        2: "Resolve DFT-grade redox or geometry uncertainty",
        3: "Resolve solubility or aggregation uncertainty",
        4: "Resolve degradation or failure-mode uncertainty",
    }.get(tier, "Resolve scientific uncertainty")


class SimulationPlannerAgent(BaseAgent):
    name = "simulation_planner"

    def run(self, state: RunState) -> RunState:
        note_map = {note.get("candidate_id"): note for note in (state.critique_notes or [])}
        decision_map = {item.get("compound_id"): item for item in (state.candidate_decision_registry or [])}
        belief_state_map = {item.get("entity_id"): item for item in (state.belief_state_registry or [])}
        requests = list(state.simulation_requests or [])
        if not requests:
            for candidate in state.shortlist or []:
                candidate_id = candidate.get("id")
                note = note_map.get(candidate_id, {})
                decision = decision_map.get(candidate_id, {}).get("decision") or note.get("decision")
                if decision == "simulate-next":
                    requests.append(
                        {
                            "simulation_request_id": f"simreq::{candidate_id}",
                            "compound_id": candidate_id,
                            "candidate_id": candidate_id,
                            "requested_tier": _infer_tier_from_note(note),
                            "reason": "simulation_planner_from_critique",
                            "requested_by": "simulation_planner",
                        }
                    )

        planned = []
        for request in requests:
            candidate_id = request.get("compound_id") or request.get("candidate_id")
            note = note_map.get(candidate_id, {})
            decision = decision_map.get(candidate_id, {})
            belief_state = belief_state_map.get(candidate_id, {})
            tier = int(request.get("requested_tier") or _infer_tier_from_note(note))
            bridge_hypothesis = note.get("bridge_hypothesis") or {}
            if bridge_hypothesis.get("expected_failure_mode") == "solubility_regression":
                tier = max(tier, 3)
            elif bridge_hypothesis.get("transferred_property") in {"redox_tuning", "oxidation_potential_shift", "reduction_potential_shift"}:
                tier = max(tier, 2)
            priority = max(0.1, min(1.0, float(decision.get("score_summary", {}).get("bridge_score", 0.0) or 0.0) + float(1.0 - belief_state.get("confidence", 0.5))))
            planned.append(
                {
                    **request,
                    "simulation_request_id": request.get("simulation_request_id") or f"simreq::{candidate_id}::{tier}",
                    "compound_id": candidate_id,
                    "candidate_id": candidate_id,
                    "tier": tier,
                    "requested_tier": tier,
                    "planner_status": "planned",
                    "question": _question_for_request(tier, request.get("scientific_question"), note),
                    "priority": round(priority, 3),
                    "requested_by": request.get("requested_by") or "critique_agent",
                }
            )

        state.simulation_requests = planned
        state.dft_queue = [item for item in planned if int(item.get("tier") or 0) >= 2]
        state.log(f"SimulationPlannerAgent planned {len(planned)} simulation requests")
        return state
