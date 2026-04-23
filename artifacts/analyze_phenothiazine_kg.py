import json
from collections import Counter, defaultdict
from pathlib import Path

kg_path = Path("/Users/chazzm3/.openclaw/workspace/pz_agent/artifacts/kg_prod_2026_04_22/d3tales_kg.json")
out_dir = Path("/Users/chazzm3/.openclaw/workspace/pz_agent/artifacts/presentation_kg")
out_dir.mkdir(parents=True, exist_ok=True)

g = json.loads(kg_path.read_text())
node_by_id = {n["id"]: n for n in g.get("nodes", [])}

pt_scaffold_id = "scaffold::e6008ac24d413469"
pt_scaffold_smiles = None
if pt_scaffold_id in node_by_id:
    pt_scaffold_smiles = (node_by_id[pt_scaffold_id].get("attrs") or {}).get("smiles")

molecule_to_scaffolds = defaultdict(list)
measurement_nodes_for_molecule = defaultdict(list)
for e in g.get("edges", []):
    t = e.get("type")
    if t == "HAS_SCAFFOLD":
        molecule_to_scaffolds[e["source"]].append(e["target"])
    elif t == "MEASURED_FOR":
        n = node_by_id.get(e["source"])
        if n and n.get("type") == "Measurement":
            measurement_nodes_for_molecule[e["target"]].append(n)

pt_molecules = []
for mol_id, scaffolds in molecule_to_scaffolds.items():
    if pt_scaffold_id not in scaffolds:
        continue
    mol = node_by_id.get(mol_id)
    if not mol or mol.get("type") != "Molecule":
        continue
    attrs = mol.get("attrs") or {}
    measurements = measurement_nodes_for_molecule.get(mol_id, [])
    prop_map = defaultdict(list)
    for m in measurements:
        ma = m.get("attrs") or {}
        pname = ma.get("property_name")
        value = ma.get("value")
        if pname and value is not None:
            prop_map[pname].append(value)
    pt_molecules.append({
        "id": mol_id,
        "smiles": attrs.get("smiles"),
        "source_group": attrs.get("source_group"),
        "properties": {k: sorted(v) for k, v in prop_map.items()},
        "property_count": len(prop_map),
        "measurement_count": sum(len(v) for v in prop_map.values()),
    })

property_coverage = Counter()
for row in pt_molecules:
    for pname in row["properties"].keys():
        property_coverage[pname] += 1

top_oxidation = []
for row in pt_molecules:
    vals = row["properties"].get("oxidation_potential")
    if vals:
        top_oxidation.append({
            "id": row["id"],
            "smiles": row["smiles"],
            "source_group": row["source_group"],
            "oxidation_potential": max(vals),
            "reduction_potential": max(row["properties"].get("reduction_potential", [None])) if row["properties"].get("reduction_potential") else None,
            "sa_score": max(row["properties"].get("sa_score", [None])) if row["properties"].get("sa_score") else None,
        })
top_oxidation.sort(key=lambda x: (x["oxidation_potential"], x["id"]), reverse=True)

source_group_counts = Counter(row.get("source_group") or "" for row in pt_molecules)
property_count_distribution = Counter(row["property_count"] for row in pt_molecules)
measurement_count_distribution = Counter(row["measurement_count"] for row in pt_molecules)

summary = {
    "kg_path": str(kg_path),
    "phenothiazine_scaffold_id": pt_scaffold_id,
    "phenothiazine_scaffold_smiles": pt_scaffold_smiles,
    "phenothiazine_molecule_count": len(pt_molecules),
    "property_coverage": dict(property_coverage.most_common()),
    "source_group_counts": dict(source_group_counts.most_common()),
    "property_count_distribution": dict(sorted(property_count_distribution.items())),
    "measurement_count_distribution": dict(sorted(measurement_count_distribution.items())),
    "top_oxidation_potential": top_oxidation[:10],
}

(out_dir / "phenothiazine_summary.json").write_text(json.dumps(summary, indent=2))
(out_dir / "phenothiazine_molecules.json").write_text(json.dumps(pt_molecules, indent=2))
(out_dir / "top_phenothiazines_by_oxidation.json").write_text(json.dumps(top_oxidation, indent=2))

print(json.dumps(summary, indent=2))
