from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pz_agent.io import ensure_dir


FIGURE_HINT_TOKENS = ("figure", "scheme", "graphical abstract", "supplementary", "chart")
HTML_IMAGE_HINTS = ("figure", "scheme", "graphical", "img")


PNG_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x02\x00\x01"
    b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _safe_figure_id(candidate_id: str, document_path: str | None, title: str | None, index: int) -> str:
    key = f"{candidate_id}::{document_path or title or 'doc'}::{index}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"figure::{candidate_id}::{digest}"


def _extract_html_image_count(document_path: str | None) -> int:
    if not document_path:
        return 0
    path = Path(document_path)
    if not path.exists():
        return 0
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return 0
    img_count = text.count("<img")
    hint_hits = sum(text.count(token) for token in HTML_IMAGE_HINTS)
    return max(img_count, min(3, hint_hits))


def _materialize_placeholder_crop(storage_ref: str | None) -> None:
    if not storage_ref:
        return
    path = Path(storage_ref)
    ensure_dir(path.parent)
    if not path.exists():
        path.write_bytes(PNG_PIXEL)


def infer_figure_candidates(document: dict[str, Any], max_figures: int = 3) -> list[dict[str, Any]]:
    candidate_id = str(document.get("candidate_id") or "candidate")
    title = str(document.get("title") or "")
    snippet = str(document.get("snippet") or "")
    text = f"{title} {snippet}".lower()
    figure_count = 1 if any(token in text for token in FIGURE_HINT_TOKENS) else 0

    if document.get("document_kind") == "pdf" and document.get("fetch_status") == "fetched":
        figure_count = max(figure_count, 1)
    elif document.get("document_kind") == "html" and document.get("fetch_status") == "fetched":
        figure_count = max(figure_count, _extract_html_image_count(document.get("local_artifact_path")))

    figure_count = min(max_figures, max(figure_count, 1 if document.get("trusted_host") else 0))

    figures: list[dict[str, Any]] = []
    for idx in range(figure_count):
        figure_id = _safe_figure_id(candidate_id, document.get("local_artifact_path"), title, idx)
        figures.append(
            {
                "figure_id": figure_id,
                "candidate_id": candidate_id,
                "source_document_path": document.get("local_artifact_path"),
                "source_metadata_path": document.get("metadata_path"),
                "page_number": None,
                "caption": None,
                "figure_type": "unknown",
                "source_url": document.get("url"),
                "storage_ref": None,
                "crop_status": "pending",
                "extraction_backend": "local_scaffold",
            }
        )
    return figures


def assemble_figure_corpus_for_candidate(document_bundle: dict[str, Any], artifacts_dir: str | Path) -> dict[str, Any]:
    candidate_id = str(document_bundle.get("candidate_id") or "candidate")
    figures: list[dict[str, Any]] = []
    for document in document_bundle.get("documents") or []:
        document_figures = infer_figure_candidates(document)
        figure_dir = Path(artifacts_dir) / candidate_id / "figures"
        ensure_dir(figure_dir)
        for item in document_figures:
            crop_name = item["figure_id"].replace("::", "_") + ".png"
            item["storage_ref"] = str(figure_dir / crop_name)
            _materialize_placeholder_crop(item["storage_ref"])
            item["crop_status"] = "extracted"
            figures.append(item)

    return {
        "candidate_id": candidate_id,
        "figure_count": len(figures),
        "figures": figures,
        "status": "ok" if figures else "empty",
    }
