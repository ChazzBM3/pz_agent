from __future__ import annotations

from typing import Any

from pz_agent.models.base import BaseSurrogateModel
from pz_agent.models.solubility import ExternalSolubilityScorer, SolubilityScorer
from pz_agent.models.synthesizability import ExternalSynthesizabilityScorer, SynthesizabilityScorer


class SynthSolubilityBaseline(BaseSurrogateModel):
    name = "synth_solubility_baseline"

    def __init__(self, use_external_scores: bool = False):
        self.use_external_scores = use_external_scores
        self.synth_scorer = ExternalSynthesizabilityScorer() if use_external_scores else SynthesizabilityScorer()
        self.sol_scorer = ExternalSolubilityScorer() if use_external_scores else SolubilityScorer()

    def predict(self, molecule: dict[str, Any]) -> dict[str, Any]:
        synth = self.synth_scorer.score(molecule)
        sol = self.sol_scorer.score(molecule)
        return {
            "predicted_synthesizability": synth["value"],
            "predicted_solubility": sol["value"],
            "predicted_priority": None,
            "model": self.name,
            "prediction_provenance": {
                "synthesizability": synth["provenance"],
                "solubility": sol["provenance"],
            },
        }


def get_default_model(use_external_scores: bool = False) -> BaseSurrogateModel:
    return SynthSolubilityBaseline(use_external_scores=use_external_scores)
