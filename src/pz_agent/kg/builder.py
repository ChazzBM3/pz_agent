from __future__ import annotations

from typing import Any

from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold

from pz_agent.io import read_json
from pz_agent.kg.claims import (
    build_bridge_case_nodes,
    build_claim_nodes,
    build_condition_node,
    build_evidence_hit_node,
    build_paper_node_from_evidence,
    build_property_node,
    build_search_query_node,
    stable_node_id,
)
from pz_agent.kg.merge import append_graph_update
from pz_agent.state import RunState


DATASET_NODE_ID = "dataset::d3tales"


def _dataset_record_node_id(record_id: str) -> str:
    return f"dataset_record::d3tales::{record_id}"


def _derive_scaffold_smiles(item: dict[str, Any]) -> str | None:
    identity = item.get("identity") or {}
    smiles = (
        identity.get("canonical_smiles")
        or item.get("canonical_smiles")
        or item.get("smiles")
    )
    if not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    scaffold = MurckoScaffold.GetScaffoldForMol(mol)
    if scaffold is None or scaffold.GetNumAtoms() == 0:
        return None
    return Chem.MolToSmiles(scaffold, canonical=True)


def build_graph_snapshot(state: RunState) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(node: dict[str, Any]) -> None:
        node_id = node["id"]
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append(node)

    def add_edge(source: str, target: str, edge_type: str) -> None:
        key = (source, target, edge_type)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"source": source, "target": target, "type": edge_type})

    run_id = state.run_dir.name
    add_node({"id": run_id, "type": "Run", "attrs": {"logs": len(state.logs)}})

    for idx, batch in enumerate(state.generation_registry or []):
        batch_id = f"generation_batch::{idx}"
        add_node({"id": batch_id, "type": "GenerationBatch", "attrs": batch})
        add_edge(batch_id, run_id, "GENERATED_IN_RUN")

    d3tales_records = [record for record in (state.source_records or []) if record.get("dataset") == "d3tales"]
    if d3tales_records:
        add_node({"id": DATASET_NODE_ID, "type": "Dataset", "attrs": {"name": "D3TaLES CSV", "source_type": "d3tales_csv"}})
        for record in d3tales_records:
            record_id = str(record.get("record_id") or "")
            if not record_id:
                continue
            dataset_record_id = _dataset_record_node_id(record_id)
            add_node(
                {
                    "id": dataset_record_id,
                    "type": "Dataset",
                    "attrs": {
                        "record_id": record_id,
                        "dataset_id": DATASET_NODE_ID,
                        "source_type": "d3tales_csv",
                        "source_group": record.get("source_group"),
                        "raw": record.get("raw"),
                    },
                }
            )
            add_edge(dataset_record_id, DATASET_NODE_ID, "DERIVED_FROM")

    stable_identity_by_candidate: dict[str, str] = {}

    for item in state.library_clean or []:
        attrs = dict(item)
        add_node({"id": item["id"], "type": "Molecule", "attrs": attrs})
        add_edge(item["id"], run_id, "GENERATED_IN_RUN")
        scaffold_smiles = _derive_scaffold_smiles(item)
        if scaffold_smiles:
            scaffold_id = f"scaffold::{scaffold_smiles}"
            add_node({"id": scaffold_id, "type": "Scaffold", "attrs": {"smiles": scaffold_smiles}})
            add_edge(item["id"], scaffold_id, "HAS_SCAFFOLD")
        stable_identity_key = item.get("stable_identity_key") or (item.get("identity") or {}).get("stable_identity_key")
        if stable_identity_key:
            stable_identity_by_candidate[item["id"]] = stable_identity_key
            add_node({
                "id": stable_identity_key,
                "type": "MolecularRepresentation",
                "attrs": {
                    "kind": "stable_identity",
                    "canonical_smiles": (item.get("identity") or {}).get("canonical_smiles"),
                    "inchikey": (item.get("identity") or {}).get("inchikey"),
                    "inchi": (item.get("identity") or {}).get("inchi"),
                },
            })
            add_edge(item["id"], stable_identity_key, "HAS_REPRESENTATION")
        if state.generation_registry:
            add_edge(item["id"], "generation_batch::0", "GENERATED_BY_BATCH")
        provenance = item.get("provenance") or {}
        if provenance.get("source_type") == "d3tales_csv" and provenance.get("source_id"):
            add_edge(item["id"], _dataset_record_node_id(str(provenance.get("source_id"))), "DERIVED_FROM")

    for pred in state.predictions or []:
        pred_id = f"pred::{pred['id']}::{pred.get('model', 'unknown')}"
        add_node({"id": pred_id, "type": "Prediction", "attrs": pred})
        add_edge(pred['id'], pred_id, "PREDICTED_PROPERTY")

        prediction_provenance = dict(pred.get("prediction_provenance") or {})
        simulation_id = stable_node_id("simulation", pred["id"], pred.get("model", "unknown"))
        add_node(
            {
                "id": simulation_id,
                "type": "SimulationResult",
                "attrs": {
                    "candidate_id": pred["id"],
                    "model": pred.get("model"),
                    "predicted_solubility": pred.get("predicted_solubility"),
                    "predicted_synthesizability": pred.get("predicted_synthesizability"),
                    "prediction_provenance": prediction_provenance,
                    "evidence_tier": "tier_E_simulation",
                    "source_tags": {
                        "source_type": "simulation",
                        "source_family": "PT",
                        "evidence_tier": "tier_E_simulation",
                        "modality": "simulation",
                        "extraction_method": "pipeline_model",
                    },
                },
            }
        )
        add_edge(simulation_id, pred["id"], "SIMULATED_FOR")

        condition_id = stable_node_id("condition_set", pred["id"], "surrogate_screen")
        add_node(
            {
                "id": condition_id,
                "type": "ConditionSet",
                "attrs": {
                    "kind": "simulation_context",
                    "value": "surrogate_screen",
                    "model": pred.get("model"),
                },
            }
        )
        add_edge(simulation_id, condition_id, "UNDER_CONDITION")

        validation_id = stable_node_id("validation_outcome", pred["id"], "surrogate_screen")
        confidence = prediction_provenance.get("confidence")
        add_node(
            {
                "id": validation_id,
                "type": "ValidationOutcome",
                "attrs": {
                    "candidate_id": pred["id"],
                    "status": "predicted",
                    "confidence": confidence,
                    "notes": prediction_provenance.get("notes"),
                },
            }
        )
        add_edge(simulation_id, validation_id, "VALIDATED_BY")

    for item in state.library_clean or []:
        measurements = item.get("measurements") or {}
        provenance = item.get("provenance") or {}
        for property_name, value in measurements.items():
            if value is None:
                continue
            measurement_id = stable_node_id("measurement", item["id"], property_name)
            attrs = {
                "record_id": item["id"],
                "property_name": property_name,
                "value": value,
                "source_group": item.get("identity", {}).get("source_group"),
                "provenance": provenance,
            }
            if provenance.get("source_type") == "d3tales_csv" and provenance.get("source_id"):
                attrs["dataset_record_id"] = _dataset_record_node_id(str(provenance.get("source_id")))
            stable_identity_key = item.get("stable_identity_key") or (item.get("identity") or {}).get("stable_identity_key")
            if stable_identity_key:
                attrs["stable_identity_key"] = stable_identity_key
            add_node(
                {
                    "id": measurement_id,
                    "type": "Measurement",
                    "attrs": attrs,
                }
            )
            property_node = build_property_node(property_name)
            add_node(property_node)
            add_edge(measurement_id, item["id"], "MEASURED_FOR")
            add_edge(measurement_id, property_node["id"], "HAS_PROPERTY")
            if provenance.get("source_type") == "d3tales_csv" and provenance.get("source_id"):
                add_edge(measurement_id, _dataset_record_node_id(str(provenance.get("source_id"))), "DERIVED_FROM")

    for item in state.simulation_queue or []:
        add_edge(item["id"], run_id, "SELECTED_FOR_SIMULATION")
        dft_sim_id = stable_node_id("simulation_request", item["id"], "simulation_handoff")
        add_node(
            {
                "id": dft_sim_id,
                "type": "SimulationResult",
                "attrs": {
                    "candidate_id": item["id"],
                    "model": "simulation_handoff",
                    "status": "requested",
                    "evidence_tier": "tier_E_simulation",
                    "source_tags": {
                        "source_type": "simulation",
                        "source_family": "PT",
                        "evidence_tier": "tier_E_simulation",
                        "modality": "simulation",
                        "extraction_method": "handoff_queue",
                    },
                },
            }
        )
        add_edge(dft_sim_id, item["id"], "SIMULATED_FOR")

    for validation in state.validation or []:
        candidate_id = str(validation.get("candidate_id") or "")
        if not candidate_id:
            continue
        quality_assessment = dict(validation.get("quality_assessment") or {})
        if quality_assessment.get("quality") != "usable":
            continue

        outputs = dict(validation.get("outputs") or {})
        predicted_reference = dict(validation.get("predicted_reference") or {})
        comparison = dict(validation.get("comparison") or {})
        provenance = dict(validation.get("provenance") or {})
        submission_id = validation.get("submission_id") or "validation_ingest"

        validation_result_id = stable_node_id("simulation_result", candidate_id, submission_id)
        add_node(
            {
                "id": validation_result_id,
                "type": "SimulationResult",
                "attrs": {
                    "candidate_id": candidate_id,
                    "status": validation.get("status"),
                    "backend": validation.get("backend"),
                    "engine": validation.get("engine"),
                    "simulation_type": validation.get("simulation_type"),
                    "submission_id": submission_id,
                    "final_energy": outputs.get("final_energy"),
                    "optimized_structure": outputs.get("optimized_structure"),
                    "groundState.solvation_energy": outputs.get("groundState.solvation_energy"),
                    "groundState.homo": outputs.get("groundState.homo"),
                    "groundState.lumo": outputs.get("groundState.lumo"),
                    "groundState.homo_lumo_gap": outputs.get("groundState.homo_lumo_gap"),
                    "groundState.dipole_moment": outputs.get("groundState.dipole_moment"),
                    "outputs": outputs,
                    "predicted_reference": predicted_reference,
                    "comparison": comparison,
                    "quality_assessment": quality_assessment,
                    "provenance": provenance,
                    "evidence_tier": "tier_E_simulation",
                    "source_tags": {
                        "source_type": "simulation",
                        "source_family": "PT",
                        "evidence_tier": "tier_E_simulation",
                        "modality": "simulation",
                        "extraction_method": "validation_ingest",
                    },
                },
            }
        )
        add_edge(validation_result_id, candidate_id, "SIMULATED_FOR")
        validation_outcome_id = stable_node_id("validated_outcome", candidate_id, submission_id)
        add_node(
            {
                "id": validation_outcome_id,
                "type": "ValidationOutcome",
                "attrs": {
                    "candidate_id": candidate_id,
                    "status": validation.get("status"),
                    "comparison": comparison,
                    "quality_assessment": quality_assessment,
                    "submission_id": submission_id,
                },
            }
        )
        add_edge(validation_result_id, validation_outcome_id, "VALIDATED_BY")

    for failure in state.simulation_failures or []:
        candidate_id = str(failure.get("candidate_id") or "")
        if not candidate_id:
            continue
        submission_id = failure.get("submission_id") or "simulation_failure"
        failure_id = stable_node_id("simulation_failure", candidate_id, submission_id)
        failure_log = dict(failure.get("failure_log") or {})
        add_node(
            {
                "id": failure_id,
                "type": "SimulationFailure",
                "attrs": {
                    "candidate_id": candidate_id,
                    "status": failure.get("status"),
                    "backend": failure.get("backend"),
                    "engine": failure.get("engine"),
                    "simulation_type": failure.get("simulation_type"),
                    "submission_id": submission_id,
                    "job_id": failure.get("job_id"),
                    "remote_target": failure.get("remote_target"),
                    "failure_source": failure.get("failure_source"),
                    "outputs": failure.get("outputs") or {},
                    "failure_log": failure_log,
                    "provenance": failure.get("provenance") or {},
                    "source_tags": {
                        "source_type": "simulation",
                        "source_family": "PT",
                        "evidence_tier": "tier_E_simulation",
                        "modality": "simulation",
                        "extraction_method": "failure_log",
                    },
                },
            }
        )
        add_edge(failure_id, candidate_id, "CONTRADICTED_BY")

    for note in state.critique_notes or []:
        claim_nodes = build_claim_nodes(note)
        evidence_tier = str(note.get("evidence_tier") or "candidate")
        scaffold_name = str((note.get("identity") or {}).get("scaffold") or "").strip()
        bridge_nodes = build_bridge_case_nodes(note)
        bridge_case_ids = [node["id"] for node in bridge_nodes if node.get("type") == "BridgeCase"]
        transform_rule_ids = [node["id"] for node in bridge_nodes if node.get("type") == "TransformRule"]
        belief_state_ids = [node["id"] for node in bridge_nodes if node.get("type") == "BeliefState"]
        failure_mode_ids = [node["id"] for node in bridge_nodes if node.get("type") == "FailureModeClass"]

        for bridge_node in bridge_nodes:
            add_node(bridge_node)
            if bridge_node.get("type") == "BridgeCase":
                add_edge(bridge_node["id"], note["candidate_id"], "ABOUT_MOLECULE")
            elif bridge_node.get("type") == "TransformRule":
                add_edge(bridge_node["id"], note["candidate_id"], "ABOUT_MOLECULE")
                for dimension in bridge_node.get("attrs", {}).get("bridge_dimensions", []) or []:
                    dimension_id = f"bridge_dimension::{dimension}"
                    add_node({"id": dimension_id, "type": "BridgeDimension", "attrs": {"name": dimension}})
                    add_edge(bridge_node["id"], dimension_id, "HAS_BRIDGE_DIMENSION")
            elif bridge_node.get("type") == "BeliefState":
                add_edge(note["candidate_id"], bridge_node["id"], "HAS_BELIEF_STATE")
            elif bridge_node.get("type") == "FailureModeClass":
                add_edge(bridge_node["id"], note["candidate_id"], "ABOUT_MOLECULE")

        for claim_node in claim_nodes:
            note_id = claim_node["id"]
            add_node(claim_node)
            if evidence_tier in {"scaffold", "general_review"} and scaffold_name:
                scaffold_id = f"scaffold::{scaffold_name}"
                add_node({"id": scaffold_id, "type": "Scaffold", "attrs": {"name": scaffold_name}})
                add_edge(note_id, scaffold_id, "ABOUT_SCAFFOLD")
            else:
                add_edge(note_id, note['candidate_id'], "ABOUT_MOLECULE")
                stable_identity_key = stable_identity_by_candidate.get(note["candidate_id"])
                if stable_identity_key:
                    add_edge(note_id, stable_identity_key, "ABOUT_REPRESENTATION")

            property_name = claim_node.get("attrs", {}).get("property_name")
            if property_name:
                property_node = build_property_node(property_name)
                add_node(property_node)
                add_edge(note_id, property_node["id"], "ABOUT_PROPERTY")

                condition_node = build_condition_node("evidence_scope", "general")
                add_node(condition_node)
                add_edge(note_id, condition_node["id"], "RELATES_TO_CONDITION")

            kg_context = note.get("kg_context")
            if kg_context:
                context_id = f"hypothesis::{note['candidate_id']}::retrieval"
                add_node({
                    "id": context_id,
                    "type": "Hypothesis",
                    "attrs": {
                        "candidate_id": note["candidate_id"],
                        "text": "KG retrieval context for critique planning.",
                        "status": "open",
                        "retrieved_context": kg_context,
                    },
                })
                add_edge(note_id, context_id, "SUPPORTED_BY")
                for bridge_case_id in bridge_case_ids:
                    add_edge(context_id, bridge_case_id, "SUPPORTED_BY")

            for transform_rule_id in transform_rule_ids:
                add_edge(note_id, transform_rule_id, "USES_RULE")
            for bridge_case_id in bridge_case_ids:
                add_edge(note_id, bridge_case_id, "BRIDGED_FROM")
            for belief_state_id in belief_state_ids:
                add_edge(note_id, belief_state_id, "SUPPORTED_BY")
            for failure_mode_id in failure_mode_ids:
                add_edge(note_id, failure_mode_id, "CONTRADICTED_BY")

            for idx, query in enumerate(note.get("queries", [])):
                query_node = build_search_query_node(note["candidate_id"], idx, query, status=note.get("status"))
                query_id = query_node["id"]
                add_node(query_node)
                add_edge(note_id, query_id, "HAS_QUERY")

            for evidence in note.get("evidence", []):
                evidence_payload = dict(evidence)
                evidence_payload.setdefault("evidence_tier", evidence_tier)
                evidence_node = build_evidence_hit_node(evidence_payload)
                evidence_id = evidence_node["id"]
                add_node(evidence_node)
                add_edge(note_id, evidence_id, "HAS_EVIDENCE_HIT")
                paper_node = build_paper_node_from_evidence(evidence_payload)
                paper_id = paper_node["id"]
                add_node(paper_node)
                add_edge(evidence_id, paper_id, "SUPPORTED_BY")
                match_type = evidence_payload.get("match_type")
                if evidence_tier in {"scaffold", "general_review"} and scaffold_name:
                    scaffold_id = f"scaffold::{scaffold_name}"
                    add_edge(evidence_id, scaffold_id, "ABOUT_SCAFFOLD")
                elif match_type == "exact":
                    add_edge(evidence_id, note["candidate_id"], "EXACT_MATCH_OF")
                    stable_identity_key = stable_identity_by_candidate.get(note["candidate_id"])
                    if stable_identity_key:
                        add_edge(evidence_id, stable_identity_key, "EXACT_MATCH_OF")
                elif match_type in {"analog", "family"}:
                    add_edge(evidence_id, note["candidate_id"], "ANALOG_OF")
                    stable_identity_key = stable_identity_by_candidate.get(note["candidate_id"])
                    if stable_identity_key:
                        add_edge(evidence_id, stable_identity_key, "ANALOG_OF")

            for media in note.get("media_evidence", []):
                media_id = media["id"]
                add_node({"id": media_id, "type": "MediaArtifact", "attrs": media})
                add_edge(note_id, media_id, "HAS_MEDIA_EVIDENCE")

            multimodal_bundle = note.get("multimodal_rerank") or {}
            for bundle in multimodal_bundle.get("bundles") or []:
                mm_id = bundle.get("bundle_id")
                if not mm_id:
                    continue
                add_node({"id": mm_id, "type": "Figure", "attrs": bundle})
                add_edge(note_id, mm_id, "HAS_FIGURE")
                judgment = bundle.get("gemma_judgment") or {}
                if judgment:
                    judgment_id = f"judgment::{mm_id}"
                    add_node({"id": judgment_id, "type": "Claim", "attrs": {**judgment, "candidate_id": note["candidate_id"], "summary": judgment.get("justification"), "status": judgment.get("status")}})
                    add_edge(judgment_id, mm_id, "SUPPORTED_BY")
                    add_edge(judgment_id, note["candidate_id"], "ABOUT_MOLECULE")

    snapshot = {
        "nodes": nodes,
        "edges": edges,
        "prediction_provenance_summary": [
            {
                "id": pred["id"],
                "prediction_provenance": pred.get("prediction_provenance", {}),
            }
            for pred in (state.predictions or [])
        ],
    }

    if state.knowledge_graph_path and state.knowledge_graph_path.exists():
        try:
            existing_graph = read_json(state.knowledge_graph_path)
            return append_graph_update(existing_graph, snapshot)
        except Exception:
            return snapshot

    return snapshot
