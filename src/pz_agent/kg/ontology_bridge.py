from __future__ import annotations

from typing import Any



def build_bridge_principle(hypothesis: dict[str, Any]) -> dict[str, Any]:
    principle_name = str(hypothesis.get("transferred_property") or "redox_tuning")
    return {
        "id": f"chem_bridge::principle::{principle_name}",
        "type": "BridgePrinciple",
        "attrs": {
            "bridge_principle_id": principle_name,
            "name": principle_name,
            "description": hypothesis.get("transfer_hypothesis"),
            "dimension_group": "bridge_transfer",
        },
    }



def build_bridge_dimension(hypothesis: dict[str, Any]) -> dict[str, Any]:
    dimension_name = "electronic_push_pull"
    transferred_property = str(hypothesis.get("transferred_property") or "")
    if "solubility" in transferred_property:
        dimension_name = "solubilizing_handle"
    elif "reduction" in transferred_property or "oxidation" in transferred_property or "redox" in transferred_property:
        dimension_name = "electronic_push_pull"
    return {
        "id": f"chem_bridge::dimension::{dimension_name}",
        "type": "BridgeDimension",
        "attrs": {
            "bridge_dimension_id": dimension_name,
            "name": dimension_name,
            "description": f"Bridge dimension for {transferred_property or 'general transfer'}.",
        },
    }



def build_failure_mode_class(hypothesis: dict[str, Any]) -> dict[str, Any] | None:
    failure_mode = hypothesis.get("expected_failure_mode")
    if not failure_mode:
        return None
    return {
        "id": f"chem_bridge::failure::{failure_mode}",
        "type": "FailureModeClass",
        "attrs": {
            "failure_mode_class_id": failure_mode,
            "name": failure_mode,
            "description": hypothesis.get("failure_rationale"),
        },
    }



def build_transform_rule(candidate_id: str, hypothesis: dict[str, Any]) -> dict[str, Any]:
    template_id = hypothesis.get("template_id") or f"bridge_rule::{candidate_id}"
    return {
        "id": f"chem_bridge::rule::{template_id}",
        "type": "TransformRule",
        "attrs": {
            "transform_rule_id": template_id,
            "candidate_id": candidate_id,
            "source_family": hypothesis.get("source_family"),
            "target_family": hypothesis.get("target_family"),
            "source_transform_signature": {"motif": hypothesis.get("source_motif")},
            "target_transform_signature": {"motif": hypothesis.get("target_motif")},
            "expected_effect_vector": {
                "property": hypothesis.get("transferred_property"),
                "effect": hypothesis.get("expected_transferred_effect"),
            },
            "applicability_conditions": {"preconditions": hypothesis.get("transfer_preconditions") or []},
            "confidence": hypothesis.get("transfer_confidence", 0.0),
            "status": "proposed",
        },
    }



def build_bridge_case(candidate_id: str, hypothesis: dict[str, Any]) -> dict[str, Any]:
    template_id = hypothesis.get("template_id") or "generic"
    return {
        "id": f"chem_bridge::case::{candidate_id}::{template_id}",
        "type": "BridgeCase",
        "attrs": {
            "bridge_case_id": f"{candidate_id}::{template_id}",
            "candidate_compound_id": candidate_id,
            "transform_rule_id": template_id,
            "source_case_ids": [],
            "bridge_score": hypothesis.get("transfer_confidence", 0.0),
            "transferability_score": hypothesis.get("transfer_confidence", 0.0),
            "status": "needs_validation",
        },
    }
