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


class SimulationPlannerAgent(BaseAgent):
    name = "simulation_planner"

    def run(self, state: RunState) -> RunState:
        note_map = {note.get("candidate_id"): note for note in (state.critique_notes or [])}
        requests = list(state.simulation_requests or [])
        if not requests:
            for candidate in state.shortlist or []:
                note = note_map.get(candidate.get("id"), {})
                decision = note.get("decision")
                if decision == "simulate-next":
                    requests.append(
                        {
                            "candidate_id": candidate.get("id"),
                            "requested_tier": _infer_tier_from_note(note),
                            "reason": "simulation_planner_from_critique",
                        }
                    )

        planned = []
        for request in requests:
            candidate_id = request.get("candidate_id")
            note = note_map.get(candidate_id, {})
            tier = int(request.get("requested_tier") or _infer_tier_from_note(note))
            planned.append(
                {
                    **request,
                    "requested_tier": tier,
                    "planner_status": "planned",
                    "question": {
                        0: "Fast filter validation",
                        1: "Resolve low-cost structural/electronic uncertainty",
                        2: "Resolve DFT-grade redox or geometry uncertainty",
                        3: "Resolve solubility or aggregation uncertainty",
                        4: "Resolve degradation or failure-mode uncertainty",
                    }.get(tier, "Resolve scientific uncertainty"),
                }
            )

        state.simulation_requests = planned
        state.dft_queue = [item for item in planned if int(item.get("requested_tier") or 0) >= 2]
        state.log(f"SimulationPlannerAgent planned {len(planned)} simulation requests")
        return state
