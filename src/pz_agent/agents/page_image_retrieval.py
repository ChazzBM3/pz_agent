from __future__ import annotations

from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.retrieval.page_image_retrieval import assemble_page_image_retrieval_for_candidate
from pz_agent.state import RunState


class PageImageRetrievalAgent(BaseAgent):
    name = "page_image_retrieval"

    def run(self, state: RunState) -> RunState:
        cfg = state.config.get("page_image_retrieval", {}) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            state.log("Page-image retrieval skipped (disabled)")
            return state

        artifacts_dir = Path(cfg.get("artifacts_dir", state.run_dir / "page_image_retrieval"))
        retrieval_registry: list[dict] = []
        updated_candidates: list[dict] = []

        for candidate in state.library_clean or []:
            retrieval_bundle = assemble_page_image_retrieval_for_candidate(candidate, artifacts_dir=artifacts_dir)
            enriched = dict(candidate)
            enriched["page_image_retrieval"] = retrieval_bundle
            updated_candidates.append(enriched)
            retrieval_registry.append(retrieval_bundle)

        state.library_clean = updated_candidates
        state.page_image_registry = retrieval_registry
        write_json(state.run_dir / "page_image_retrieval.json", retrieval_registry)
        state.log(f"Page-image retrieval scaffold prepared for {len(retrieval_registry)} candidates")
        return state
