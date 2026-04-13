from __future__ import annotations

from pathlib import Path

from pz_agent.data.d3tales_loader import is_phenothiazine_like_record, load_d3tales_csv


CSV_TEXT = """_id,smiles,source_group,oxidation_potential
ptz_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.1
ptz_b,CCN1c2ccccc2Sc2ccccc21,demo,0.9
other_a,c1ccccc1,demo,2.0
"""


def test_load_d3tales_csv_can_filter_to_phenothiazine_like_records(tmp_path: Path) -> None:
    csv_path = tmp_path / "demo.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")

    all_records = load_d3tales_csv(csv_path)
    filtered = load_d3tales_csv(csv_path, phenothiazine_only=True)

    assert len(all_records) == 3
    assert [record.record_id for record in filtered] == ["ptz_a", "ptz_b"]
    assert all(is_phenothiazine_like_record(record) for record in filtered)
