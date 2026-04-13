from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.retrieval.ocr_caption import assemble_ocr_caption_for_candidate
from pz_agent.state import RunState


class OCRCaptionAgent(BaseAgent):
    name = "ocr_caption"

    def run(self, state: RunState) -> RunState:
        cfg = state.config.get("ocr_caption", {}) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            state.log("OCR/caption extraction skipped (disabled)")
            return state

        registry: list[dict] = []
        updated_candidates: list[dict] = []
        fig_map = {bundle.get("candidate_id"): bundle for bundle in (state.figure_registry or [])}

        for candidate in state.library_clean or []:
            ocr_bundle = assemble_ocr_caption_for_candidate(fig_map.get(candidate.get("id"), {"candidate_id": candidate.get("id"), "figures": []}), artifacts_dir=state.run_dir / "ocr_caption")
            registry.append(ocr_bundle)
            enriched = dict(candidate)
            enriched["ocr_caption"] = ocr_bundle
            fig_bundle = enriched.get("figure_corpus") or {}
            ocr_map = {entry.get("figure_id"): entry for entry in (ocr_bundle.get("entries") or [])}
            updated_figures = []
            for figure in fig_bundle.get("figures") or []:
                figure = dict(figure)
                extra = ocr_map.get(figure.get("figure_id"), {})
                if extra:
                    figure["caption"] = extra.get("caption_text")
                    figure["ocr_text"] = extra.get("ocr_text")
                updated_figures.append(figure)
            if fig_bundle:
                enriched["figure_corpus"] = {**fig_bundle, "figures": updated_figures}
            updated_candidates.append(enriched)

        state.library_clean = updated_candidates
        state.ocr_registry = registry
        write_json(state.run_dir / "ocr_caption.json", registry)
        extracted_count = sum(1 for bundle in registry for entry in (bundle.get("entries") or []) if entry.get("ocr_status") == "ok" or entry.get("caption_status") == "ok")
        state.log(f"OCR/caption extraction prepared for {len(registry)} candidates, populated {extracted_count} figure text entries")
        return state
