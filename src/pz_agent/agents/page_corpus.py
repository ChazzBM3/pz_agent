from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.retrieval.page_corpus import assemble_page_corpus_for_candidate
from pz_agent.state import RunState


class PageCorpusAgent(BaseAgent):
    name = "page_corpus"

    def run(self, state: RunState) -> RunState:
        cfg = state.config.get("page_corpus", {}) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            state.log("Page corpus assembly skipped (disabled)")
            return state

        candidates = state.library_clean or []
        page_registry: list[dict] = []
        updated_candidates: list[dict] = []

        for candidate in candidates:
            page_bundle = assemble_page_corpus_for_candidate(candidate)
            enriched = dict(candidate)
            enriched["page_corpus"] = page_bundle
            updated_candidates.append(enriched)
            page_registry.append(page_bundle)

        state.library_clean = updated_candidates
        state.page_registry = page_registry
        write_json(state.run_dir / "page_corpus.json", page_registry)
        state.log(f"Page corpus assembled for {len(updated_candidates)} candidates")
        return state
