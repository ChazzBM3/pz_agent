from __future__ import annotations

from pathlib import Path

from pz_agent.data.d3tales_loader import load_d3tales_csv


CSV_TEXT = """_id,smiles,source_group,oxidation_potential,groundState.homo,omega\nrec1,C1=CC=CC=C1,group_a,0.91,-5.2,0.17\nrec2,C1=NC=CC=C1,group_b,,,-0.01\nrec3,CC,,,,\n"""


def test_load_d3tales_csv_normalizes_rows(tmp_path: Path) -> None:
    path = tmp_path / "d3tales.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")

    records = load_d3tales_csv(path)

    assert len(records) == 3
    assert records[0].record_id == "rec1"
    assert records[0].smiles == "C1=CC=CC=C1"
    assert records[0].measurements["oxidation_potential"] == 0.91
    assert records[0].measurements["groundState.homo"] == -5.2
    assert records[1].measurements["oxidation_potential"] is None
    assert records[1].to_candidate()["provenance"]["source_type"] == "d3tales_csv"
    assert all(value is None for value in records[2].measurements.values())


def test_load_d3tales_csv_can_exclude_zero_information_rows(tmp_path: Path) -> None:
    path = tmp_path / "d3tales.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")

    records = load_d3tales_csv(path, exclude_zero_information_rows=True)

    assert len(records) == 2
    assert [record.record_id for record in records] == ["rec1", "rec2"]


def test_load_d3tales_csv_limit(tmp_path: Path) -> None:
    path = tmp_path / "d3tales.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")

    records = load_d3tales_csv(path, limit=1)

    assert len(records) == 1
    assert records[0].record_id == "rec1"
