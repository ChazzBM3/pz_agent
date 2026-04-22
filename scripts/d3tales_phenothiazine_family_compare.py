from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

PHENOTHIAZINE_SCAFFOLDS = {
    "C1=CC2Nc3ccccc3SC2C=C1",
    "c1ccc2c(c1)Nc1ccccc1S2",
    "C1=CC2Nc3ccc(N(c4ccccc4)c4ccccc4)cc3SC2C=C1",
}

TRACKED_PROPERTIES = [
    "oxidation_potential",
    "reduction_potential",
    "groundState.solvation_energy",
    "groundState.homo",
    "groundState.lumo",
    "groundState.homo_lumo_gap",
]


def _stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    mid = n // 2
    median = values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2.0
    return {
        "count": n,
        "min": values[0],
        "median": median,
        "max": values[-1],
        "mean": sum(values) / n,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare phenothiazine-family scaffolds in the filtered production KG.")
    parser.add_argument("--kg", default="artifacts/kg_prod_2026_04_22/d3tales_kg.filtered.json")
    parser.add_argument("--out", default="artifacts/kg_prod_2026_04_22/d3tales_phenothiazine_family_compare.json")
    args = parser.parse_args()

    kg = json.loads(Path(args.kg).read_text())
    nodes = {node["id"]: node for node in kg.get("nodes", [])}

    scaffold_smiles_by_id = {}
    molecule_attrs = {}
    measurement_attrs = {}
    property_names = {}
    scaffold_to_molecules: dict[str, set[str]] = defaultdict(set)
    molecule_to_measurements: dict[str, list[str]] = defaultdict(list)
    measurement_to_property: dict[str, str] = {}

    for node_id, node in nodes.items():
        t = node.get("type")
        attrs = node.get("attrs") or {}
        if t == "Scaffold":
            scaffold_smiles_by_id[node_id] = attrs.get("smiles")
        elif t == "Molecule":
            molecule_attrs[node_id] = attrs
        elif t == "Measurement":
            measurement_attrs[node_id] = attrs
        elif t == "Property":
            property_names[node_id] = attrs.get("name")

    for edge in kg.get("edges", []):
        et = edge.get("type")
        if et == "HAS_SCAFFOLD":
            scaffold_to_molecules[edge["target"]].add(edge["source"])
        elif et == "MEASURED_FOR":
            molecule_to_measurements[edge["target"]].append(edge["source"])
        elif et == "HAS_PROPERTY":
            measurement_to_property[edge["source"]] = edge["target"]

    families = []
    for scaffold_id, smiles in scaffold_smiles_by_id.items():
        if smiles not in PHENOTHIAZINE_SCAFFOLDS:
            continue
        molecules = sorted(scaffold_to_molecules.get(scaffold_id, []))
        source_groups = Counter()
        property_values = {prop: [] for prop in TRACKED_PROPERTIES}
        for molecule_id in molecules:
            attrs = molecule_attrs.get(molecule_id, {})
            provenance = attrs.get("provenance") or {}
            source_groups[provenance.get("source_group") or attrs.get("source_group") or "<missing>"] += 1
            for measurement_id in molecule_to_measurements.get(molecule_id, []):
                prop_id = measurement_to_property.get(measurement_id)
                prop_name = property_names.get(prop_id)
                if prop_name in property_values:
                    value = (measurement_attrs.get(measurement_id) or {}).get("value")
                    if isinstance(value, (int, float)):
                        property_values[prop_name].append(float(value))
        families.append(
            {
                "scaffold_smiles": smiles,
                "molecule_count": len(molecules),
                "source_groups": dict(source_groups),
                "property_stats": {prop: _stats(vals) for prop, vals in property_values.items()},
            }
        )

    families.sort(key=lambda item: (-item["molecule_count"], item["scaffold_smiles"]))
    out = {
        "kg_path": args.kg,
        "families": families,
        "notes": [
            "These scaffold families can serve as direct anchors for phenothiazine-family transfer analysis.",
            "Source-group composition helps distinguish which scaffold neighborhoods are coming from which campaigns or datasets.",
            "Property distribution summaries are more useful for prioritization than coverage alone.",
        ],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
