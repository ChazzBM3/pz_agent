from __future__ import annotations

from typing import Any

from pz_agent.models.base import BaseSurrogateModel


class SynthSolubilityBaseline(BaseSurrogateModel):
    name = "synth_solubility_baseline"

    def predict(self, molecule: dict[str, Any]) -> dict[str, Any]:
        return {
            "predicted_synthesizability": None,
            "predicted_solubility": None,
            "predicted_priority": None,
            "model": self.name,
        }


def get_default_model() -> BaseSurrogateModel:
    return SynthSolubilityBaseline()
