from __future__ import annotations

from pz_agent.kg.ontology_bridge import (
    build_bridge_case,
    build_bridge_dimension,
    build_bridge_principle,
    build_failure_mode_class,
    build_transform_rule,
)



def test_bridge_ontology_builders_emit_typed_nodes() -> None:
    hypothesis = {
        "source_family": "chem_qn::quinone_abstract",
        "target_family": "chem_pt::phenothiazine",
        "transferred_property": "redox_tuning",
        "transfer_hypothesis": "transfer useful redox behavior",
        "source_motif": "quinone_redox_pattern",
        "target_motif": "phenothiazine_redox_pattern",
        "transfer_preconditions": ["substituent_present"],
        "expected_transferred_effect": "partial_redox_behavior_transfer",
        "expected_failure_mode": "effect_not_transferred",
        "failure_rationale": "orbital mismatch",
        "template_id": "qn_to_pt_generic_redox_transfer",
        "transfer_confidence": 0.5,
    }
    assert build_bridge_principle(hypothesis)["type"] == "BridgePrinciple"
    assert build_bridge_dimension(hypothesis)["type"] == "BridgeDimension"
    assert build_failure_mode_class(hypothesis)["type"] == "FailureModeClass"
    assert build_transform_rule("cand_1", hypothesis)["type"] == "TransformRule"
    assert build_bridge_case("cand_1", hypothesis)["type"] == "BridgeCase"
