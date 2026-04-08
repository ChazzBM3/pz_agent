from __future__ import annotations

from typing import Any
import hashlib


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
    semantics: list[dict[str, Any]] = [
        {
            "key": "candidate_evidence",
            "subject_type": "molecule",
            "predicate": "candidate_evidence",
            "polarity": "support",
            "property_name": None,
        }
    ]
    if signals.get("supports_solubility"):
        semantics.append(
            {
                "key": "solubility",
                "subject_type": "molecule",
                "predicate": "supports_property",
                "polarity": "support",
                "property_name": "solubility",
            }
        )
    if signals.get("supports_synthesizability"):
        semantics.append(
            {
                "key": "synthesizability",
                "subject_type": "molecule",
                "predicate": "supports_property",
                "polarity": "support",
                "property_name": "synthesizability",
            }
        )
    if signals.get("warns_instability"):
        semantics.append(
            {
                "key": "instability",
                "subject_type": "molecule",
                "predicate": "warns_instability",
                "polarity": "contradiction",
                "property_name": "instability",
            }
        )
    return semantics



def build_claim_nodes(note: dict[str, Any]) -> list[dict[str, Any]]:
    signals = note.get("signals", {})
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
