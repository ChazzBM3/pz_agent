from __future__ import annotations

from pathlib import Path
import re

from pz_agent.kg.rag import retrieve_context, summarize_property_coverage
from pz_agent.kg.schema_v2 import RetrievalQuery


SCHOLARLY_SITE_HINT = "(site:pubs.acs.org OR site:sciencedirect.com OR site:wiley.com OR site:pubmed.ncbi.nlm.nih.gov OR site:doi.org)"


def _looks_like_registry_id(token: str | None) -> bool:
    if not token:
        return False
    return bool(re.fullmatch(r"[A-Z0-9]{5,}", token.strip()))


def _clean_token(token: str | None) -> str:
    if not token:
        return ""
    return re.sub(r"\s+", " ", str(token)).strip()


def build_candidate_queries(
    candidate: dict,
    search_fields: list[str] | None = None,
    query_hints: list[str] | None = None,
) -> list[str]:
    fields = search_fields or ["phenothiazine", "solubility", "synthesizability", "derivative"]
    identity = candidate.get("identity", {})
    scaffold = _clean_token(identity.get("scaffold") or "phenothiazine")
    decoration_summary = _clean_token(identity.get("decoration_summary"))
    electronic_bias = _clean_token(identity.get("electronic_bias"))
    attachment_text = _clean_token(" ".join(identity.get("attachment_summary") or []))
    candidate_name = _clean_token(identity.get("name"))
    candidate_id = _clean_token(candidate.get("id"))

    public_name = candidate_name if candidate_name and not _looks_like_registry_id(candidate_name) else ""
    public_id = candidate_id if candidate_id and not _looks_like_registry_id(candidate_id) else ""
    public_token_text = " ".join(token for token in [public_name, public_id] if token)

    property_terms = []
    for field in fields:
        field = _clean_token(field)
        if field and field not in property_terms:
            property_terms.append(field)
    property_clause = " OR ".join(property_terms) if property_terms else "oxidation potential OR reduction potential"

    motif_bits = [bit for bit in [scaffold, decoration_summary, electronic_bias, attachment_text] if bit]
    motif_clause = " ".join(motif_bits)

    queries = [
        f'{SCHOLARLY_SITE_HINT} "{scaffold}" ({property_clause})',
        f'{SCHOLARLY_SITE_HINT} "{scaffold}" derivative synthesis redox',
    ]
    if motif_clause:
        queries.append(f'{SCHOLARLY_SITE_HINT} "{scaffold}" {motif_clause} ({property_clause})')
    if public_token_text:
        queries.append(f'{SCHOLARLY_SITE_HINT} "{public_token_text}" "{scaffold}" chemistry')

    for hint in query_hints or []:
        cleaned_hint = _clean_token(hint)
        if not cleaned_hint:
            continue
        if _looks_like_registry_id(cleaned_hint.split()[0]):
            continue
        constrained_hint = f"{SCHOLARLY_SITE_HINT} {cleaned_hint}"
        if constrained_hint not in queries:
            queries.append(constrained_hint)
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
        property_coverage = summarize_property_coverage(graph_path, item["id"])
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
                "measurement_context": property_coverage,
                "signals": {
                    "supports_solubility": None,
                    "supports_synthesizability": None,
                    "warns_instability": None,
                    "exact_match_hits": kg_context.exact_match_hits,
                    "analog_match_hits": kg_context.analog_match_hits,
                    "support_score": kg_context.support_score,
                    "contradiction_score": kg_context.contradiction_score,
                    "measurement_count": int(property_coverage.get("measurement_count", 0)),
                    "property_count": int(property_coverage.get("property_count", 0)),
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
        measurement_context = note.get("measurement_context", {})
        open_questions = kg_context.get("open_questions", [])
        note["summary"] = "Structured critique bundle includes KG-derived context, text-evidence stubs, media stubs, and graph-ready provenance."
        if measurement_context.get("measurement_count", 0):
            note["summary"] += f" Measured properties available: {measurement_context.get('property_count', 0)} across {measurement_context.get('measurement_count', 0)} records."
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
            "measurement_count": int(note.get("signals", {}).get("measurement_count", 0)),
            "property_count": int(note.get("signals", {}).get("property_count", 0)),
        }
    return notes
