from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState


class LibraryDesignerAgent(BaseAgent):
    name = "library_designer"

    def run(self, state: RunState) -> RunState:
        state.library_raw = [
            {"id": "pz_001", "smiles": "PLACEHOLDER_SMILES_1", "sites": ["R1"]},
            {"id": "pz_002", "smiles": "PLACEHOLDER_SMILES_2", "sites": ["R2"]},
        ]
        state.log("Library designer produced placeholder phenothiazine candidates")
        return state
