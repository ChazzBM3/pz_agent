from __future__ import annotations

from typing import Any

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

    for item in state.library_clean or []:
        attrs = dict(item)
        add_node({"id": item["id"], "type": "Molecule", "attrs": attrs})
        add_edge(item["id"], run_id, "GENERATED_IN_RUN")
        if state.generation_registry:
            add_edge(item["id"], "generation_batch::0", "GENERATED_BY_BATCH")

    for pred in state.predictions or []:
        pred_id = f"pred::{pred['id']}::{pred.get('model', 'unknown')}"
        add_node({"id": pred_id, "type": "Prediction", "attrs": pred})
        add_edge(pred['id'], pred_id, "PREDICTED_PROPERTY")

    for item in state.library_clean or []:
        measurements = item.get("measurements") or {}
        provenance = item.get("provenance") or {}
        for property_name, value in measurements.items():
            if value is None:
                continue
            measurement_id = stable_node_id("measurement", item["id"], property_name)
            add_node(
                {
                    "id": measurement_id,
                    "type": "Measurement",
                    "attrs": {
                        "record_id": item["id"],
                        "property_name": property_name,
                        "value": value,
                        "source_group": item.get("identity", {}).get("source_group"),
                        "provenance": provenance,
                    },
                }
            )
            property_node = build_property_node(property_name)
            add_node(property_node)
            add_edge(measurement_id, item["id"], "MEASURED_FOR")
            add_edge(measurement_id, property_node["id"], "HAS_PROPERTY")

    for item in state.dft_queue or []:
        add_edge(item["id"], run_id, "SELECTED_FOR_DFT")

    for note in state.critique_notes or []:
        claim_nodes = build_claim_nodes(note)
        evidence_tier = str(note.get("evidence_tier") or "candidate")
        scaffold_name = str((note.get("identity") or {}).get("scaffold") or "").strip()
        bridge_nodes = build_bridge_case_nodes(note)
        bridge_case_ids = [node["id"] for node in bridge_nodes if node.get("type") == "BridgeCase"]
        transform_rule_ids = [node["id"] for node in bridge_nodes if node.get("type") == "TransformRule"]
        belief_state_ids = [node["id"] for node in bridge_nodes if node.get("type") == "BeliefState"]

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

        for claim_node in claim_nodes:
            note_id = claim_node["id"]
            add_node(claim_node)
            if evidence_tier in {"scaffold", "general_review"} and scaffold_name:
                scaffold_id = f"scaffold::{scaffold_name}"
                add_node({"id": scaffold_id, "type": "Scaffold", "attrs": {"name": scaffold_name}})
                add_edge(note_id, scaffold_id, "ABOUT_SCAFFOLD")
            else:
                add_edge(note_id, note['candidate_id'], "ABOUT_MOLECULE")

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
                elif match_type in {"analog", "family"}:
                    add_edge(evidence_id, note["candidate_id"], "ANALOG_OF")

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
