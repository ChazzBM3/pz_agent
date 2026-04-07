from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.chemistry.genmol_import import attach_genmol_provenance, load_external_genmol_candidates
from pz_agent.chemistry.scaffold import get_phenothiazine_prompt_context
from pz_agent.state import RunState


class LibraryDesignerAgent(BaseAgent):
    name = "library_designer"

    def run(self, state: RunState) -> RunState:
        context = get_phenothiazine_prompt_context()
        source_path = self.config.get("generation", {}).get("external_genmol_path")
        if source_path:
            imported = load_external_genmol_candidates(source_path)
            metadata = {
                "mode": context["strategy"],
                "objective": self.config.get("generation", {}).get("prompts", {}).get("objective"),
            }
            state.library_raw = attach_genmol_provenance(
                imported,
                source_path=source_path,
                run_metadata=metadata,
            )
            state.generation_registry = [
                {
                    "source_path": source_path,
                    "engine": "genmol_external",
                    "count": len(state.library_raw),
                    "metadata": metadata,
                }
            ]
            state.log(f"Library designer imported {len(state.library_raw)} external GenMol candidates")
            return state

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
        state.generation_registry = [
            {
                "source_path": None,
                "engine": engine,
                "count": len(state.library_raw),
                "metadata": {"mode": context["strategy"]},
            }
        ]
        state.log("Library designer produced placeholder GenMol-derived phenothiazine candidates")
        return state
