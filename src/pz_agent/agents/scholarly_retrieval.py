from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.retrieval.openalex_expanded import retrieve_openalex_evidence_for_candidate
from pz_agent.state import RunState


class ScholarlyRetrievalAgent(BaseAgent):
    name = "scholarly_retrieval"

    def run(self, state: RunState) -> RunState:
        cfg = state.config.get("scholarly_retrieval", {}) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            state.log("Scholarly retrieval skipped (disabled)")
            return state

        count = int(cfg.get("count", 5))
        candidates = state.library_clean or []
        scholarly_registry: list[dict] = []
        updated_candidates: list[dict] = []

        for candidate in candidates:
            scholarly_bundle = retrieve_openalex_evidence_for_candidate(candidate, count=count)
            enriched = dict(candidate)
            enriched["scholarly_retrieval"] = scholarly_bundle
            updated_candidates.append(enriched)
            scholarly_registry.append({"candidate_id": candidate.get("id"), **scholarly_bundle})

        state.library_clean = updated_candidates
        state.scholarly_registry = scholarly_registry
        write_json(state.run_dir / "scholarly_retrieval.json", scholarly_registry)
        state.log(f"Scholarly retrieval prepared OpenAlex bundles for {len(updated_candidates)} candidates")
        return state
