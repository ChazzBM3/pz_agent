from __future__ import annotations

from pathlib import Path
from typing import Any


OCR_HINTS = ("compound", "fig", "figure", "scheme", "phenothiazine", "redox")
CAPTION_HINTS = ("figure", "scheme", "fig.", "graphical abstract")


def _extract_caption_from_document(source_document_path: str | None) -> str | None:
    if not source_document_path:
        return None
    path = Path(source_document_path)
    if not path.exists() or path.suffix.lower() != ".html":
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    lowered = text.lower()
    for hint in CAPTION_HINTS:
        idx = lowered.find(hint)
        if idx >= 0:
            snippet = text[idx : idx + 200].strip().replace("\n", " ")
            return snippet[:160]
    return None


def _extract_ocr_from_figure_asset(storage_ref: str | None, source_document_path: str | None) -> str | None:
    if storage_ref and Path(storage_ref).exists():
        path = Path(storage_ref)
        stem_text = path.stem.replace("_", " ")
        if any(token in stem_text.lower() for token in OCR_HINTS):
            return stem_text
        return f"ocr placeholder from {path.name}"

    if source_document_path and source_document_path.lower().endswith(".pdf"):
        return "ocr placeholder from extracted pdf figure"
    return None


def build_ocr_caption_stub(figure: dict[str, Any]) -> dict[str, Any]:
    figure_id = str(figure.get("figure_id") or "figure")
    source_document = str(figure.get("source_document_path") or "")

    caption_text = figure.get("caption") or _extract_caption_from_document(source_document) or "Caption extraction unavailable"
    ocr_text = figure.get("ocr_text") or _extract_ocr_from_figure_asset(figure.get("storage_ref"), source_document)

    return {
        "figure_id": figure_id,
        "caption_text": caption_text,
        "ocr_text": ocr_text,
        "caption_status": "ok" if caption_text and caption_text != "Caption extraction unavailable" else "missing",
        "ocr_status": "ok" if ocr_text else "missing",
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
