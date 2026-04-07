from __future__ import annotations

from typing import Any


def attach_critique_placeholders(shortlist: list[dict[str, Any]], enable_web_search: bool, max_candidates: int) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for item in shortlist[:max_candidates]:
        notes.append(
            {
                "candidate_id": item["id"],
                "web_search_enabled": enable_web_search,
                "status": "placeholder",
                "recommended_query": f"{item['id']} phenothiazine redox potential stability literature",
                "summary": "Placeholder critique summary; replace with actual web search and evidence extraction.",
            }
        )
    return notes
