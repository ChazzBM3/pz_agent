from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.chemistry.scaffold import get_phenothiazine_prompt_context
from pz_agent.state import RunState


class LibraryDesignerAgent(BaseAgent):
    name = "library_designer"

    def run(self, state: RunState) -> RunState:
        context = get_phenothiazine_prompt_context()
        engine = self.config.get("generation", {}).get("engine", "genmol")
        state.library_raw = [
            {
                "id": "pz_001",
                "smiles": "PLACEHOLDER_SMILES_1",
                "generation_engine": engine,
                "generation_mode": context["strategy"],
                "sites": ["R1"],
            },
            {
                "id": "pz_002",
                "smiles": "PLACEHOLDER_SMILES_2",
                "generation_engine": engine,
                "generation_mode": context["strategy"],
                "sites": ["R2"],
            },
        ]
        state.log("Library designer produced placeholder GenMol-derived phenothiazine candidates")
        return state
