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



def apply_literature_adjustment(row: dict[str, Any], critique_note: dict[str, Any] | None) -> dict[str, Any]:
    item = dict(row)
    base = item.get("predicted_priority")
    if base is None or not critique_note:
        return item

    signals = critique_note.get("signals", {})
    bonus = 0.0
    rationale: list[str] = []

    if signals.get("supports_solubility"):
        bonus += 0.05
        rationale.append("literature_supports_solubility")
    if signals.get("supports_synthesizability"):
        bonus += 0.05
        rationale.append("literature_supports_synthesizability")
    analog_hits = int(signals.get("analog_match_hits", 0) or 0)
    if analog_hits > 0:
        analog_bonus = min(0.05, analog_hits * 0.002)
        bonus += analog_bonus
        rationale.append(f"analog_hits_bonus={analog_bonus:.3f}")
    if signals.get("warns_instability"):
        bonus -= 0.08
        rationale.append("instability_warning_penalty")

    item["literature_adjustment"] = bonus
    item["predicted_priority_literature_adjusted"] = base + bonus
    item.setdefault("ranking_rationale", {})
    item["ranking_rationale"]["literature_adjustment"] = rationale
    return item



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
