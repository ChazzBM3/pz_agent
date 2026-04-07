from __future__ import annotations


def build_candidate_queries(candidate: dict, search_fields: list[str] | None = None) -> list[str]:
    fields = search_fields or ["phenothiazine", "solubility", "synthesizability", "derivative"]
    joined = " ".join(fields)
    identity = candidate.get("identity", {})
    tokens = [
        candidate.get("id"),
        identity.get("name"),
        identity.get("scaffold"),
        identity.get("decoration_summary"),
        *(identity.get("decoration_tokens") or []),
    ]
    token_text = " ".join(token for token in tokens if token)
    return [
        f"{token_text} {joined}".strip(),
        f"{token_text} phenothiazine literature".strip(),
        f"phenothiazine derivative {identity.get('decoration_summary') or ''} {joined}".strip(),
    ]


def attach_critique_placeholders(
    shortlist: list[dict],
    enable_web_search: bool,
    max_candidates: int,
    search_fields: list[str] | None = None,
) -> list[dict]:
    notes: list[dict] = []
    for item in shortlist[:max_candidates]:
        notes.append(
            {
                "candidate_id": item["id"],
                "web_search_enabled": enable_web_search,
                "status": "pending_web_search" if enable_web_search else "disabled",
                "queries": build_candidate_queries(item, search_fields=search_fields),
                "summary": "Awaiting web evidence collection for top candidate.",
                "evidence": [],
                "media_evidence": [],
                "signals": {
                    "supports_solubility": None,
                    "supports_synthesizability": None,
                    "warns_instability": None,
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
        note["summary"] = "Structured critique bundle includes text-evidence stubs, media stubs, and graph-ready provenance."
        if note.get("web_search_enabled"):
            note["status"] = "ready_for_live_web_ingestion"
        note["signals"] = {
            "supports_solubility": None,
            "supports_synthesizability": None,
            "warns_instability": None,
            "exact_match_hits": 0,
            "analog_match_hits": 0,
        }
    return notes
