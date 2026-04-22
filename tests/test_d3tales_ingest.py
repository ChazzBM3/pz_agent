from __future__ import annotations

import json
from pathlib import Path

from pz_agent.kg.d3tales_ingest import ingest_d3tales_csv, records_to_graph
from pz_agent.data.d3tales_loader import load_d3tales_csv


CSV_TEXT = """_id,smiles,source_group,sa_score,oxidation_potential,reduction_potential,groundState.solvation_energy,hole_reorganization_energy,electron_reorganization_energy\nrec_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.2,1.4,0.7,-0.8,0.2,0.3\nrec_b,CCN1c2ccccc2Sc2ccccc21,demo,2.1,0.4,0.2,0.1,1.1,1.2\n"""


def test_records_to_graph_includes_dataset_and_measurements(tmp_path: Path) -> None:
    path = tmp_path / "d3tales.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    records = load_d3tales_csv(path)

    graph = records_to_graph(records)

    assert any(node["id"] == "dataset::d3tales" for node in graph["nodes"])
    assert any(node["type"] == "Measurement" for node in graph["nodes"])
    assert any(edge["type"] == "MEASURED_FOR" for edge in graph["edges"])
    assert any(edge["type"] == "HAS_PROPERTY" for edge in graph["edges"])


def test_records_to_graph_includes_scaffold_nodes_and_edges(tmp_path: Path) -> None:
    path = tmp_path / "d3tales.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    records = load_d3tales_csv(path)

    graph = records_to_graph(records)

    assert any(node["type"] == "Scaffold" for node in graph["nodes"])
    assert any(edge["type"] == "HAS_SCAFFOLD" for edge in graph["edges"])


def test_ingest_d3tales_csv_writes_graph(tmp_path: Path) -> None:
    csv_path = tmp_path / "d3tales.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    graph_path = tmp_path / "graph.json"

    merged = ingest_d3tales_csv(csv_path, output_graph_path=graph_path, limit=1)

    assert graph_path.exists()
    written = json.loads(graph_path.read_text())
    assert merged == written
    assert any(node["type"] == "Molecule" for node in written["nodes"])
