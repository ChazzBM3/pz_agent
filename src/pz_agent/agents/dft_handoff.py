from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState


class DFTHandoffAgent(BaseAgent):
    name = "dft_handoff"

    def run(self, state: RunState) -> RunState:
        shortlist = list(state.shortlist or [])
        shortlist.sort(
            key=lambda item: (
                -float(item.get("predicted_priority_literature_adjusted", item.get("predicted_priority", 0.0)) or 0.0),
                -float(item.get("ranking_rationale", {}).get("belief_state", {}).get("transferability_score", 0.0) or 0.0),
                -float(item.get("ranking_rationale", {}).get("belief_state", {}).get("simulation_support", 0.0) or 0.0),
                item.get("id", ""),
            )
        )
        state.dft_queue = shortlist
        state.log("DFT handoff prioritized shortlist using literature-adjusted score, bridge belief state, and simulation support")
        return state
