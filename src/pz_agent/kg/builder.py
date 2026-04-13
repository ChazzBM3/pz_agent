from __future__ import annotations

from typing import Any

from pz_agent.io import read_json
from pz_agent.kg.claims import (
    build_claim_nodes,
    build_condition_node,
    build_evidence_hit_node,
    build_paper_node_from_evidence,
    build_property_node,
    build_search_query_node,
    stable_node_id,
)
from pz_agent.kg.merge import append_graph_update
from pz_agent.kg.schema_v3 import KG_V3_LAYERS
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

    run_id = f"run::{state.run_dir.name}"
    add_node({"id": run_id, "type": "Run", "attrs": {"logs": len(state.logs), "kg_layers": KG_V3_LAYERS}})

    for idx, batch in enumerate(state.generation_registry or []):
        batch_id = f"run::generation_batch::{idx}"
        add_node({"id": batch_id, "type": "GenerationBatch", "attrs": batch})
        add_edge(batch_id, run_id, "GENERATED_IN_RUN")

    for dossier in state.dossier_registry or []:
        dossier_id = f"belief::dossier::{dossier['candidate_id']}"
        add_node({"id": dossier_id, "type": "Hypothesis", "attrs": dossier})
        add_edge(dossier_id, dossier["candidate_id"], "PROPOSES")
        add_edge(dossier_id, run_id, "GENERATED_IN_RUN")

        bridge_hypothesis = dossier.get("bridge_hypothesis") or {}
        if bridge_hypothesis.get("source_family"):
            bridge_id = f"bridge::{dossier['candidate_id']}::proposal"
            add_node({"id": bridge_id, "type": "TransformRule", "attrs": {**bridge_hypothesis, "candidate_id": dossier["candidate_id"]}})
            add_edge(dossier_id, bridge_id, "PROPOSES_TRANSFER")
            add_edge(bridge_id, dossier["candidate_id"], "TRANSFERS_UNDER")

        scaffold_meta = dossier.get("scaffold_metadata") or {}
        scaffold_name = scaffold_meta.get("scaffold_family") or "phenothiazine"
        scaffold_id = f"chem_pt::scaffold::{scaffold_name}"
        add_node({"id": scaffold_id, "type": "Scaffold", "attrs": {"name": scaffold_name, "layer": "chemistry"}})
        add_edge(dossier["candidate_id"], scaffold_id, "BELONGS_TO_FAMILY")

        for site_assignment in scaffold_meta.get("site_assignments") or []:
            site = site_assignment.get("site") or "unknown"
            site_id = f"chem_pt::site::{dossier['candidate_id']}::{site}"
            add_node({"id": site_id, "type": "AttachmentSite", "attrs": {**site_assignment, "candidate_id": dossier["candidate_id"]}})
            add_edge(dossier["candidate_id"], site_id, "ATTACHED_AT")
            substituent_class = site_assignment.get("substituent_class")
            if substituent_class:
                substituent_id = f"chem_pt::substituent::{dossier['candidate_id']}::{substituent_class}"
                add_node({"id": substituent_id, "type": "Substituent", "attrs": {"name": substituent_class, "candidate_id": dossier["candidate_id"]}})
                add_edge(site_id, substituent_id, "HAS_DECORATION_PATTERN")

    for belief in state.belief_registry or []:
        belief_id = f"belief::{belief['candidate_id']}"
        add_node({"id": belief_id, "type": "Hypothesis", "attrs": belief})
        add_edge(belief_id, belief["candidate_id"], "ABOUT_MOLECULE")
        add_edge(belief_id, run_id, "UPDATES_BELIEF")

    for bridge in state.bridge_registry or []:
        bridge_id = f"bridge::{bridge['candidate_id']}::{bridge.get('source_family')}::{bridge.get('target_family')}"
        add_node({"id": bridge_id, "type": "TransformRule", "attrs": bridge})
        add_edge(bridge_id, bridge["candidate_id"], "TRANSFERS_UNDER")
        add_edge(bridge_id, run_id, "GENERATED_IN_RUN")

    for ranking in state.ranking_registry or []:
        rank_id = f"run::ranking::{ranking['candidate_id']}"
        add_node({"id": rank_id, "type": "RankingDecision", "attrs": ranking})
        add_edge(rank_id, ranking["candidate_id"], "RANKED_IN")
        add_edge(rank_id, run_id, "GENERATED_IN_RUN")

    for request in state.simulation_requests or []:
        request_id = f"run::simulation_request::{request['candidate_id']}::{request.get('requested_tier')}"
        add_node({"id": request_id, "type": "SimulationRequest", "attrs": request})
        add_edge(request_id, request["candidate_id"], "TESTS")
        add_edge(request_id, run_id, "GENERATED_IN_RUN")

    for result in state.simulation_results or []:
        result_id = f"run::simulation_result::{result['candidate_id']}"
        add_node({"id": result_id, "type": "SimulationResult", "attrs": result})
        add_edge(result_id, result["candidate_id"], "VALIDATED_BY")
        add_edge(result_id, run_id, "GENERATED_IN_RUN")

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
