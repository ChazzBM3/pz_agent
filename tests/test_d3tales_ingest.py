from __future__ import annotations

from pathlib import Path

from pz_agent.kg.d3tales_ingest import ingest_d3tales_csv, records_to_graph
from pz_agent.data.d3tales_loader import load_d3tales_csv


CSV_TEXT = """_id,smiles,source_group,oxidation_potential,groundState.homo,omega\nrec1,C1=CC=CC=C1,group_a,0.91,-5.2,0.17\nrec2,C1=NC=CC=C1,group_b,1.01,-5.0,0.15\n"""


def test_records_to_graph_creates_measurement_nodes(tmp_path: Path) -> None:
    path = tmp_path / "d3tales.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    records = load_d3tales_csv(path)

    graph = records_to_graph(records)

    assert any(node["type"] == "Dataset" for node in graph["nodes"])
    assert any(node["type"] == "Molecule" for node in graph["nodes"])
    assert any(node["type"] == "Measurement" for node in graph["nodes"])
    assert any(node["type"] == "Property" for node in graph["nodes"])
    assert any(edge["type"] == "MEASURED_FOR" for edge in graph["edges"])
    assert any(edge["type"] == "HAS_PROPERTY" for edge in graph["edges"])


def test_ingest_d3tales_csv_writes_graph(tmp_path: Path) -> None:
    csv_path = tmp_path / "d3tales.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    graph_path = tmp_path / "graph.json"

    merged = ingest_d3tales_csv(csv_path, output_graph_path=graph_path, limit=1)

    assert graph_path.exists()
    assert any(node["id"] == "rec1" for node in merged["nodes"])
    assert any(node["type"] == "Measurement" for node in merged["nodes"])
