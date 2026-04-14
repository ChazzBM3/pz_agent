from __future__ import annotations


def get_phenothiazine_prompt_context() -> dict:
    return {
        "scaffold": "phenothiazine",
        "strategy": "genmol_generation",
        "notes": "Initial candidates should come from a generative AI pass using GenMol-style generation constrained to phenothiazine derivatives.",
        "default_bridge_dimensions": [
            "electronic_push_pull",
            "solubilizing_handle",
            "route_modularity",
        ],
        "default_generation_priors": {
            "pt_direct": 0.5,
            "bridge_driven": 0.3,
            "simulation_driven": 0.2,
        },
    }
