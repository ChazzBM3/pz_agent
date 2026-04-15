from __future__ import annotations

from typing import Any



def _stable_identity_key_for_node(node: dict[str, Any]) -> str | None:
    attrs = dict(node.get("attrs", {}) or {})
    if node.get("type") != "Molecule":
        return None
    return attrs.get("stable_identity_key") or (attrs.get("identity", {}) or {}).get("stable_identity_key")



def _identity_grouping_edges(nodes: dict[str, dict[str, Any]], merged_edges: dict[tuple[str, str, str], dict[str, Any]]) -> None:
    for node_id, node in list(nodes.items()):
        stable_identity_key = _stable_identity_key_for_node(node)
        if not stable_identity_key:
            continue
        if stable_identity_key not in nodes:
            nodes[stable_identity_key] = {
                "id": stable_identity_key,
                "type": "MolecularRepresentation",
                "attrs": {
                    "kind": "stable_identity",
                },
            }
        key = (node_id, stable_identity_key, "HAS_REPRESENTATION")
        if key not in merged_edges:
            merged_edges[key] = {"source": node_id, "target": stable_identity_key, "type": "HAS_REPRESENTATION"}



def merge_graphs(*graphs: dict[str, Any] | None) -> dict[str, Any]:
    merged_nodes: dict[str, dict[str, Any]] = {}
    merged_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    prediction_provenance_summary: list[dict[str, Any]] = []
    seen_prediction_ids: set[str] = set()

    for graph in graphs:
        if not graph:
            continue
        for node in graph.get("nodes", []):
            node_id = node["id"]
            if node_id not in merged_nodes:
                merged_nodes[node_id] = node
                continue
            existing = merged_nodes[node_id]
            existing_attrs = dict(existing.get("attrs", {}))
            new_attrs = dict(node.get("attrs", {}))
            existing_attrs.update({k: v for k, v in new_attrs.items() if v is not None})
            existing["attrs"] = existing_attrs
            if not existing.get("type") and node.get("type"):
                existing["type"] = node["type"]

        for edge in graph.get("edges", []):
            key = (edge.get("source"), edge.get("target"), edge.get("type"))
            merged_edges[key] = edge

        for pred in graph.get("prediction_provenance_summary", []):
            pred_id = pred.get("id")
            if pred_id in seen_prediction_ids:
                continue
            seen_prediction_ids.add(pred_id)
            prediction_provenance_summary.append(pred)

    _identity_grouping_edges(merged_nodes, merged_edges)

    return {
        "nodes": sorted(merged_nodes.values(), key=lambda x: x.get("id", "")),
        "edges": sorted(merged_edges.values(), key=lambda x: (x.get("source", ""), x.get("target", ""), x.get("type", ""))),
        "prediction_provenance_summary": prediction_provenance_summary,
    }


def append_graph_update(existing_graph: dict[str, Any] | None, new_graph: dict[str, Any]) -> dict[str, Any]:
    return merge_graphs(existing_graph, new_graph)



def ingest_graph_update(base_graph: dict[str, Any] | None, update_nodes: list[dict[str, Any]], update_edges: list[dict[str, Any]]) -> dict[str, Any]:
    update = {
        "nodes": update_nodes,
        "edges": update_edges,
        "prediction_provenance_summary": [],
    }
    return append_graph_update(base_graph, update)
