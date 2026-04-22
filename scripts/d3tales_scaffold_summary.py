from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize scaffold structure from a D3TaLES KG artifact.")
    parser.add_argument("--kg", default="artifacts/kg_prod_2026_04_22/d3tales_kg.filtered.json")
    parser.add_argument("--out", default="artifacts/kg_prod_2026_04_22/d3tales_scaffold_summary.json")
    args = parser.parse_args()

    kg = json.loads(Path(args.kg).read_text())
    nodes = {node["id"]: node for node in kg.get("nodes", [])}
    scaffold_to_molecules: dict[str, set[str]] = defaultdict(set)
    molecule_to_measurements: dict[str, list[str]] = defaultdict(list)
    property_names: dict[str, str] = {}

    for node in nodes.values():
        if node.get("type") == "Property":
            property_names[node["id"]] = (node.get("attrs") or {}).get("name")

    measurement_to_property: dict[str, str] = {}
    for edge in kg.get("edges", []):
        if edge.get("type") == "HAS_SCAFFOLD":
            scaffold_to_molecules[edge["target"]].add(edge["source"])
        elif edge.get("type") == "MEASURED_FOR":
            molecule_to_measurements[edge["target"]].append(edge["source"])
        elif edge.get("type") == "HAS_PROPERTY":
            measurement_to_property[edge["source"]] = edge["target"]

    summaries = []
    for scaffold_id, molecules in scaffold_to_molecules.items():
        scaffold_node = nodes.get(scaffold_id, {})
        scaffold_smiles = ((scaffold_node.get("attrs") or {}).get("smiles"))
        property_counts = Counter()
        measurement_total = 0
        for molecule_id in molecules:
            seen = set()
            for measurement_id in molecule_to_measurements.get(molecule_id, []):
                prop_id = measurement_to_property.get(measurement_id)
                prop_name = property_names.get(prop_id)
                if prop_name:
                    property_counts[prop_name] += 1
                    seen.add(prop_name)
            measurement_total += len(seen)
        molecule_count = len(molecules)
        summaries.append(
            {
                "scaffold_id": scaffold_id,
                "scaffold_smiles": scaffold_smiles,
                "molecule_count": molecule_count,
                "avg_property_coverage": measurement_total / molecule_count if molecule_count else 0.0,
                "property_coverage": {
                    prop: {
                        "count": count,
                        "fraction": count / molecule_count if molecule_count else 0.0,
                    }
                    for prop, count in sorted(property_counts.items())
                },
            }
        )

    summaries.sort(key=lambda item: (-item["molecule_count"], item["scaffold_smiles"] or ""))
    top = summaries[:50]
    phenothiazine_like = [
        item for item in summaries
        if item.get("scaffold_smiles") in {"C1=CC2Nc3ccccc3SC2C=C1", "c1ccc2c(c1)Nc1ccccc1S2"}
    ]
    sparse_promising = [
        item for item in summaries
        if 3 <= item["molecule_count"] <= 25 and item["property_coverage"].get("oxidation_potential", {}).get("fraction", 0.0) >= 0.5
    ][:50]

    out = {
        "kg_path": args.kg,
        "unique_scaffold_count": len(summaries),
        "top_scaffolds": top,
        "phenothiazine_like_scaffolds": phenothiazine_like,
        "sparse_promising_scaffolds": sparse_promising,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({
        "unique_scaffold_count": len(summaries),
        "top_scaffolds_preview": [
            {"scaffold_smiles": item["scaffold_smiles"], "molecule_count": item["molecule_count"]}
            for item in top[:10]
        ],
        "phenothiazine_like_scaffold_count": len(phenothiazine_like),
        "sparse_promising_count": len(sparse_promising),
    }, indent=2))


if __name__ == "__main__":
    main()
