from __future__ import annotations

from pathlib import Path

from pz_agent.kg.rag import retrieve_context
from pz_agent.kg.schema_v2 import RetrievalQuery


def build_candidate_queries(
    candidate: dict,
    search_fields: list[str] | None = None,
    query_hints: list[str] | None = None,
) -> list[str]:
    fields = search_fields or ["phenothiazine", "solubility", "synthesizability", "derivative"]
    joined = " ".join(fields)
    identity = candidate.get("identity", {})
    tokens = [
        candidate.get("id"),
        identity.get("name"),
        identity.get("scaffold"),
        identity.get("decoration_summary"),
        identity.get("electronic_bias"),
        *(identity.get("decoration_tokens") or []),
    ]
    token_text = " ".join(token for token in tokens if token)
    attachment_text = " ".join(identity.get("attachment_summary") or [])
    queries = [
        f"{token_text} {joined}".strip(),
        f"{token_text} {attachment_text} phenothiazine literature".strip(),
        f"phenothiazine derivative {identity.get('decoration_summary') or ''} {identity.get('electronic_bias') or ''} {joined}".strip(),
    ]
    for hint in query_hints or []:
        if hint and hint not in queries:
            queries.append(hint)
    return queries


def attach_critique_placeholders(
    shortlist: list[dict],
    enable_web_search: bool,
    max_candidates: int,
    search_fields: list[str] | None = None,
    graph_path: Path | None = None,
) -> list[dict]:
    notes: list[dict] = []
    for item in shortlist[:max_candidates]:
        retrieval_query = RetrievalQuery(
            candidate_id=item["id"],
            properties_of_interest=list(search_fields or []),
        )
        kg_context = retrieve_context(graph_path, retrieval_query)
        notes.append(
            {
                "candidate_id": item["id"],
                "web_search_enabled": enable_web_search,
                "status": "pending_web_search" if enable_web_search else "disabled",
                "queries": build_candidate_queries(item, search_fields=search_fields, query_hints=kg_context.query_hints),
                "summary": "Awaiting web evidence collection for top candidate.",
                "evidence": [],
                "media_evidence": [],
                "kg_context": kg_context.to_dict(),
                "signals": {
                    "supports_solubility": None,
                    "supports_synthesizability": None,
                    "warns_instability": None,
                    "exact_match_hits": kg_context.exact_match_hits,
                    "analog_match_hits": kg_context.analog_match_hits,
                    "support_score": kg_context.support_score,
                    "contradiction_score": kg_context.contradiction_score,
                },
            }
        )
    return notes


def synthesize_evidence_from_queries(notes: list[dict]) -> list[dict]:
    for note in notes:
        evidence = []
        media_evidence = []
        for idx, query in enumerate(note.get("queries", [])):
            evidence.append(
                {
                    "id": f"evidence::{note['candidate_id']}::{idx}",
                    "kind": "web_result_stub",
                    "query": query,
                    "title": f"Stub literature hit for {note['candidate_id']}",
                    "url": None,
                    "snippet": "Replace with actual title/url/snippet from web_search tool integration.",
                    "match_type": "unknown",
                    "provenance": {
                        "source_type": "web_search",
                        "query": query,
                        "confidence": None,
                        "evidence_level": "unknown",
                    },
                }
            )
            media_evidence.append(
                {
                    "id": f"media::{note['candidate_id']}::{idx}",
                    "kind": "plot_or_figure_stub",
                    "query": query,
                    "caption": "Stub figure/plot reference for this evidence item.",
                    "source_url": None,
                    "image_path": None,
                    "media_type": "plot",
                    "provenance": {
                        "source_type": "literature_figure_or_generated_plot",
                        "query": query,
                        "confidence": None,
                    },
                }
            )
        note["evidence"] = evidence
        note["media_evidence"] = media_evidence
        kg_context = note.get("kg_context", {})
        open_questions = kg_context.get("open_questions", [])
        note["summary"] = "Structured critique bundle includes KG-derived context, text-evidence stubs, media stubs, and graph-ready provenance."
        if open_questions:
            note["summary"] += " Open questions: " + " | ".join(open_questions[:3])
        if note.get("web_search_enabled"):
            note["status"] = "ready_for_live_web_ingestion"
        note["signals"] = {
            "supports_solubility": None,
            "supports_synthesizability": None,
            "warns_instability": None,
            "exact_match_hits": int(note.get("signals", {}).get("exact_match_hits", 0)),
            "analog_match_hits": int(note.get("signals", {}).get("analog_match_hits", 0)),
            "support_score": float(note.get("signals", {}).get("support_score", 0.0)),
            "contradiction_score": float(note.get("signals", {}).get("contradiction_score", 0.0)),
        }
    return notes
