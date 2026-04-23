from __future__ import annotations

from typing import Any

from pz_agent.models.provenance import PredictionProvenance


class SynthesizabilityScorer:
    name = "synthesizability_heuristic"
    version = "0.1"

    def score(self, molecule: dict[str, Any]) -> dict[str, Any]:
        smiles = str(molecule.get("smiles", ""))
        value = max(0.0, min(1.0, 1.0 - (len(smiles) / 120.0))) if smiles else None
        return {
            "value": value,
            "provenance": PredictionProvenance(
                model_name=self.name,
                model_version=self.version,
                source_type="internal_heuristic",
                confidence=0.2 if value is not None else None,
                notes="Very rough heuristic based on string-length proxy; replace with real synthesizability model.",
            ).to_dict(),
        }


class ExternalSynthesizabilityScorer(SynthesizabilityScorer):
    name = "synthesizability_external_import"

    def score(self, molecule: dict[str, Any]) -> dict[str, Any]:
        value = molecule.get("external_synthesizability")
        if value is None:
            fallback = super().score(molecule)
            fallback["provenance"]["notes"] = (
                "External synthesizability score missing; fell back to internal heuristic."
            )
            return fallback
        return {
            "value": value,
            "provenance": PredictionProvenance(
                model_name=self.name,
                model_version=self.version,
                source_type="external_import",
                confidence=None,
                notes="Imported from external score payload if present.",
            ).to_dict(),
        }
