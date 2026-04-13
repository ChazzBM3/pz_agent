from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState


class DFTHandoffAgent(BaseAgent):
    name = "dft_handoff"

    def run(self, state: RunState) -> RunState:
        existing_queue = list(state.dft_queue or [])
        if existing_queue:
            state.log(f"DFT handoff received {len(existing_queue)} planned tier-2+ requests")
            return state
        state.dft_queue = list(state.shortlist or [])
        state.log("DFT handoff created fallback placeholder queue")
        return state
