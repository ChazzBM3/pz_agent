from __future__ import annotations

from pathlib import Path
from typing import Any

from pz_agent.data.d3tales_loader import D3TaLESRecord, load_d3tales_csv
from pz_agent.kg.claims import build_property_node, stable_node_id
from pz_agent.kg.merge import ingest_graph_update
from pz_agent.io import read_json, write_json


DATASET_NODE_ID = "dataset::d3tales"



def _build_dataset_node() -> dict[str, Any]:
    return {
        "id": DATASET_NODE_ID,
        "type": "Dataset",
        "attrs": {
            "name": "D3TaLES CSV",
            "source_type": "d3tales_csv",
        },
    }



def _build_molecule_node(record: D3TaLESRecord) -> dict[str, Any]:
    return {
        "id": record.record_id,
        "type": "Molecule",
        "attrs": {
            "id": record.record_id,
            "smiles": record.smiles,
            "source_group": record.source_group,
            "identity": record.identity,
            "provenance": {
                "source_type": "d3tales_csv",
                "source_id": record.record_id,
            },
        },
    }



def _build_measurement_node(record: D3TaLESRecord, property_name: str, value: float) -> dict[str, Any]:
    measurement_id = stable_node_id("measurement", record.record_id, property_name)
    return {
        "id": measurement_id,
        "type": "Measurement",
        "attrs": {
            "record_id": record.record_id,
            "property_name": property_name,
            "value": value,
            "source_group": record.source_group,
            "provenance": {
                "source_type": "d3tales_csv",
                "source_id": record.record_id,
            },
        },
    }



def records_to_graph(records: list[D3TaLESRecord]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    dataset_node = _build_dataset_node()
    nodes.append(dataset_node)

    for record in records:
        molecule_node = _build_molecule_node(record)
        nodes.append(molecule_node)
        edges.append({"source": molecule_node["id"], "target": DATASET_NODE_ID, "type": "DERIVED_FROM"})

        for property_name, value in record.measurements.items():
            if value is None:
                continue
            property_node = build_property_node(property_name)
            measurement_node = _build_measurement_node(record, property_name, value)
            nodes.append(property_node)
            nodes.append(measurement_node)
            edges.append({"source": measurement_node["id"], "target": molecule_node["id"], "type": "MEASURED_FOR"})
            edges.append({"source": measurement_node["id"], "target": property_node["id"], "type": "HAS_PROPERTY"})
            edges.append({"source": measurement_node["id"], "target": DATASET_NODE_ID, "type": "DERIVED_FROM"})

    return {
        "nodes": nodes,
        "edges": edges,
        "prediction_provenance_summary": [],
    }



def ingest_d3tales_csv(
    csv_path: str | Path,
    output_graph_path: str | Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    records = load_d3tales_csv(csv_path, limit=limit)
    graph_update = records_to_graph(records)

    if output_graph_path is None:
        return graph_update

    output_path = Path(output_graph_path)
    if output_path.exists():
        base_graph = read_json(output_path)
    else:
        base_graph = None
    merged = ingest_graph_update(base_graph, graph_update["nodes"], graph_update["edges"])
    write_json(output_path, merged)
    return merged
