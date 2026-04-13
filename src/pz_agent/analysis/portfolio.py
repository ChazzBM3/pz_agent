from __future__ import annotations

from typing import Any

DEFAULT_PORTFOLIO_BUDGETS = {
    "exploit": 0.40,
    "explore": 0.25,
    "bridge": 0.25,
    "falsify": 0.10,
}



def normalize_budget_map(raw: dict[str, Any] | None) -> dict[str, float]:
    merged = {**DEFAULT_PORTFOLIO_BUDGETS, **(raw or {})}
    cleaned = {key: max(0.0, float(value)) for key, value in merged.items()}
    total = sum(cleaned.values()) or 1.0
    return {key: value / total for key, value in cleaned.items()}



def assign_portfolio_buckets(candidates: list[dict[str, Any]], budgets: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    normalized = normalize_budget_map(budgets)
    ordered_buckets = ["exploit", "explore", "bridge", "falsify"]
    target_counts = {bucket: normalized[bucket] * len(candidates) for bucket in ordered_buckets}
    assigned_counts = {bucket: 0 for bucket in ordered_buckets}
    assignments: list[dict[str, Any]] = []

    ranked_candidates = sorted(
        list(candidates),
        key=lambda item: float((item.get("ranked_row") or {}).get("predicted_priority", item.get("predicted_priority", 0.0)) or 0.0),
        reverse=True,
    )

    for index, candidate in enumerate(ranked_candidates):
        identity = candidate.get("identity") or {}
        has_bridge_signal = bool(identity.get("decoration_tokens") or identity.get("substituent_fragments"))
        bucket_preferences = []
        if index == 0:
            bucket_preferences.append("exploit")
        if has_bridge_signal:
            bucket_preferences.append("bridge")
        bucket_preferences.extend([bucket for bucket in ordered_buckets if bucket not in bucket_preferences])

        bucket = max(
            bucket_preferences,
            key=lambda name: (target_counts[name] - assigned_counts[name], -ordered_buckets.index(name)),
        )
        assigned_counts[bucket] += 1
        assignments.append(
            {
                "candidate_id": candidate.get("id"),
                "proposal_bucket": bucket,
                "selection_reason": f"portfolio_selector::{bucket}",
                "budget_fraction": normalized[bucket],
                "exploration_score": 1.0 if bucket in {"explore", "bridge", "falsify"} else 0.25,
                "exploitation_score": 1.0 if bucket == "exploit" else 0.35,
                "bridge_relevance": 1.0 if bucket == "bridge" and has_bridge_signal else (0.5 if has_bridge_signal else 0.0),
            }
        )

    return assignments
