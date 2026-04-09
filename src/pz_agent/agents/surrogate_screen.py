from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.models.surrogate_registry import get_default_model
from pz_agent.state import RunState


class SurrogateScreenAgent(BaseAgent):
    name = "surrogate_screen"

    def run(self, state: RunState) -> RunState:
        use_external_scores = bool(self.config.get("screening", {}).get("use_external_scores", False))
        model = get_default_model(use_external_scores=use_external_scores)
        state.predictions = []
        for item in (state.library_clean or []):
            pred = model.predict(item)
            state.predictions.append({
                **item,
                **pred,
                "id": item["id"],
            })
        mode = "external score import" if use_external_scores else "internal stub scoring"
        state.log(f"Surrogate screen generated synthesizability and solubility predictions using {mode}")
        return state
