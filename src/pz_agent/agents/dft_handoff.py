from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState


class DFTHandoffAgent(BaseAgent):
    name = "dft_handoff"

    def run(self, state: RunState) -> RunState:
        state.dft_queue = list(state.shortlist or [])
        state.log("DFT handoff created placeholder queue")
        return state
