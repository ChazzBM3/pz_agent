from __future__ import annotations


def build_candidate_queries(candidate: dict, search_fields: list[str] | None = None) -> list[str]:
    fields = search_fields or ["phenothiazine", "solubility", "synthesizability", "derivative"]
    joined = " ".join(fields)
    return [
        f"{candidate['id']} {joined}",
        f"{candidate['id']} phenothiazine literature",
        f"phenothiazine derivative {joined}",
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
                "signals": {
                    "supports_solubility": None,
                    "supports_synthesizability": None,
                    "warns_instability": None,
                },
            }
        )
    return notes
