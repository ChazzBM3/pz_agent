from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


IDENTITY_FIELDS = {"_id", "smiles", "source_group"}
MEASUREMENT_FIELDS = {
    "sa_score",
    "oxidation_potential",
    "reduction_potential",
    "groundState.solvation_energy",
    "groundState.dipole_moment",
    "groundState.globular_volume",
    "molecular_weight",
    "number_of_atoms",
    "adiabatic_ionization_energy",
    "adiabatic_electron_affinity",
    "hole_reorganization_energy",
    "electron_reorganization_energy",
    "groundState.homo",
    "groundState.lumo",
    "groundState.homo_lumo_gap",
    "omega",
}


@dataclass
class D3TaLESRecord:
    record_id: str
    smiles: str
    source_group: str | None
    identity: dict[str, Any]
    measurements: dict[str, float | None]
    raw: dict[str, Any]

    def to_candidate(self) -> dict[str, Any]:
        return {
            "id": self.record_id,
            "smiles": self.smiles,
            "identity": {
                "name": self.record_id,
                "source_group": self.source_group,
            },
            "measurements": self.measurements,
            "provenance": {
                "source_type": "d3tales_csv",
                "source_id": self.record_id,
                "source_group": self.source_group,
            },
        }


def _normalize_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None



def _normalize_row(row: dict[str, str]) -> D3TaLESRecord | None:
    record_id = (row.get("_id") or "").strip()
    smiles = (row.get("smiles") or "").strip()
    if not record_id or not smiles:
        return None

    source_group = (row.get("source_group") or "").strip() or None
    measurements = {field: _normalize_float(row.get(field)) for field in MEASUREMENT_FIELDS if field in row}
    identity = {field: row.get(field) for field in IDENTITY_FIELDS if field in row}

    return D3TaLESRecord(
        record_id=record_id,
        smiles=smiles,
        source_group=source_group,
        identity=identity,
        measurements=measurements,
        raw=dict(row),
    )



def load_d3tales_csv(path: str | Path, limit: int | None = None) -> list[D3TaLESRecord]:
    records: list[D3TaLESRecord] = []
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = _normalize_row(row)
            if record is None:
                continue
            records.append(record)
            if limit is not None and len(records) >= limit:
                break
    return records



def iter_d3tales_csv(path: str | Path) -> Iterator[D3TaLESRecord]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = _normalize_row(row)
            if record is not None:
                yield record
