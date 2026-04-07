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



def compute_decoration_adjustment(row: dict[str, Any]) -> tuple[float, list[str]]:
    identity = row.get("identity", {})
    bonus = 0.0
    rationale: list[str] = []

    substituent_count = identity.get("substituent_count")
    if substituent_count is not None:
        if 1 <= substituent_count <= 3:
            bonus += 0.03
            rationale.append("moderate_substituent_count_bonus")
        elif substituent_count and substituent_count > 5:
            bonus -= 0.03
            rationale.append("high_substituent_count_penalty")

    electronic_bias = identity.get("electronic_bias")
    if electronic_bias == "mixed":
        bonus += 0.01
        rationale.append("mixed_electronic_bias_bonus")
    elif electronic_bias == "electron_withdrawing_skew":
        bonus += 0.005
        rationale.append("ewg_skew_small_bonus")
    elif electronic_bias == "electron_donating_skew":
        bonus += 0.005
        rationale.append("edg_skew_small_bonus")

    return bonus, rationale



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
        base_priority = compute_priority_score(item)
        decoration_bonus, decoration_rationale = compute_decoration_adjustment(item)
        item["predicted_priority"] = None if base_priority is None else base_priority + decoration_bonus
        item["decoration_adjustment"] = decoration_bonus
        item["ranking_rationale"] = {
            "primary_objectives": ["synthesizability", "solubility"],
            "weights": {"synthesizability": 0.55, "solubility": 0.45},
            "decoration_adjustment": decoration_rationale,
        }
        enriched.append(item)
    enriched.sort(key=lambda x: (-1.0 if x.get("predicted_priority") is None else -float(x["predicted_priority"]), x.get("id", "")))
    return enriched
