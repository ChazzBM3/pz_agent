from __future__ import annotations

from pz_agent.agents.generation import _build_dossier



def test_build_dossier_contains_enriched_scaffold_metadata() -> None:
    candidate = {
        "id": "cand_1",
        "smiles": "CC",
        "sites": ["R1", "R2"],
        "identity": {
            "scaffold": "phenothiazine",
            "decoration_tokens": ["OMe"],
            "positional_tokens": ["R1 para OMe"],
            "attachment_summary": ["phenothiazine_core+OMe"],
            "substituent_fragments": ["frag:OMe"],
            "substitution_pattern": "mono_substituted",
            "electronic_bias": "electron_donating_skew",
        },
        "structure_expansion": {"query_hints": ["phenothiazine redox"]},
    }
    prediction = {"predicted_solubility": 0.7, "predicted_synthesizability": 0.8, "prediction_uncertainty": 0.2}
    ranked_row = {"predicted_priority": 1.1}
    portfolio_assignment = {"proposal_bucket": "bridge", "selection_reason": "portfolio_selector::bridge", "bridge_relevance": 1.0}
    dossier = _build_dossier(candidate, prediction, ranked_row, portfolio_assignment)
    scaffold_meta = dossier["scaffold_metadata"]
    assert scaffold_meta["attachment_summary"] == ["phenothiazine_core+OMe"]
    assert scaffold_meta["substituent_fragments"] == ["frag:OMe"]
    assert scaffold_meta["substitution_pattern"] == "mono_substituted"
    assert len(scaffold_meta["site_assignments"]) == 2
    assert dossier["portfolio_metadata"]["proposal_bucket"] == "bridge"
    assert dossier["bridge_hypothesis"]["source_family"] == "chem_qn::quinone_abstract"
