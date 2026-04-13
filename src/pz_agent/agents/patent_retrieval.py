from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.retrieval.patents import retrieve_patent_evidence_for_candidate
from pz_agent.state import RunState


class PatentRetrievalAgent(BaseAgent):
    name = "patent_retrieval"

    def run(self, state: RunState) -> RunState:
        cfg = state.config.get("patent_retrieval", {}) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            state.log("Patent retrieval skipped (disabled)")
            return state

        count = int(cfg.get("count", 5))
        timeout = int(cfg.get("timeout", 20))
        candidates = state.library_clean or []
        patent_registry: list[dict] = []
        updated_candidates: list[dict] = []

        for candidate in candidates:
            patent_bundle = retrieve_patent_evidence_for_candidate(candidate, count=count, timeout=timeout)
            enriched = dict(candidate)
            enriched["patent_retrieval"] = patent_bundle
            updated_candidates.append(enriched)
            patent_registry.append({"candidate_id": candidate.get("id"), **patent_bundle})

        state.library_clean = updated_candidates
        state.patent_registry = patent_registry
        write_json(state.run_dir / "patent_retrieval.json", patent_registry)
        state.log(f"Patent retrieval prepared query bundles for {len(updated_candidates)} candidates")
        return state
