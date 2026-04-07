from __future__ import annotations

from typing import Any

from pz_agent.state import RunState


def build_graph_snapshot(state: RunState) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    run_id = state.run_dir.name
    nodes.append({"id": run_id, "type": "Run", "attrs": {"logs": len(state.logs)}})

    for idx, batch in enumerate(state.generation_registry or []):
        batch_id = f"generation_batch::{idx}"
        nodes.append({"id": batch_id, "type": "GenerationBatch", "attrs": batch})
        edges.append({"source": batch_id, "target": run_id, "type": "GENERATED_IN_RUN"})

    for item in state.library_clean or []:
        nodes.append({"id": item["id"], "type": "Molecule", "attrs": item})
        edges.append({"source": item["id"], "target": run_id, "type": "GENERATED_IN_RUN"})
        if state.generation_registry:
            edges.append({"source": item["id"], "target": "generation_batch::0", "type": "GENERATED_BY_BATCH"})

    for pred in state.predictions or []:
        pred_id = f"pred::{pred['id']}::{pred.get('model', 'unknown')}"
        nodes.append({"id": pred_id, "type": "Prediction", "attrs": pred})
        edges.append({"source": pred['id'], "target": pred_id, "type": "PREDICTED_PROPERTY"})

    for item in state.dft_queue or []:
        edges.append({"source": item["id"], "target": run_id, "type": "SELECTED_FOR_DFT"})

    for note in state.critique_notes or []:
        note_id = f"search::{note['candidate_id']}"
        nodes.append({"id": note_id, "type": "LiteratureClaim", "attrs": note})
        edges.append({"source": note['candidate_id'], "target": note_id, "type": "MENTIONED_IN_SEARCH"})
        for idx, query in enumerate(note.get("queries", [])):
            query_id = f"query::{note['candidate_id']}::{idx}"
            nodes.append({"id": query_id, "type": "LiteraturePaper", "attrs": {"query": query, "status": note.get("status")}})
            edges.append({"source": note_id, "target": query_id, "type": "SUPPORTED_BY"})
        for media in note.get("media_evidence", []):
            media_id = media["id"]
            nodes.append({"id": media_id, "type": "MediaArtifact", "attrs": media})
            edges.append({"source": note_id, "target": media_id, "type": "HAS_MEDIA_EVIDENCE"})

    return {
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
