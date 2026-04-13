from __future__ import annotations

from typing import Any



def build_bridge_hypothesis(candidate: dict[str, Any], bucket: str, bridge_relevance: float = 0.0) -> dict[str, Any]:
    if bucket != "bridge":
        return {
            "source_family": None,
            "target_family": "chem_pt::phenothiazine",
            "transfer_hypothesis": None,
            "source_motif": None,
            "target_motif": None,
            "transferred_property": None,
            "transfer_preconditions": [],
            "expected_transferred_effect": None,
            "expected_failure_mode": None,
            "failure_rationale": None,
            "template_id": None,
            "transfer_confidence": bridge_relevance,
        }

    identity = candidate.get("identity") or {}
    fragments = identity.get("substituent_fragments") or []
    tokens = identity.get("decoration_tokens") or []
    electronic_bias = identity.get("electronic_bias")

    if any("cyano" in fragment for fragment in fragments) or "C#N" in tokens:
        template_id = "qn_to_pt_acceptor_shift"
        source_motif = "quinone_acceptor_tuning"
        target_motif = "phenothiazine_acceptor_decoration"
        transferred_property = "reduction_potential_shift"
        transfer_preconditions = ["acceptor_substituent_present", "conjugation_retained"]
        expected_effect = "lower_lumo_and_stabilize_reduction"
        failure_mode = "charge_localization_breaks_transfer"
        failure_rationale = "acceptor behavior may not survive scaffold-specific charge redistribution"
    elif electronic_bias == "electron_donating_skew":
        template_id = "qn_to_pt_donor_shift"
        source_motif = "quinone_donor_tuning"
        target_motif = "phenothiazine_donor_decoration"
        transferred_property = "oxidation_potential_shift"
        transfer_preconditions = ["donor_substituent_present", "aryl_coupling_retained"]
        expected_effect = "raise_homo_and_tune_oxidation_window"
        failure_mode = "solubility_regression"
        failure_rationale = "donor-heavy substitutions may transfer electronics while hurting solubility"
    else:
        template_id = "qn_to_pt_generic_redox_transfer"
        source_motif = "quinone_redox_pattern"
        target_motif = "phenothiazine_redox_pattern"
        transferred_property = "redox_tuning"
        transfer_preconditions = ["substituent_present", "ring_substitution_accessible"]
        expected_effect = "partial_redox_behavior_transfer"
        failure_mode = "effect_not_transferred"
        failure_rationale = "scaffold-level orbital differences may prevent useful transfer"

    return {
        "source_family": "chem_qn::quinone_abstract",
        "target_family": "chem_pt::phenothiazine",
        "transfer_hypothesis": "quinone-inspired substituent logic may transfer useful redox behavior into the phenothiazine scaffold",
        "source_motif": source_motif,
        "target_motif": target_motif,
        "transferred_property": transferred_property,
        "transfer_preconditions": transfer_preconditions,
        "expected_transferred_effect": expected_effect,
        "expected_failure_mode": failure_mode,
        "failure_rationale": failure_rationale,
        "template_id": template_id,
        "transfer_confidence": bridge_relevance,
    }
