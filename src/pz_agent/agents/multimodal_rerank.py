from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.retrieval.multimodal_rerank import assemble_multimodal_rerank_for_candidate, parse_gemma_multimodal_response
from pz_agent.state import RunState


class MultimodalRerankAgent(BaseAgent):
    name = "multimodal_rerank"

    def run(self, state: RunState) -> RunState:
        cfg = state.config.get("multimodal_rerank", {}) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            state.log("Multimodal rerank bundle assembly skipped (disabled)")
            return state

        rerank_registry: list[dict] = []
        updated_candidates: list[dict] = []

        for candidate in state.library_clean or []:
            rerank_bundle = assemble_multimodal_rerank_for_candidate(candidate)
            for bundle in rerank_bundle.get("bundles") or []:
                response_text = bundle.get("gemma_response")
                if isinstance(response_text, str) and response_text.strip():
                    bundle["gemma_judgment"] = parse_gemma_multimodal_response(response_text)
            enriched = dict(candidate)
            enriched["multimodal_rerank"] = rerank_bundle
            updated_candidates.append(enriched)
            rerank_registry.append(rerank_bundle)

        state.library_clean = updated_candidates
        state.multimodal_registry = rerank_registry
        write_json(state.run_dir / "multimodal_rerank.json", rerank_registry)
        state.log(f"Multimodal rerank bundles prepared for {len(rerank_registry)} candidates")
        return state
