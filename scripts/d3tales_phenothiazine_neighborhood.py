from __future__ import annotations

import argparse
import json
from pathlib import Path

PHENOTHIAZINE_SCAFFOLDS = {
    "C1=CC2Nc3ccccc3SC2C=C1",
    "c1ccc2c(c1)Nc1ccccc1S2",
}


def _mean_range(scaffold: dict, property_name: str) -> dict:
    info = scaffold.get("property_coverage", {}).get(property_name, {})
    return {
        "count": info.get("count", 0),
        "fraction": info.get("fraction", 0.0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize phenothiazine scaffold neighborhood from scaffold summary.")
    parser.add_argument("--summary", default="artifacts/kg_prod_2026_04_22/d3tales_scaffold_summary.json")
    parser.add_argument("--out", default="artifacts/kg_prod_2026_04_22/d3tales_phenothiazine_neighborhood.json")
    args = parser.parse_args()

    summary = json.loads(Path(args.summary).read_text())
    scaffolds = summary.get("top_scaffolds", []) + summary.get("sparse_promising_scaffolds", []) + summary.get("phenothiazine_like_scaffolds", [])
    dedup = {}
    for item in scaffolds:
        dedup[item["scaffold_smiles"]] = item
    all_scaffolds = list(dedup.values())

    phenothiazines = [item for item in all_scaffolds if item["scaffold_smiles"] in PHENOTHIAZINE_SCAFFOLDS]
    comparators = [
        item for item in all_scaffolds
        if item["scaffold_smiles"] not in PHENOTHIAZINE_SCAFFOLDS and item.get("molecule_count", 0) >= 20
    ]
    comparators = sorted(
        comparators,
        key=lambda item: (
            -item.get("property_coverage", {}).get("oxidation_potential", {}).get("fraction", 0.0),
            -item.get("molecule_count", 0),
        ),
    )[:20]

    report = {
        "phenothiazine_scaffolds": [
            {
                "scaffold_smiles": item["scaffold_smiles"],
                "molecule_count": item["molecule_count"],
                "avg_property_coverage": item["avg_property_coverage"],
                "oxidation_potential": _mean_range(item, "oxidation_potential"),
                "reduction_potential": _mean_range(item, "reduction_potential"),
                "groundState.solvation_energy": _mean_range(item, "groundState.solvation_energy"),
                "groundState.homo": _mean_range(item, "groundState.homo"),
                "groundState.lumo": _mean_range(item, "groundState.lumo"),
            }
            for item in phenothiazines
        ],
        "comparison_scaffolds": [
            {
                "scaffold_smiles": item["scaffold_smiles"],
                "molecule_count": item["molecule_count"],
                "avg_property_coverage": item["avg_property_coverage"],
                "oxidation_potential": _mean_range(item, "oxidation_potential"),
                "reduction_potential": _mean_range(item, "reduction_potential"),
            }
            for item in comparators
        ],
        "narrative_notes": [
            "Phenothiazine-like scaffold families are present with strong property coverage and should be treated as anchor neighborhoods rather than sparse edge cases.",
            "The broader dataset is dominated by generic aromatic scaffolds, so scaffold-family targeting is more meaningful than raw whole-dataset frequency.",
            "Transfer-learning or analogical ranking should likely compare phenothiazine scaffold neighborhoods against well-covered nearby scaffold families rather than the full dataset at once.",
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
