from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState


class StandardizerAgent(BaseAgent):
    name = "standardizer"

    def run(self, state: RunState) -> RunState:
        state.library_clean = state.library_raw or []
        state.descriptors = [
            {"id": item["id"], "mw": None, "logp": None, "sa_score": None}
            for item in state.library_clean
        ]
        state.log("Standardizer generated placeholder clean library and descriptors")
        return state
