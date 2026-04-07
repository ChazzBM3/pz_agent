from __future__ import annotations


def get_phenothiazine_prompt_context() -> dict:
    return {
        "scaffold": "phenothiazine",
        "strategy": "genmol_generation",
        "notes": "Initial candidates should come from a generative AI pass using GenMol-style generation constrained to phenothiazine derivatives.",
    }
