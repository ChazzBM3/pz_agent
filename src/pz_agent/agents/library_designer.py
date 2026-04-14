from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.chemistry.genmol_import import attach_genmol_provenance, load_external_genmol_candidates
from pz_agent.chemistry.scaffold import get_phenothiazine_prompt_context
from pathlib import Path

from pz_agent.data.d3tales_loader import load_d3tales_csv
from pz_agent.kg.generation_priors import derive_generation_priors_from_graph
from pz_agent.state import RunState


class LibraryDesignerAgent(BaseAgent):
    name = "library_designer"

    def run(self, state: RunState) -> RunState:
        context = get_phenothiazine_prompt_context()
        generation_config = self.config.get("generation", {})
        source_path = generation_config.get("external_genmol_path")
        d3tales_csv_path = generation_config.get("d3tales_csv_path")
        d3tales_limit = generation_config.get("d3tales_limit")
        d3tales_phenothiazine_only = bool(generation_config.get("d3tales_phenothiazine_only", False))

        prior_bundle = derive_generation_priors_from_graph(Path.cwd())
        metadata = {
            "mode": context["strategy"],
            "objective": generation_config.get("prompts", {}).get("objective"),
            "generation_priors": prior_bundle.get("generation_priors", context.get("default_generation_priors", {})),
            "bridge_dimensions": prior_bundle.get("bridge_dimensions", context.get("default_bridge_dimensions", [])),
            "failure_bias": prior_bundle.get("failure_bias", []),
            "prior_source": prior_bundle.get("source", "default"),
            "proposal_rationale": "PT-centered generation with live KG-derived bridge and simulation priors.",
        }

        if d3tales_csv_path:
            records = load_d3tales_csv(
                d3tales_csv_path,
                limit=d3tales_limit,
                phenothiazine_only=d3tales_phenothiazine_only,
            )
            state.library_raw = [
                {
                    **record.to_candidate(),
                    "proposal_prior": {
                        "proposal_mode": "pt_direct_seed",
                        "generation_priors": metadata["generation_priors"],
                        "bridge_dimensions": metadata["bridge_dimensions"],
                        "failure_bias": metadata["failure_bias"],
                        "prior_source": metadata["prior_source"],
                    },
                }
                for record in records
            ]
            state.generation_registry = [
                {
                    "source_path": d3tales_csv_path,
                    "engine": "d3tales_csv",
                    "count": len(state.library_raw),
                    "metadata": {
                        **metadata,
                        "source_kind": "real_measurement_demo",
                        "phenothiazine_only": d3tales_phenothiazine_only,
                    },
                }
            ]
            state.log(f"Library designer imported {len(state.library_raw)} D3TaLES candidates for demo run")
            return state

        if source_path:
            imported = load_external_genmol_candidates(source_path)
            state.library_raw = [
                {
                    **item,
                    "proposal_prior": {
                        "proposal_mode": "external_seed_with_bridge_priors",
                        "generation_priors": metadata["generation_priors"],
                        "bridge_dimensions": metadata["bridge_dimensions"],
                        "failure_bias": metadata["failure_bias"],
                        "prior_source": metadata["prior_source"],
                    },
                }
                for item in attach_genmol_provenance(
                    imported,
                    source_path=source_path,
                    run_metadata=metadata,
                )
            ]
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
                "proposal_prior": {
                    "proposal_mode": "bridge_driven_placeholder",
                    "generation_priors": metadata["generation_priors"],
                    "bridge_dimensions": metadata["bridge_dimensions"],
                    "failure_bias": metadata["failure_bias"],
                    "prior_source": metadata["prior_source"],
                },
            },
            {
                "id": "pz_002",
                "smiles": "PLACEHOLDER_SMILES_2",
                "generation_engine": engine,
                "generation_mode": context["strategy"],
                "sites": ["R2"],
                "proposal_prior": {
                    "proposal_mode": "simulation_driven_placeholder",
                    "generation_priors": metadata["generation_priors"],
                    "bridge_dimensions": metadata["bridge_dimensions"],
                    "failure_bias": metadata["failure_bias"],
                    "prior_source": metadata["prior_source"],
                },
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
