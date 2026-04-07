from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState


class SurrogateScreenAgent(BaseAgent):
    name = "surrogate_screen"

    def run(self, state: RunState) -> RunState:
        state.predictions = [
            {
                "id": item["id"],
                "predicted_redox_score": None,
                "predicted_stability_score": None,
                "model": "baseline_placeholder",
            }
            for item in (state.library_clean or [])
        ]
        state.log("Surrogate screen added placeholder predictions")
        return state
