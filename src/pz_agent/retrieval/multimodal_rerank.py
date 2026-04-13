from __future__ import annotations

import json
from typing import Any


DEFAULT_GEMMA_MULTIMODAL_PROMPT = (
    "You are evaluating whether a retrieved chemistry page/figure is relevant to a target phenothiazine candidate. "
    "Use the target structure image, candidate identity, source snippet, figure crop path, and caption/OCR placeholders. "
    "Return JSON with keys: match_label, property_relevance, confidence, justification, needs_human_review."
)


def build_gemma_multimodal_prompt(bundle: dict[str, Any]) -> str:
    identity = bundle.get("candidate_identity") or {}
    payload = {
        "task": "multimodal_candidate_rerank",
        "instructions": DEFAULT_GEMMA_MULTIMODAL_PROMPT,
        "candidate": {
            "candidate_id": bundle.get("candidate_id"),
            "iupac_name": identity.get("iupac_name"),
            "scaffold": identity.get("scaffold"),
            "substitution_pattern": identity.get("substitution_pattern"),
            "molecular_formula": identity.get("molecular_formula"),
        },
        "artifacts": {
            "query_image_path": bundle.get("query_image_path"),
            "target_image_path": bundle.get("target_image_path"),
            "caption": bundle.get("caption"),
            "ocr_text": bundle.get("ocr_text"),
            "title": bundle.get("title"),
            "snippet": bundle.get("snippet"),
            "source_url": bundle.get("source_url"),
        },
    }
    return json.dumps(payload, indent=2)


def parse_gemma_multimodal_response(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {
            "match_label": "unparsed",
            "property_relevance": "unknown",
            "confidence": "low",
            "justification": text,
            "needs_human_review": True,
            "status": "parse_failed",
        }

    return {
        "match_label": payload.get("match_label", "unknown"),
        "property_relevance": payload.get("property_relevance", "unknown"),
        "confidence": payload.get("confidence", "unknown"),
        "justification": payload.get("justification"),
        "needs_human_review": bool(payload.get("needs_human_review", False)),
        "status": "ok",
    }


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
        bundle = {
            "bundle_id": f"mm_rerank::{candidate_id}::{idx}",
            "candidate_id": candidate_id,
            "query_image_path": target.get("query_image_path"),
            "target_image_path": target.get("target_image_path"),
            "figure_id": target.get("figure_id"),
            "caption": target.get("caption"),
            "ocr_text": target.get("ocr_text") or None,
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
        bundle["gemma_prompt"] = build_gemma_multimodal_prompt(bundle)
        bundle["gemma_response"] = None
        bundle["gemma_judgment"] = None
        bundles.append(bundle)

    return {
        "candidate_id": candidate_id,
        "bundle_count": len(bundles),
        "bundles": bundles,
        "backend": "gemma_planned",
        "status": "ok" if bundles else "empty",
    }
