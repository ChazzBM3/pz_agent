from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from pz_agent.io import read_json, write_json


def build_scaffold_feature_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    molecule_to_scaffold: dict[str, str] = {}
    scaffold_to_molecules: dict[str, set[str]] = defaultdict(set)
    molecule_to_measurement_count: dict[str, int] = defaultdict(int)

    for edge in graph.get("edges", []):
        edge_type = edge.get("type")
        if edge_type == "HAS_SCAFFOLD":
            molecule_to_scaffold[edge["source"]] = edge["target"]
            scaffold_to_molecules[edge["target"]].add(edge["source"])
        elif edge_type == "MEASURED_FOR":
            molecule_to_measurement_count[edge["target"]] += 1

    features = {}
    for molecule_id, scaffold_id in molecule_to_scaffold.items():
        scaffold_node = nodes.get(scaffold_id, {})
        scaffold_smiles = ((scaffold_node.get("attrs") or {}).get("smiles"))
        family = scaffold_to_molecules.get(scaffold_id, set())
        family_measurement_counts = [molecule_to_measurement_count.get(member, 0) for member in family]
        avg_measurements = sum(family_measurement_counts) / len(family_measurement_counts) if family_measurement_counts else 0.0
        features[molecule_id] = {
            "scaffold_id": scaffold_id,
            "scaffold_smiles": scaffold_smiles,
            "scaffold_family_size": len(family),
            "scaffold_family_avg_measurements": avg_measurements,
            "scaffold_measurement_density": molecule_to_measurement_count.get(molecule_id, 0),
        }
    return features


def build_scaffold_features_from_path(graph_path: Path | None) -> dict[str, dict[str, Any]]:
    if not graph_path or not Path(graph_path).exists():
        return {}
    graph = read_json(Path(graph_path))
    return build_scaffold_feature_index(graph)


def write_scaffold_features(graph_path: Path | None, output_path: Path) -> dict[str, dict[str, Any]]:
    features = build_scaffold_features_from_path(graph_path)
    write_json(output_path, features)
    return features
