from __future__ import annotations

from typing import Any


D3TALES_TIER_1 = {
    "oxidation_potential",
    "reduction_potential",
    "groundState.solvation_energy",
    "hole_reorganization_energy",
    "electron_reorganization_energy",
}

D3TALES_TIER_1_DIRECTIONS = {
    "oxidation_potential": "high",
    "reduction_potential": "high",
    "groundState.solvation_energy": "low",
    "hole_reorganization_energy": "low",
    "electron_reorganization_energy": "low",
}

D3TALES_TIER_2 = {
    "adiabatic_ionization_energy",
    "adiabatic_electron_affinity",
    "groundState.homo",
    "groundState.lumo",
    "groundState.homo_lumo_gap",
    "omega",
    "groundState.dipole_moment",
}

D3TALES_TIER_3 = {
    "sa_score",
    "molecular_weight",
    "number_of_atoms",
    "groundState.globular_volume",
}



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



def compute_measurement_hierarchy_adjustment(measurement_summary: dict[str, Any] | None) -> tuple[float, list[str]]:
    if not measurement_summary:
        return 0.0, []

    properties = set(measurement_summary.get("properties", []) or [])
    bonus = 0.0
    rationale: list[str] = []

    tier_1_hits = sorted(properties & D3TALES_TIER_1)
    tier_2_hits = sorted(properties & D3TALES_TIER_2)
    tier_3_hits = sorted(properties & D3TALES_TIER_3)

    if tier_1_hits:
        tier_1_bonus = min(0.18, 0.03 * len(tier_1_hits))
        bonus += tier_1_bonus
        rationale.append(f"d3tales_tier1_bonus={tier_1_bonus:.3f}:{','.join(tier_1_hits)}")
    if tier_2_hits:
        tier_2_bonus = min(0.08, 0.01 * len(tier_2_hits))
        bonus += tier_2_bonus
        rationale.append(f"d3tales_tier2_bonus={tier_2_bonus:.3f}:{','.join(tier_2_hits)}")
    if tier_3_hits:
        tier_3_bonus = min(0.03, 0.005 * len(tier_3_hits))
        bonus += tier_3_bonus
        rationale.append(f"d3tales_tier3_bonus={tier_3_bonus:.3f}:{','.join(tier_3_hits)}")

    return bonus, rationale



def compute_tier_1_value_adjustment(
    measurement_values: dict[str, dict[str, Any]] | None,
) -> tuple[float, list[str]]:
    if not measurement_values:
        return 0.0, []

    bonus = 0.0
    rationale: list[str] = []

    for property_name, direction in D3TALES_TIER_1_DIRECTIONS.items():
        summary = measurement_values.get(property_name)
        if not summary:
            continue
        raw_value = summary.get("value")
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue

        if direction == "high":
            property_bonus = max(-0.04, min(0.04, value * 0.02))
        else:
            property_bonus = max(-0.04, min(0.04, -value * 0.02))

        bonus += property_bonus
        rationale.append(f"tier1_value_adjustment:{property_name}={property_bonus:.3f}:value={value:.3f}")

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

    exact_hits = int(signals.get("exact_match_hits", 0) or 0)
    analog_hits = int(signals.get("analog_match_hits", 0) or 0)
    support_score = float(signals.get("support_score", 0.0) or 0.0)
    contradiction_score = float(signals.get("contradiction_score", 0.0) or 0.0)
    measurement_count = int(signals.get("measurement_count", 0) or 0)
    property_count = int(signals.get("property_count", 0) or 0)

    if exact_hits > 0:
        exact_bonus = min(0.08, exact_hits * 0.01)
        bonus += exact_bonus
        rationale.append(f"exact_hits_bonus={exact_bonus:.3f}")
    if analog_hits > 0:
        analog_bonus = min(0.05, analog_hits * 0.002)
        bonus += analog_bonus
        rationale.append(f"analog_hits_bonus={analog_bonus:.3f}")
    if support_score > 0:
        support_bonus = min(0.08, support_score * 0.005)
        bonus += support_bonus
        rationale.append(f"kg_support_bonus={support_bonus:.3f}")
    if contradiction_score > 0:
        contradiction_penalty = min(0.10, contradiction_score * 0.01)
        bonus -= contradiction_penalty
        rationale.append(f"kg_contradiction_penalty={contradiction_penalty:.3f}")
    if measurement_count > 0:
        measurement_bonus = min(0.06, measurement_count * 0.002)
        bonus += measurement_bonus
        rationale.append(f"measurement_coverage_bonus={measurement_bonus:.3f}")
    if property_count > 0:
        property_bonus = min(0.04, property_count * 0.003)
        bonus += property_bonus
        rationale.append(f"property_coverage_bonus={property_bonus:.3f}")

    measurement_summary = critique_note.get("measurement_context") or item.get("ranking_rationale", {}).get("measurement_summary")
    hierarchy_bonus, hierarchy_rationale = compute_measurement_hierarchy_adjustment(measurement_summary)
    bonus += hierarchy_bonus
    rationale.extend(hierarchy_rationale)

    measurement_values = critique_note.get("measurement_values") or item.get("ranking_rationale", {}).get("measurement_values")
    value_bonus, value_rationale = compute_tier_1_value_adjustment(measurement_values)
    bonus += value_bonus
    rationale.extend(value_rationale)

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
