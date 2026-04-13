from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pz_agent.chemistry.visual_identity import render_candidate_structure_image


COLPALI_HINT = "local_image_similarity"


def _file_signature(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _score_target(query_image_path: str | None, figure: dict[str, Any]) -> float:
    target_path = figure.get("storage_ref")
    query_sig = _file_signature(query_image_path)
    target_sig = _file_signature(target_path)
    if query_sig and target_sig and query_sig[:8] == target_sig[:8]:
        return 1.0

    score = 0.1
    caption = str(figure.get("caption") or "").lower()
    ocr_text = str(figure.get("ocr_text") or "").lower()
    source_path = str(figure.get("source_document_path") or "").lower()
    if any(token in caption for token in ["phenothiazine", "redox", "scheme", "figure"]):
        score += 0.35
    if any(token in ocr_text for token in ["phenothiazine", "compound", "redox"]):
        score += 0.35
    if source_path.endswith(".pdf"):
        score += 0.1
    return min(score, 0.99)


def assemble_page_image_retrieval_for_candidate(candidate: dict[str, Any], artifacts_dir: str | Path, top_k: int = 5) -> dict[str, Any]:
    candidate_id = str(candidate.get("id") or "candidate")
    figure_bundle = candidate.get("figure_corpus") or {}
    image_dir = Path(artifacts_dir) / candidate_id / "queries"
    query_image = render_candidate_structure_image(candidate, image_dir)

    retrieval_targets: list[dict[str, Any]] = []
    for figure in figure_bundle.get("figures") or []:
        retrieval_targets.append(
            {
                "candidate_id": candidate_id,
                "figure_id": figure.get("figure_id"),
                "query_image_path": query_image,
                "target_image_path": figure.get("storage_ref"),
                "source_document_path": figure.get("source_document_path"),
                "caption": figure.get("caption"),
                "ocr_text": figure.get("ocr_text"),
                "score": _score_target(query_image, figure),
                "status": COLPALI_HINT,
            }
        )

    retrieval_targets.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    retrieval_targets = retrieval_targets[:top_k]

    return {
        "candidate_id": candidate_id,
        "query_image_path": query_image,
        "target_count": len(retrieval_targets),
        "targets": retrieval_targets,
        "backend": "local_image_similarity",
        "status": "ok" if retrieval_targets else "empty",
    }
