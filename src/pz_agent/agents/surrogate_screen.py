from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.models.surrogate_registry import get_default_model
from pz_agent.state import RunState


class SurrogateScreenAgent(BaseAgent):
    name = "surrogate_screen"

    def run(self, state: RunState) -> RunState:
        model = get_default_model()
        state.predictions = []
        for item in (state.library_clean or []):
            pred = model.predict(item)
            state.predictions.append({
                "id": item["id"],
                **pred,
            })
        state.log("Surrogate screen added placeholder synthesizability and solubility predictions")
        return state
