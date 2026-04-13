from __future__ import annotations

from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.retrieval.document_fetch import assemble_document_artifacts_for_candidate
from pz_agent.state import RunState


class DocumentFetchAgent(BaseAgent):
    name = "document_fetch"

    def run(self, state: RunState) -> RunState:
        cfg = state.config.get("document_fetch", {}) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            state.log("Document fetch enrichment skipped (disabled)")
            return state

        artifacts_dir = Path(cfg.get("artifacts_dir", state.run_dir / "page_assets"))
        page_registry = state.page_registry or []
        document_registry: list[dict] = []

        for page_bundle in page_registry:
            document_bundle = assemble_document_artifacts_for_candidate(page_bundle, artifacts_dir=artifacts_dir)
            document_registry.append(document_bundle)

        updated_candidates: list[dict] = []
        doc_map = {bundle.get("candidate_id"): bundle for bundle in document_registry}
        for candidate in state.library_clean or []:
            enriched = dict(candidate)
            enriched["document_fetch"] = doc_map.get(candidate.get("id"), {"candidate_id": candidate.get("id"), "document_count": 0, "documents": [], "status": "empty"})
            updated_candidates.append(enriched)

        state.library_clean = updated_candidates
        state.document_registry = document_registry
        write_json(state.run_dir / "document_fetch.json", document_registry)
        state.log(f"Document artifact metadata prepared for {len(document_registry)} candidates")
        return state
