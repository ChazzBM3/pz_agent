from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

try:
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    RDKIT_AVAILABLE = True
except Exception:
    Chem = None
    MurckoScaffold = None
    RDKIT_AVAILABLE = False


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



def _murcko_scaffold_smiles(smiles: str) -> str | None:
    if not RDKIT_AVAILABLE:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    scaffold_mol = MurckoScaffold.GetScaffoldForMol(mol)
    if scaffold_mol is None:
        return None
    return Chem.MolToSmiles(scaffold_mol, canonical=True)



def is_phenothiazine_like_record(record: D3TaLESRecord) -> bool:
    scaffold = _murcko_scaffold_smiles(record.smiles)
    if scaffold is None:
        token_text = f"{record.smiles} {record.record_id} {record.source_group or ''}".lower()
        return "phenothiaz" in token_text
    return scaffold in {
        "c1ccc2c(c1)Sc1ccccc1S2",
        "c1ccc2c(c1)Nc1ccccc1S2",
    }



def load_d3tales_csv(
    path: str | Path,
    limit: int | None = None,
    phenothiazine_only: bool = False,
    exclude_zero_information_rows: bool = False,
) -> list[D3TaLESRecord]:
    records: list[D3TaLESRecord] = []
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = _normalize_row(row)
            if record is None:
                continue
            if exclude_zero_information_rows and all(value is None for value in record.measurements.values()):
                continue
            if phenothiazine_only and not is_phenothiazine_like_record(record):
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
