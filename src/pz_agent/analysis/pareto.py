from __future__ import annotations

from typing import Any


def compute_priority_score(row: dict[str, Any], synth_weight: float = 0.55, sol_weight: float = 0.45) -> float | None:
    synth = row.get("predicted_synthesizability")
    sol = row.get("predicted_solubility")
    if synth is None and sol is None:
        return None
    synth = 0.0 if synth is None else float(synth)
    sol = 0.0 if sol is None else float(sol)
    return synth_weight * synth + sol_weight * sol



def compute_placeholder_pareto(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["predicted_priority"] = compute_priority_score(item)
        item["ranking_rationale"] = {
            "primary_objectives": ["synthesizability", "solubility"],
            "weights": {"synthesizability": 0.55, "solubility": 0.45},
        }
        enriched.append(item)
    enriched.sort(key=lambda x: (-1.0 if x.get("predicted_priority") is None else -float(x["predicted_priority"]), x.get("id", "")))
    return enriched
