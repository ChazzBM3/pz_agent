from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.chemistry.descriptors import compute_basic_descriptors
from pz_agent.chemistry.standardize import standardize_candidates
from pz_agent.state import RunState


class StandardizerAgent(BaseAgent):
    name = "standardizer"

    def run(self, state: RunState) -> RunState:
        state.library_clean = standardize_candidates(state.library_raw or [])
        state.descriptors = compute_basic_descriptors(state.library_clean)
        state.log("Standardizer generated placeholder clean library and descriptors")
        return state
