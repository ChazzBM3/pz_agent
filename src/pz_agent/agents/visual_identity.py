from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.chemistry.visual_identity import attach_visual_identity_batch
from pz_agent.state import RunState


class VisualIdentityAgent(BaseAgent):
    name = "visual_identity"

    def run(self, state: RunState) -> RunState:
        enabled = bool(state.config.get("visual_identity", {}).get("enabled", True))
        if not enabled:
            state.log("Visual identity stage skipped")
            return state

        image_dir = state.run_dir / "structure_images"
        model = str(state.config.get("visual_identity", {}).get("model", "gemini-2.5-flash"))
        state.library_clean = attach_visual_identity_batch(state.library_clean or [], image_dir, model=model)
        state.visual_registry = [
            item.get("visual_bundle")
            for item in (state.library_clean or [])
            if item.get("visual_bundle")
        ]
        state.log(f"Visual identity prepared {len(state.visual_registry or [])} rendered structure bundles")
        return state
