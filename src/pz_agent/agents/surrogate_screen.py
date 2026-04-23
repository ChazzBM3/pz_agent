from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.models.surrogate_registry import get_default_model
from pz_agent.state import RunState


class SurrogateScreenAgent(BaseAgent):
    name = "surrogate_screen"

    def run(self, state: RunState) -> RunState:
        configured_external = bool(self.config.get("screening", {}).get("use_external_scores", False))
        detected_external = any(
            item.get("external_synthesizability") is not None or item.get("external_solubility") is not None
            for item in (state.library_clean or [])
        )
        use_external_scores = configured_external or detected_external
        model = get_default_model(use_external_scores=use_external_scores)
        state.predictions = []
        for item in (state.library_clean or []):
            pred = model.predict(item)
            state.predictions.append({
                **item,
                **pred,
                "id": item["id"],
            })
        if configured_external:
            mode = "external score import with heuristic fallback"
        elif detected_external:
            mode = "auto-detected external score import with heuristic fallback"
        else:
            mode = "internal stub scoring"
        state.log(f"Surrogate screen generated synthesizability and solubility predictions using {mode}")
        return state
