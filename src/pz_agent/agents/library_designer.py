from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.chemistry.genmol_import import attach_genmol_provenance, load_external_genmol_candidates
from pz_agent.chemistry.scaffold import get_phenothiazine_prompt_context
from pz_agent.data.d3tales_loader import load_d3tales_csv
from pz_agent.state import RunState


class LibraryDesignerAgent(BaseAgent):
    name = "library_designer"

    def run(self, state: RunState) -> RunState:
        context = get_phenothiazine_prompt_context()
        generation_config = self.config.get("generation", {})
        source_path = generation_config.get("external_genmol_path")
        d3tales_csv_path = generation_config.get("d3tales_csv_path")
        d3tales_limit = generation_config.get("d3tales_limit")

        metadata = {
            "mode": context["strategy"],
            "objective": generation_config.get("prompts", {}).get("objective"),
        }

        if d3tales_csv_path:
            records = load_d3tales_csv(d3tales_csv_path, limit=d3tales_limit)
            state.library_raw = [record.to_candidate() for record in records]
            state.generation_registry = [
                {
                    "source_path": d3tales_csv_path,
                    "engine": "d3tales_csv",
                    "count": len(state.library_raw),
                    "metadata": {
                        **metadata,
                        "source_kind": "real_measurement_demo",
                    },
                }
            ]
            state.log(f"Library designer imported {len(state.library_raw)} D3TaLES candidates for demo run")
            return state

        if source_path:
            imported = load_external_genmol_candidates(source_path)
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
