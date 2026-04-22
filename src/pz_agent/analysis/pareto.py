from __future__ import annotations

from typing import Any



def _dedupe_evidence_items(critique_note: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not critique_note:
        return [], {"unique_exact": 0, "unique_analog": 0, "unique_property": 0, "unique_total": 0}

    evidence = critique_note.get("evidence") or []
    unique_items: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    exact_count = 0
    analog_count = 0
    property_count = 0

    for item in evidence:
        match_type = str(item.get("match_type") or "unknown").lower()
        title = str(item.get("title") or "").strip().lower()
        query = str(item.get("query") or "").strip().lower()
        url = str(item.get("url") or "").strip().lower()
        key = (match_type, title, query, url)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_items.append(item)
        text = " ".join(str(item.get(k) or "") for k in ["title", "snippet", "query"]).lower()
        if match_type == "exact":
            exact_count += 1
        elif match_type in {"analog", "family"}:
            analog_count += 1
        if any(token in text for token in ["solubility", "redox", "oxidation", "reduction", "electrochemical", "electrolyte", "battery", "voltammetry"]):
            property_count += 1

    return unique_items, {
        "unique_exact": exact_count,
        "unique_analog": analog_count,
        "unique_property": property_count,
        "unique_total": len(unique_items),
    }



def _compute_candidate_specificity_adjustment(critique_note: dict[str, Any] | None) -> tuple[float, list[str]]:
    if not critique_note:
        return 0.0, []

    evidence, _ = _dedupe_evidence_items(critique_note)
    if not evidence:
        return 0.0, []

    exact_hits = 0
    analog_hits = 0
    unknown_hits = 0
    property_hits = 0
    off_target_hits = 0

    for item in evidence:
        match_type = str(item.get("match_type") or "unknown").lower()
        text = " ".join(str(item.get(k) or "") for k in ["title", "snippet", "query"]).lower()
        if match_type == "exact":
            exact_hits += 1
        elif match_type in {"analog", "family"}:
            analog_hits += 1
        else:
            unknown_hits += 1
        if any(token in text for token in ["solubility", "redox", "oxidation", "reduction", "electrochemical", "electrolyte", "battery", "voltammetry"]):
            property_hits += 1
        if any(token in text for token in ["photocatal", "organophotoredox", "semipinacol", "solar cell", "nanomedicine", "polymer", "peptide", "lysine", "dendrimer"]):
            off_target_hits += 1

    bonus = 0.0
    rationale: list[str] = []
    if exact_hits > 0:
        exact_bonus = min(0.06, exact_hits * 0.015)
        bonus += exact_bonus
        rationale.append(f"candidate_specific_exact_bonus={exact_bonus:.3f}")
    if analog_hits > 0:
        analog_bonus = min(0.03, analog_hits * 0.006)
        bonus += analog_bonus
        rationale.append(f"candidate_specific_analog_bonus={analog_bonus:.3f}")
    if property_hits > 0:
        property_bonus = min(0.03, property_hits * 0.004)
        bonus += property_bonus
        rationale.append(f"property_specific_evidence_bonus={property_bonus:.3f}")
    if unknown_hits > max(exact_hits + analog_hits, 0):
        penalty = min(0.03, unknown_hits * 0.003)
        bonus -= penalty
        rationale.append(f"unknown_match_penalty={penalty:.3f}")
    if off_target_hits > 0:
        penalty = min(0.05, off_target_hits * 0.01)
        bonus -= penalty
        rationale.append(f"off_target_evidence_penalty={penalty:.3f}")

    return bonus, rationale


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
    proposal_prior = dict(row.get("proposal_prior") or {})
    bonus = 0.0
    rationale: list[str] = []

    proposal_mode = str(proposal_prior.get("proposal_mode") or "")
    generation_priors = dict(proposal_prior.get("generation_priors") or {})
    failure_bias = list(proposal_prior.get("failure_bias") or [])
    if proposal_mode == "pt_direct_seed":
        bonus += 0.01 + float(generation_priors.get("pt_direct", 0.0) or 0.0) * 0.01
        rationale.append("pt_direct_seed_bonus")
    elif proposal_mode == "bridge_driven_placeholder":
        bonus += 0.01 + float(generation_priors.get("bridge_driven", 0.0) or 0.0) * 0.015
        rationale.append("bridge_driven_generation_bonus")
    elif proposal_mode == "simulation_driven_placeholder":
        bonus += 0.008 + float(generation_priors.get("simulation_driven", 0.0) or 0.0) * 0.02
        rationale.append("simulation_driven_generation_bonus")
    if failure_bias:
        rationale.append(f"generation_failure_bias_count={len(failure_bias)}")

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



def _compute_kg_prior_adjustment(critique_note: dict[str, Any] | None) -> tuple[float, list[str]]:
    if not critique_note:
        return 0.0, []

    support_mix = dict(critique_note.get("support_mix") or {})
    belief_state = dict((critique_note.get("ranking_rationale") or {}).get("belief_state") or {})
    bonus = 0.0
    rationale: list[str] = []

    transferability_score = float(support_mix.get("transferability_score", 0.0) or 0.0)
    if transferability_score > 0:
        transfer_bonus = min(0.04, transferability_score * 0.03)
        bonus += transfer_bonus
        rationale.append(f"kg_prior_transferability_bonus={transfer_bonus:.3f}")

    simulation_support = float(support_mix.get("simulation_support", 0.0) or 0.0)
    if simulation_support > 0:
        sim_bonus = min(0.05, simulation_support * 0.05)
        bonus += sim_bonus
        rationale.append(f"kg_prior_simulation_bonus={sim_bonus:.3f}")

    support_score = float(belief_state.get("support_score", 0.0) or 0.0)
    contradiction_score = float(belief_state.get("contradiction_score", 0.0) or 0.0)
    if support_score > 0:
        support_bonus = min(0.04, support_score * 0.01)
        bonus += support_bonus
        rationale.append(f"kg_prior_belief_support_bonus={support_bonus:.3f}")
    if contradiction_score > 0:
        penalty = min(0.05, contradiction_score * 0.02)
        bonus -= penalty
        rationale.append(f"kg_prior_belief_contradiction_penalty={penalty:.3f}")

    return bonus, rationale



def compute_scaffold_support_adjustment(scaffold_context: dict[str, Any] | None) -> tuple[float, list[str]]:
    if not scaffold_context:
        return 0.0, []

    family_size = int(scaffold_context.get("scaffold_family_size", 0) or 0)
    family_avg_measurements = float(scaffold_context.get("scaffold_family_avg_measurements", 0.0) or 0.0)
    molecule_measurements = float(scaffold_context.get("scaffold_measurement_density", 0.0) or 0.0)

    bonus = 0.0
    rationale: list[str] = []

    if family_size >= 20:
        family_bonus = min(0.03, family_size / 1000.0)
        bonus += family_bonus
        rationale.append(f"scaffold_family_support_bonus={family_bonus:.3f}:size={family_size}")
    elif 1 <= family_size <= 3:
        penalty = 0.01
        bonus -= penalty
        rationale.append(f"scaffold_family_sparse_penalty={penalty:.3f}:size={family_size}")

    if family_avg_measurements >= 10:
        measurement_bonus = min(0.03, family_avg_measurements / 500.0)
        bonus += measurement_bonus
        rationale.append(f"scaffold_family_measurement_bonus={measurement_bonus:.3f}:avg={family_avg_measurements:.2f}")

    if molecule_measurements == 0 and family_avg_measurements > 0:
        penalty = min(0.015, family_avg_measurements / 1000.0)
        bonus -= penalty
        rationale.append(f"candidate_without_local_measurements_penalty={penalty:.3f}")
    elif molecule_measurements >= 5:
        local_bonus = min(0.015, molecule_measurements / 1000.0)
        bonus += local_bonus
        rationale.append(f"candidate_local_measurement_bonus={local_bonus:.3f}:count={molecule_measurements:.0f}")

    return bonus, rationale


def compute_scaffold_novelty_adjustment(
    row: dict[str, Any],
    critique_note: dict[str, Any] | None,
    scaffold_context: dict[str, Any] | None,
) -> tuple[float, list[str]]:
    if not scaffold_context:
        return 0.0, []

    family_size = int(scaffold_context.get("scaffold_family_size", 0) or 0)
    family_avg_measurements = float(scaffold_context.get("scaffold_family_avg_measurements", 0.0) or 0.0)
    predicted_priority = row.get("predicted_priority")
    support_mix = dict(critique_note.get("support_mix") or {}) if critique_note else {}

    bonus = 0.0
    rationale: list[str] = []

    if 1 <= family_size <= 5:
        edge_bonus = 0.09
        bonus += edge_bonus
        rationale.append(f"novel_sparse_family_bonus={edge_bonus:.3f}:size={family_size}")
    elif 6 <= family_size <= 20:
        edge_bonus = 0.045
        bonus += edge_bonus
        rationale.append(f"novel_mid_sparse_family_bonus={edge_bonus:.3f}:size={family_size}")
    elif family_size >= 100:
        penalty = min(0.03, family_size / 5000.0)
        bonus -= penalty
        rationale.append(f"novel_dense_family_penalty={penalty:.3f}:size={family_size}")

    if family_avg_measurements <= 3 and predicted_priority is not None and float(predicted_priority) >= 0.6:
        underexplored_bonus = 0.045
        bonus += underexplored_bonus
        rationale.append("high_priority_underexplored_family_bonus=0.045")

    analog_support = float(support_mix.get("adjacent_scaffold_support", 0.0) or 0.0)
    exact_support = float((critique_note or {}).get("signals", {}).get("exact_match_hits", 0) or 0.0)
    if analog_support > 0 and exact_support == 0:
        bridge_bonus = min(0.02, analog_support * 0.02)
        bonus += bridge_bonus
        rationale.append(f"analog_bridge_novelty_bonus={bridge_bonus:.3f}")

    return bonus, rationale


def apply_literature_adjustment(row: dict[str, Any], critique_note: dict[str, Any] | None) -> dict[str, Any]:
    item = dict(row)
    base = item.get("predicted_priority")
    item.setdefault("ranking_rationale", {})
    scaffold_context = item.get("ranking_rationale", {}).get("scaffold_context")
    if base is None:
        item.setdefault("literature_adjustment", 0.0)
        item.setdefault("predicted_priority_literature_adjusted", None)
        item["ranking_rationale"].setdefault("literature_adjustment", [])
        item["novelty_adjustment"] = 0.0
        item["predicted_priority_novelty_adjusted"] = None
        item["ranking_rationale"].setdefault("novelty_adjustment", [])
        return item

    if not critique_note:
        item["literature_adjustment"] = 0.0
        item["predicted_priority_literature_adjusted"] = base
        novelty_bonus, novelty_rationale = compute_scaffold_novelty_adjustment(item, critique_note, scaffold_context)
        item["novelty_adjustment"] = novelty_bonus
        item["predicted_priority_novelty_adjusted"] = base + novelty_bonus
        item["ranking_rationale"].setdefault("literature_adjustment", [])
        item["ranking_rationale"]["novelty_adjustment"] = novelty_rationale
        return item

    signals = critique_note.get("signals", {})
    evidence_tier = str(critique_note.get("evidence_tier") or "candidate")
    _, dedupe_summary = _dedupe_evidence_items(critique_note)
    bonus = 0.0
    rationale: list[str] = [f"evidence_tier={evidence_tier}"]
    if dedupe_summary["unique_total"]:
        rationale.append(f"deduped_evidence_items={dedupe_summary['unique_total']}")

    if evidence_tier in {"scaffold", "general_review"}:
        signals = dict(signals)
        signals["supports_solubility"] = False
        signals["supports_synthesizability"] = False
        signals["exact_match_hits"] = 0
        signals["analog_match_hits"] = 0
        signals["property_aligned_hits"] = 0
        signals["support_score"] = min(float(signals.get("support_score", 0.0) or 0.0), 0.2)

    if signals.get("supports_solubility"):
        bonus += 0.05
        rationale.append("literature_supports_solubility")
    if signals.get("supports_synthesizability"):
        bonus += 0.05
        rationale.append("literature_supports_synthesizability")

    raw_exact_hits = int(signals.get("exact_match_hits", 0) or 0)
    raw_analog_hits = int(signals.get("analog_match_hits", 0) or 0)
    raw_property_hits = int(signals.get("property_aligned_hits", 0) or 0)

    exact_hits = min(raw_exact_hits, dedupe_summary["unique_exact"] or raw_exact_hits)
    analog_hits = min(raw_analog_hits, dedupe_summary["unique_analog"] or raw_analog_hits)
    broad_scaffold_hits = int(signals.get("broad_scaffold_hits", 0) or 0)
    property_aligned_hits = min(raw_property_hits, dedupe_summary["unique_property"] or raw_property_hits)
    review_hits = int(signals.get("review_hits", 0) or 0)
    patent_hit_count = int(signals.get("patent_hit_count", 0) or 0)
    scholarly_hit_count = int(signals.get("scholarly_hit_count", 0) or 0)
    support_score = float(signals.get("support_score", 0.0) or 0.0)
    contradiction_score = float(signals.get("contradiction_score", 0.0) or 0.0)
    measurement_count = int(signals.get("measurement_count", 0) or 0)
    property_count = int(signals.get("property_count", 0) or 0)

    if exact_hits > 0:
        exact_bonus = min(0.08, exact_hits * 0.012)
        bonus += exact_bonus
        rationale.append(f"exact_hits_bonus={exact_bonus:.3f}")
    if analog_hits > 0:
        analog_bonus = min(0.04, analog_hits * 0.003)
        bonus += analog_bonus
        rationale.append(f"analog_hits_bonus={analog_bonus:.3f}")
    if broad_scaffold_hits > 0:
        scaffold_bonus = min(0.01, broad_scaffold_hits * 0.0005)
        bonus += scaffold_bonus
        rationale.append(f"broad_scaffold_bonus={scaffold_bonus:.3f}")
    if property_aligned_hits > 0:
        property_alignment_bonus = min(0.04, property_aligned_hits * 0.004)
        bonus += property_alignment_bonus
        rationale.append(f"property_aligned_hits_bonus={property_alignment_bonus:.3f}")
    if support_score > 0:
        support_bonus = min(0.05, support_score * 0.003)
        bonus += support_bonus
        rationale.append(f"kg_support_bonus={support_bonus:.3f}")
    if patent_hit_count > 0:
        patent_bonus = min(0.05, patent_hit_count * 0.004)
        bonus += patent_bonus
        rationale.append(f"patent_hits_bonus={patent_bonus:.3f}")
    if scholarly_hit_count > 0:
        scholarly_bonus = min(0.03, scholarly_hit_count * 0.002)
        bonus += scholarly_bonus
        rationale.append(f"scholarly_hits_bonus={scholarly_bonus:.3f}")
    if review_hits > 0:
        review_penalty = min(0.02, review_hits * 0.002)
        bonus -= review_penalty
        rationale.append(f"generic_review_penalty={review_penalty:.3f}")
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

    specificity_bonus, specificity_rationale = _compute_candidate_specificity_adjustment(critique_note)
    bonus += specificity_bonus
    rationale.extend(specificity_rationale)

    scaffold_context = item.get("ranking_rationale", {}).get("scaffold_context")
    scaffold_bonus, scaffold_rationale = compute_scaffold_support_adjustment(scaffold_context)
    bonus += scaffold_bonus
    rationale.extend(scaffold_rationale)

    support_mix = dict(critique_note.get("support_mix") or {}) if critique_note else {}
    transferability_score = float(support_mix.get("transferability_score", 0.0) or 0.0)
    if transferability_score > 0:
        transfer_bonus = min(0.05, transferability_score * 0.04)
        bonus += transfer_bonus
        rationale.append(f"bridge_transferability_bonus={transfer_bonus:.3f}")
    if float(support_mix.get("quinone_bridge_support", 0.0) or 0.0) > 0:
        rationale.append("bridge_support_from_quinone_teacher")
    if float(support_mix.get("adjacent_scaffold_support", 0.0) or 0.0) > 0:
        rationale.append("bridge_support_from_adjacent_scaffold")

    prior_bonus, prior_rationale = _compute_kg_prior_adjustment(critique_note)
    bonus += prior_bonus
    rationale.extend(prior_rationale)

    if signals.get("warns_instability"):
        bonus -= 0.08
        rationale.append("instability_warning_penalty")

    item["literature_adjustment"] = bonus
    item["predicted_priority_literature_adjusted"] = base + bonus
    novelty_bonus, novelty_rationale = compute_scaffold_novelty_adjustment(item, critique_note, scaffold_context)
    item["novelty_adjustment"] = novelty_bonus
    item["predicted_priority_novelty_adjusted"] = base + novelty_bonus
    item.setdefault("ranking_rationale", {})
    item["ranking_rationale"]["literature_adjustment"] = rationale
    item["ranking_rationale"]["novelty_adjustment"] = novelty_rationale
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
