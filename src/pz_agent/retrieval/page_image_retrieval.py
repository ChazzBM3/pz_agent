from __future__ import annotations

from pathlib import Path
from typing import Any

from pz_agent.chemistry.visual_identity import render_candidate_structure_image


COLPALI_HINT = "placeholder_colpali_ready"


def assemble_page_image_retrieval_for_candidate(candidate: dict[str, Any], artifacts_dir: str | Path) -> dict[str, Any]:
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
                "status": COLPALI_HINT,
            }
        )

    return {
        "candidate_id": candidate_id,
        "query_image_path": query_image,
        "target_count": len(retrieval_targets),
        "targets": retrieval_targets,
        "backend": "colpali_planned",
        "status": "ok" if retrieval_targets else "empty",
    }
