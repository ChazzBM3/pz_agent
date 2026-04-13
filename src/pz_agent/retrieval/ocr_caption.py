from __future__ import annotations

from pathlib import Path
from typing import Any


OCR_HINTS = ("compound", "fig", "figure", "scheme", "phenothiazine", "redox")


def build_ocr_caption_stub(figure: dict[str, Any]) -> dict[str, Any]:
    figure_id = str(figure.get("figure_id") or "figure")
    source_document = str(figure.get("source_document_path") or "")
    caption = figure.get("caption")

    inferred_caption = caption or "Caption extraction pending"
    inferred_ocr = None
    if any(token in source_document.lower() for token in ["pdf", "figure", "scheme"]):
        inferred_ocr = "OCR extraction pending for likely figure-bearing source"

    return {
        "figure_id": figure_id,
        "caption_text": inferred_caption,
        "ocr_text": inferred_ocr,
        "caption_status": "pending",
        "ocr_status": "pending",
    }


def assemble_ocr_caption_for_candidate(figure_bundle: dict[str, Any], artifacts_dir: str | Path) -> dict[str, Any]:
    candidate_id = str(figure_bundle.get("candidate_id") or "candidate")
    entries = [build_ocr_caption_stub(figure) for figure in (figure_bundle.get("figures") or [])]
    return {
        "candidate_id": candidate_id,
        "entry_count": len(entries),
        "entries": entries,
        "status": "ok" if entries else "empty",
    }
