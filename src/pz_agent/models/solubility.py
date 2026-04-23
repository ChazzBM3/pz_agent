from __future__ import annotations

from typing import Any

from pz_agent.models.provenance import PredictionProvenance


class SolubilityScorer:
    name = "solubility_heuristic"
    version = "0.1"

    def score(self, molecule: dict[str, Any]) -> dict[str, Any]:
        smiles = str(molecule.get("smiles", ""))
        aromatic_penalty = smiles.count("=") * 0.03
        hetero_bonus = (smiles.count("N") + smiles.count("O") + smiles.count("S")) * 0.04
        raw = 0.45 + hetero_bonus - aromatic_penalty
        value = max(0.0, min(1.0, raw)) if smiles else None
        return {
            "value": value,
            "provenance": PredictionProvenance(
                model_name=self.name,
                model_version=self.version,
                source_type="internal_heuristic",
                confidence=0.2 if value is not None else None,
                units={"solubility": "relative_score_0_to_1"},
                notes="Very rough heuristic using simple SMILES token counts; replace with real QSPR or external model.",
            ).to_dict(),
        }


class ExternalSolubilityScorer(SolubilityScorer):
    name = "solubility_external_import"

    def score(self, molecule: dict[str, Any]) -> dict[str, Any]:
        value = molecule.get("external_solubility")
        if value is None:
            fallback = super().score(molecule)
            fallback["provenance"]["notes"] = (
                "External solubility score missing; fell back to internal heuristic."
            )
            return fallback
        return {
            "value": value,
            "provenance": PredictionProvenance(
                model_name=self.name,
                model_version=self.version,
                source_type="external_import",
                confidence=None,
                units={"solubility": molecule.get("external_solubility_units", "unknown")},
                notes="Imported from external score payload if present.",
            ).to_dict(),
        }
