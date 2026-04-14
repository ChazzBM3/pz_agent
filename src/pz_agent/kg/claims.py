from __future__ import annotations

from typing import Any
import hashlib
import math


def stable_node_id(prefix: str, *parts: str | None) -> str:
    key = "::".join((part or "") for part in parts if part is not None).strip() or prefix
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}::{digest}"


def stable_paper_id(title: str | None = None, url: str | None = None) -> str:
    return stable_node_id("paper", url or title or "unknown-paper")


def build_search_query_node(candidate_id: str, index: int, query: str, status: str | None = None) -> dict[str, Any]:
    return {
        "id": f"query::{candidate_id}::{index}",
        "type": "SearchQuery",
        "attrs": {
            "candidate_id": candidate_id,
            "query": query,
            "status": status,
        },
    }


def infer_claim_semantics(note: dict[str, Any]) -> list[dict[str, Any]]:
    signals = note.get("signals", {})
    evidence_tier = str(note.get("evidence_tier") or "candidate")
    subject_type = "scaffold" if evidence_tier in {"scaffold", "general_review"} else "molecule"
    semantics: list[dict[str, Any]] = [
        {
            "key": "candidate_evidence",
            "subject_type": subject_type,
            "predicate": "candidate_evidence",
            "polarity": "support",
            "property_name": None,
            "evidence_tier": evidence_tier,
        }
    ]

    property_support = dict(signals.get("property_support") or {})
    for property_name, support_count in sorted(property_support.items()):
        polarity = "contradiction" if property_name == "instability" else "support"
        predicate = "warns_instability" if property_name == "instability" else "supports_property"
        semantics.append(
            {
                "key": property_name,
                "subject_type": "molecule",
                "predicate": predicate,
                "polarity": polarity,
                "property_name": property_name,
                "evidence_tier": evidence_tier,
                "support_count": int(support_count or 0),
            }
        )
    return semantics



def build_claim_nodes(note: dict[str, Any]) -> list[dict[str, Any]]:
    signals = note.get("signals", {})
    support_mix = dict(note.get("support_mix") or {})
    nodes = []
    for semantics in infer_claim_semantics(note):
        claim_key = semantics["key"]
        nodes.append(
            {
                "id": f"claim::{note['candidate_id']}::{claim_key}",
                "type": "Claim",
                "attrs": {
                    "candidate_id": note["candidate_id"],
                    "status": note.get("status"),
                    "summary": note.get("summary"),
                    "signals": signals,
                    "support_mix": support_mix,
                    "web_search_enabled": note.get("web_search_enabled"),
                    **semantics,
                },
            }
        )
    return nodes


def build_evidence_hit_node(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": evidence["id"],
        "type": "EvidenceHit",
        "attrs": dict(evidence),
    }


def build_condition_node(kind: str, value: str) -> dict[str, Any]:
    return {
        "id": stable_node_id("condition", kind, value),
        "type": "Condition",
        "attrs": {
            "kind": kind,
            "value": value,
        },
    }



def build_property_node(property_name: str) -> dict[str, Any]:
    return {
        "id": f"property::{property_name}",
        "type": "Property",
        "attrs": {
            "name": property_name,
        },
    }



def build_paper_node_from_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    title = evidence.get("title")
    url = evidence.get("url")
    return {
        "id": stable_paper_id(title=title, url=url),
        "type": "Paper",
        "attrs": {
            "title": title,
            "url": url,
            "snippet": evidence.get("snippet"),
            "source": evidence.get("provenance", {}).get("source_type") or evidence.get("kind"),
        },
    }



def _belief_confidence(support_score: float, contradiction_score: float, direct_pt_support: float, simulation_support: float) -> float:
    value = 1.0 * support_score - 1.1 * contradiction_score + 0.4 * direct_pt_support + 0.3 * simulation_support
    return 1.0 / (1.0 + math.exp(-value))



def _belief_status(confidence: float, support_score: float, contradiction_score: float, direct_pt_support: float) -> str:
    if contradiction_score >= 2.0 and confidence < 0.25:
        return "retired"
    if contradiction_score > support_score and confidence < 0.45:
        return "contradicted"
    if confidence >= 0.60 and support_score > contradiction_score:
        return "supported"
    if contradiction_score >= 3.0 and direct_pt_support == 0:
        return "retired"
    return "proposed"



def build_bridge_case_nodes(note: dict[str, Any]) -> list[dict[str, Any]]:
    support_mix = dict(note.get("support_mix") or {})
    transferability_score = float(support_mix.get("transferability_score", 0.0) or 0.0)
    if transferability_score <= 0.0:
        return []

    evidence = note.get("evidence") or []
    source_families = sorted({str(item.get("source_family") or item.get("source_tags", {}).get("source_family") or "mixed") for item in evidence})
    if not any(family in {"QN", "adjacent"} for family in source_families):
        return []

    descriptor_similarity = min(1.0, 0.35 + 0.15 * len([k for k, v in support_mix.items() if isinstance(v, (int, float)) and v and k.endswith("support")]))
    mechanism_similarity = 0.7 if support_mix.get("adjacent_scaffold_support", 0) or support_mix.get("quinone_bridge_support", 0) else 0.45
    condition_similarity = 0.75 if support_mix.get("direct_pt_support", 0) else 0.6
    evidence_support = min(1.0, sum(float(v or 0.0) for k, v in support_mix.items() if k.endswith("support")) / 3.0)
    simulation_agreement = min(1.0, float(support_mix.get("simulation_support", 0.0) or 0.0))
    contradiction_penalty = min(1.0, 0.25 * float(support_mix.get("contradiction_count", 0) or 0))

    bridge_dimensions = []
    property_support = dict((note.get("signals") or {}).get("property_support") or {})
    if property_support.get("oxidation_potential") or property_support.get("reduction_potential"):
        bridge_dimensions.append("electronic_push_pull")
    if property_support.get("solubility"):
        bridge_dimensions.append("solubilizing_handle")
    if property_support.get("instability"):
        bridge_dimensions.append("degradation_family")
    if property_support.get("synthesizability"):
        bridge_dimensions.append("route_modularity")
    if not bridge_dimensions:
        bridge_dimensions.append("charge_delocalization")

    transform_rule_id = f"transform_rule::{note['candidate_id']}"
    bridge_case_id = f"bridge_case::{note['candidate_id']}"
    support_score = evidence_support + float(support_mix.get("direct_pt_support", 0.0) or 0.0) + float(support_mix.get("simulation_support", 0.0) or 0.0)
    contradiction_score = contradiction_penalty
    confidence = _belief_confidence(
        support_score=support_score,
        contradiction_score=contradiction_score,
        direct_pt_support=float(support_mix.get("direct_pt_support", 0.0) or 0.0),
        simulation_support=float(support_mix.get("simulation_support", 0.0) or 0.0),
    )
    status = _belief_status(
        confidence=confidence,
        support_score=support_score,
        contradiction_score=contradiction_score,
        direct_pt_support=float(support_mix.get("direct_pt_support", 0.0) or 0.0),
    )

    nodes = [
        {
            "id": transform_rule_id,
            "type": "TransformRule",
            "attrs": {
                "rule_id": transform_rule_id,
                "source_family": "/".join(source_families),
                "target_family": "PT",
                "source_transform": "literature_inferred_substituent_strategy",
                "target_transform": "pt_candidate_property_transfer",
                "bridge_dimensions": bridge_dimensions,
                "expected_effect_vector": property_support,
                "applicability_conditions": ["electrolyte_relevant_context"],
                "confidence": round(transferability_score, 3),
                "support_mix": support_mix,
                "calibration_error": round(max(0.0, 1.0 - transferability_score), 3),
                "status": "proposed" if transferability_score < 0.75 else "supported",
            },
        },
        {
            "id": bridge_case_id,
            "type": "BridgeCase",
            "attrs": {
                "case_id": bridge_case_id,
                "target_candidate_id": note["candidate_id"],
                "source_evidence_refs": [item.get("id") for item in evidence[:5] if item.get("id")],
                "bridge_principle_refs": bridge_dimensions,
                "transform_rule_ref": transform_rule_id,
                "transferability_score": round(transferability_score, 3),
                "descriptor_similarity": round(descriptor_similarity, 3),
                "mechanism_similarity": round(mechanism_similarity, 3),
                "condition_similarity": round(condition_similarity, 3),
                "evidence_support": round(evidence_support, 3),
                "simulation_agreement": round(simulation_agreement, 3),
                "contradiction_penalty": round(contradiction_penalty, 3),
                "rationale": note.get("summary"),
                "next_action": "simulation_request" if transferability_score < 0.75 else "generation_prior",
                "validation_status": "failed_transfer" if transferability_score < 0.25 else "pending",
                "support_mix": support_mix,
            },
        },
        {
            "id": f"belief_state::{note['candidate_id']}",
            "type": "BeliefState",
            "attrs": {
                "belief_id": f"belief_state::{note['candidate_id']}",
                "belief_type": "candidate_transferability",
                "status": status,
                "confidence": round(confidence, 3),
                "support_score": round(support_score, 3),
                "contradiction_score": round(contradiction_score, 3),
                "direct_pt_support": round(float(support_mix.get("direct_pt_support", 0.0) or 0.0), 3),
                "broader_pt_support": round(float(support_mix.get("pt_scaffold_support", 0.0) or 0.0), 3),
                "adjacent_support": round(float(support_mix.get("adjacent_scaffold_support", 0.0) or 0.0), 3),
                "quinone_support": round(float(support_mix.get("quinone_bridge_support", 0.0) or 0.0), 3),
                "simulation_support": round(float(support_mix.get("simulation_support", 0.0) or 0.0), 3),
                "weak_support": round(float(support_mix.get("metadata_support", 0.0) or 0.0), 3),
                "last_updated": "current_run",
                "owner_agent": "critique",
                "notes": note.get("summary"),
                "support_mix": support_mix,
            },
        },
    ]

    if transferability_score < 0.25 or contradiction_penalty >= 0.5:
        nodes.append(
            {
                "id": f"failure_mode::{note['candidate_id']}",
                "type": "FailureModeClass",
                "attrs": {
                    "candidate_id": note["candidate_id"],
                    "kind": "failed_transfer",
                    "transferability_score": round(transferability_score, 3),
                    "contradiction_penalty": round(contradiction_penalty, 3),
                    "notes": note.get("summary"),
                },
            }
        )

    return nodes
