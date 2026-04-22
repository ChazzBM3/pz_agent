from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"RDKit is required for scaffold audit: {exc}")

from pz_agent.data.d3tales_loader import MEASUREMENT_FIELDS, load_d3tales_csv


def scaffold_smiles(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    scaffold = MurckoScaffold.GetScaffoldForMol(mol)
    if scaffold is None:
        return None
    if scaffold.GetNumAtoms() == 0:
        return None
    return Chem.MolToSmiles(scaffold, canonical=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit D3TaLES scaffold-level coverage.")
    parser.add_argument("--csv", default="data/d3tales.csv")
    parser.add_argument("--out", default="artifacts/kg_prod_2026_04_22/d3tales_scaffold_audit.json")
    args = parser.parse_args()

    records = load_d3tales_csv(args.csv, limit=None, exclude_zero_information_rows=True)
    scaffold_records: dict[str, list] = defaultdict(list)
    invalid_scaffolds = 0

    for record in records:
        scaffold = scaffold_smiles(record.smiles)
        if scaffold is None:
            invalid_scaffolds += 1
            continue
        scaffold_records[scaffold].append(record)

    scaffold_summary = []
    for scaffold, members in scaffold_records.items():
        source_groups = Counter(record.source_group or "<missing>" for record in members)
        property_counts = Counter()
        complete_panel = 0
        for record in members:
            present = 0
            for prop, value in record.measurements.items():
                if value is not None:
                    property_counts[prop] += 1
                    present += 1
            if present == len(MEASUREMENT_FIELDS):
                complete_panel += 1
        scaffold_summary.append(
            {
                "scaffold": scaffold,
                "record_count": len(members),
                "source_groups": dict(source_groups),
                "complete_panel_count": complete_panel,
                "property_coverage": {
                    prop: {
                        "count": property_counts[prop],
                        "fraction": property_counts[prop] / len(members),
                    }
                    for prop in sorted(MEASUREMENT_FIELDS)
                },
            }
        )

    scaffold_summary.sort(key=lambda item: (-item["record_count"], item["scaffold"]))
    top_scaffolds = scaffold_summary[:25]
    sparse_promising = [
        item
        for item in scaffold_summary
        if 3 <= item["record_count"] <= 25 and item["property_coverage"].get("oxidation_potential", {}).get("fraction", 0) >= 0.5
    ][:25]

    result = {
        "csv": str(args.csv),
        "record_count": len(records),
        "unique_scaffold_count": len(scaffold_summary),
        "invalid_scaffold_count": invalid_scaffolds,
        "top_scaffolds": top_scaffolds,
        "sparse_promising_scaffolds": sparse_promising,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "record_count": result["record_count"],
        "unique_scaffold_count": result["unique_scaffold_count"],
        "invalid_scaffold_count": result["invalid_scaffold_count"],
        "top_scaffolds_preview": [
            {"scaffold": item["scaffold"], "record_count": item["record_count"]}
            for item in top_scaffolds[:10]
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
