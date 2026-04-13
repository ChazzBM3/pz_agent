from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pz_agent.chemistry.vision_client import DEFAULT_VISION_MODEL, extract_visual_identity_with_gemini, gemini_vision_available


DEFAULT_GEMMA_MULTIMODAL_PROMPT = (
    "You are evaluating whether a retrieved chemistry page/figure is relevant to a target phenothiazine candidate. "
    "Use the target structure image, candidate identity, source snippet, figure crop path, and caption/OCR context. "
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
            "retrieval_score": bundle.get("retrieval_score"),
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


def _fallback_multimodal_judgment(bundle: dict[str, Any], reason: str) -> dict[str, Any]:
    score = float(bundle.get("retrieval_score") or 0.0)
    caption = str(bundle.get("caption") or "").lower()
    ocr_text = str(bundle.get("ocr_text") or "").lower()
    text = f"{caption} {ocr_text}"
    if score >= 0.75 or "phenothiazine" in text:
        match_label = "analog"
        confidence = "medium"
    elif score >= 0.4:
        match_label = "possible"
        confidence = "low"
    else:
        match_label = "unknown"
        confidence = "low"
    property_relevance = "redox" if "redox" in text else "unknown"
    return {
        "match_label": match_label,
        "property_relevance": property_relevance,
        "confidence": confidence,
        "justification": f"fallback multimodal judgment ({reason})",
        "needs_human_review": True,
        "status": "fallback",
    }


def invoke_gemma_multimodal(bundle: dict[str, Any], model: str = DEFAULT_VISION_MODEL, timeout: int = 120) -> dict[str, Any]:
    query_image_path = bundle.get("query_image_path")
    target_image_path = bundle.get("target_image_path")
    available, reason = gemini_vision_available()
    if not available:
        return {
            "gemma_response": None,
            "gemma_judgment": _fallback_multimodal_judgment(bundle, reason or "gemini_unavailable"),
            "backend_status": reason or "gemini_unavailable",
            "backend": "fallback",
        }

    if not query_image_path or not target_image_path:
        return {
            "gemma_response": None,
            "gemma_judgment": _fallback_multimodal_judgment(bundle, "missing_image_paths"),
            "backend_status": "missing_image_paths",
            "backend": "fallback",
        }

    prompt = build_gemma_multimodal_prompt(bundle)
    target_result = extract_visual_identity_with_gemini(target_image_path, prompt=prompt, model=model, timeout=timeout)
    status = target_result.get("vision_status")
    if status != "gemini_ok":
        return {
            "gemma_response": target_result.get("raw_output"),
            "gemma_judgment": _fallback_multimodal_judgment(bundle, str(status)),
            "backend_status": status,
            "backend": "fallback",
        }

    visual_identity = target_result.get("visual_identity") or {}
    response_text = json.dumps(visual_identity)
    return {
        "gemma_response": response_text,
        "gemma_judgment": parse_gemma_multimodal_response(response_text),
        "backend_status": status,
        "backend": model,
    }


def assemble_multimodal_rerank_for_candidate(candidate: dict[str, Any], invoke_live: bool = True, model: str = DEFAULT_VISION_MODEL, timeout: int = 120) -> dict[str, Any]:
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
            "retrieval_score": target.get("score"),
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
            "backend": "gemma_live" if invoke_live else "gemma_planned",
            "status": "ready_for_multimodal_rerank",
        }
        bundle["gemma_prompt"] = build_gemma_multimodal_prompt(bundle)
        bundle["gemma_response"] = None
        bundle["gemma_judgment"] = None
        if invoke_live:
            result = invoke_gemma_multimodal(bundle, model=model, timeout=timeout)
            bundle["gemma_response"] = result.get("gemma_response")
            bundle["gemma_judgment"] = result.get("gemma_judgment")
            bundle["backend_status"] = result.get("backend_status")
            bundle["backend"] = result.get("backend")
        bundles.append(bundle)

    return {
        "candidate_id": candidate_id,
        "bundle_count": len(bundles),
        "bundles": bundles,
        "backend": "gemma_live" if invoke_live else "gemma_planned",
        "status": "ok" if bundles else "empty",
    }
