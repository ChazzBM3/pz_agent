from __future__ import annotations

from typing import Any


def assemble_multimodal_rerank_for_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(candidate.get("id") or "candidate")
    retrieval_bundle = candidate.get("page_image_retrieval") or {}
    document_bundle = candidate.get("document_fetch") or {}
    identity = candidate.get("identity") or {}

    doc_map = {doc.get("local_artifact_path"): doc for doc in (document_bundle.get("documents") or [])}

    bundles: list[dict[str, Any]] = []
    for idx, target in enumerate(retrieval_bundle.get("targets") or []):
        source_document_path = target.get("source_document_path")
        source_doc = doc_map.get(source_document_path, {})
        bundles.append(
            {
                "bundle_id": f"mm_rerank::{candidate_id}::{idx}",
                "candidate_id": candidate_id,
                "query_image_path": target.get("query_image_path"),
                "target_image_path": target.get("target_image_path"),
                "figure_id": target.get("figure_id"),
                "caption": target.get("caption"),
                "source_document_path": source_document_path,
                "source_metadata_path": source_doc.get("metadata_path"),
                "source_url": source_doc.get("url"),
                "snippet": source_doc.get("snippet"),
                "title": source_doc.get("title"),
                "candidate_identity": {
                    "iupac_name": identity.get("iupac_name"),
                    "scaffold": identity.get("scaffold") or identity.get("core_assumption"),
                    "substitution_pattern": identity.get("substitution_pattern"),
                    "molecular_formula": identity.get("molecular_formula"),
                },
                "backend": "gemma_planned",
                "status": "ready_for_multimodal_rerank",
            }
        )

    return {
        "candidate_id": candidate_id,
        "bundle_count": len(bundles),
        "bundles": bundles,
        "backend": "gemma_planned",
        "status": "ok" if bundles else "empty",
    }
