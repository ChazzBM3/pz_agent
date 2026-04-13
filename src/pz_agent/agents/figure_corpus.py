from __future__ import annotations

from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.retrieval.figure_corpus import assemble_figure_corpus_for_candidate
from pz_agent.state import RunState


class FigureCorpusAgent(BaseAgent):
    name = "figure_corpus"

    def run(self, state: RunState) -> RunState:
        cfg = state.config.get("figure_corpus", {}) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            state.log("Figure corpus assembly skipped (disabled)")
            return state

        artifacts_dir = Path(cfg.get("artifacts_dir", state.run_dir / "figure_assets"))
        document_registry = state.document_registry or []
        figure_registry: list[dict] = []
        updated_candidates: list[dict] = []

        for document_bundle in document_registry:
            figure_bundle = assemble_figure_corpus_for_candidate(document_bundle, artifacts_dir=artifacts_dir)
            figure_registry.append(figure_bundle)

        fig_map = {bundle.get("candidate_id"): bundle for bundle in figure_registry}
        for candidate in state.library_clean or []:
            enriched = dict(candidate)
            enriched["figure_corpus"] = fig_map.get(candidate.get("id"), {"candidate_id": candidate.get("id"), "figure_count": 0, "figures": [], "status": "empty"})
            updated_candidates.append(enriched)

        state.library_clean = updated_candidates
        state.figure_registry = figure_registry
        write_json(state.run_dir / "figure_corpus.json", figure_registry)
        state.log(f"Figure corpus scaffold assembled for {len(figure_registry)} candidates")
        return state
