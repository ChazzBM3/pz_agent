#!/usr/bin/env python3
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
        if math.isnan(out):
            return None
        return out
    except Exception:
        return None


def canonicalize_smiles(smiles: str) -> str:
    try:
        from rdkit import Chem  # type: ignore

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return smiles
        return Chem.MolToSmiles(mol, canonical=True)
    except Exception:
        return smiles


def detect_results_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "conformers", "records", "molecules", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def pick_smiles(row: dict[str, Any]) -> str | None:
    for key in (
        "smiles",
        "canonical_smiles",
        "generated_smiles",
        "molecule_smiles",
        "lowest_energy_smiles",
    ):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    molecule = row.get("molecule")
    if isinstance(molecule, dict):
        for key in ("smiles", "canonical_smiles"):
            value = molecule.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def best_numeric(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if "." in key:
            current: Any = row
            ok = True
            for part in key.split("."):
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    ok = False
                    break
            if ok:
                value = safe_float(current)
                if value is not None:
                    return value
        else:
            value = safe_float(row.get(key))
            if value is not None:
                return value
    return None


def load_seed_metadata(manifest_path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(manifest_path)
    records = payload.get("records", payload if isinstance(payload, list) else [])
    out = {}
    for row in records:
        if isinstance(row, dict) and row.get("id"):
            out[row["id"]] = row
    return out


def score_row(row: dict[str, Any]) -> tuple[float, float, float, float]:
    logs = row.get("best_logS_mol_L")
    sa = row.get("best_sa_score")
    conf = row.get("best_energy")
    parent_ox = row.get("seed_oxidation_potential")
    return (
        logs if logs is not None else float("-inf"),
        -(sa if sa is not None else float("inf")),
        -(conf if conf is not None else float("inf")),
        parent_ox if parent_ox is not None else float("-inf"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate and deduplicate GenMol CPU run outputs")
    parser.add_argument("--base-dir", required=True, help="Directory containing per-seed result folders")
    parser.add_argument("--seed-manifest", default="artifacts/grimm_genmol_manifest.json")
    parser.add_argument("--out-prefix", default=None, help="Prefix for output files, defaults to <base-dir>/global_ranked")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    seed_manifest = Path(args.seed_manifest)
    out_prefix = Path(args.out_prefix) if args.out_prefix else (base_dir / "global_ranked")
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    seed_meta = load_seed_metadata(seed_manifest)
    all_rows: list[dict[str, Any]] = []
    duplicate_map: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for seed_dir in sorted([p for p in base_dir.iterdir() if p.is_dir()]):
        seed_id = seed_dir.name.split("_", 1)[-1] if "_" in seed_dir.name else seed_dir.name
        meta = seed_meta.get(seed_id, {"id": seed_id})
        sa_path = seed_dir / "sa_scores_ranked.json"
        conf_path = seed_dir / "lowest_energy_conformers.json"
        if not sa_path.exists() and not conf_path.exists():
            continue

        sa_rows = detect_results_list(load_json(sa_path)) if sa_path.exists() else []
        conf_rows = detect_results_list(load_json(conf_path)) if conf_path.exists() else []

        sa_by_smiles: dict[str, dict[str, Any]] = {}
        for row in sa_rows:
            smiles = pick_smiles(row)
            if smiles:
                sa_by_smiles[canonicalize_smiles(smiles)] = row

        conf_by_smiles: dict[str, dict[str, Any]] = {}
        for row in conf_rows:
            smiles = pick_smiles(row)
            if smiles:
                conf_by_smiles[canonicalize_smiles(smiles)] = row

        seen = set(sa_by_smiles) | set(conf_by_smiles)
        for canonical in seen:
            sa_row = sa_by_smiles.get(canonical, {})
            conf_row = conf_by_smiles.get(canonical, {})
            merged = {
                "seed_id": seed_id,
                "seed_smiles": meta.get("smiles"),
                "seed_oxidation_potential": safe_float(meta.get("oxidation_potential")),
                "seed_source_group": meta.get("source_group"),
                "result_dir": str(seed_dir),
                "smiles": sa_row.get("smiles") or conf_row.get("smiles") or canonical,
                "canonical_smiles": canonical,
                "best_sa_score": best_numeric(sa_row, "sa_score", "SA_score", "score", "sascorer"),
                "best_logS_mol_L": best_numeric(
                    sa_row,
                    "logS_mol_L",
                    "logS",
                    "esol",
                    "ESOL",
                    "solubility",
                ),
                "solubility_class": sa_row.get("Sol_Class") or sa_row.get("solubility_class"),
                "best_energy": best_numeric(
                    conf_row,
                    "energy",
                    "lowest_energy",
                    "energy_kcal_mol",
                    "energy_ev",
                    "conformer_energy",
                ),
                "best_conformer_path": conf_row.get("path") or conf_row.get("conformer_path"),
                "sa_rank_within_seed": best_numeric(sa_row, "rank", "sa_rank"),
                "raw_sa_record": sa_row,
                "raw_conf_record": conf_row,
            }
            all_rows.append(merged)
            duplicate_map[canonical].append(merged)

    deduped = []
    for canonical, group in duplicate_map.items():
        ordered = sorted(group, key=score_row, reverse=True)
        best = dict(ordered[0])
        best["appears_in_seed_count"] = len(group)
        best["appears_in_seeds"] = [row["seed_id"] for row in ordered]
        best["duplicate_seed_ids"] = [row["seed_id"] for row in ordered[1:]]
        deduped.append(best)

    deduped.sort(key=score_row, reverse=True)
    for i, row in enumerate(deduped, start=1):
        row["global_rank"] = i

    summary = {
        "base_dir": str(base_dir),
        "seed_manifest": str(seed_manifest),
        "seed_count_seen": len({row["seed_id"] for row in all_rows}),
        "raw_candidate_count": len(all_rows),
        "unique_candidate_count": len(deduped),
        "duplicate_candidate_count": len(all_rows) - len(deduped),
        "top10": [
            {
                "global_rank": row["global_rank"],
                "canonical_smiles": row["canonical_smiles"],
                "seed_id": row["seed_id"],
                "best_logS_mol_L": row["best_logS_mol_L"],
                "best_sa_score": row["best_sa_score"],
                "best_energy": row["best_energy"],
                "appears_in_seed_count": row["appears_in_seed_count"],
            }
            for row in deduped[:10]
        ],
    }

    json_path = out_prefix.with_suffix(".json")
    csv_path = out_prefix.with_suffix(".csv")
    summary_path = out_prefix.with_name(out_prefix.name + "_summary.json")

    json_path.write_text(json.dumps(deduped, indent=2))
    summary_path.write_text(json.dumps(summary, indent=2))

    fieldnames = [
        "global_rank",
        "canonical_smiles",
        "smiles",
        "seed_id",
        "seed_smiles",
        "seed_oxidation_potential",
        "seed_source_group",
        "best_logS_mol_L",
        "best_sa_score",
        "best_energy",
        "solubility_class",
        "sa_rank_within_seed",
        "appears_in_seed_count",
        "appears_in_seeds",
        "duplicate_seed_ids",
        "result_dir",
        "best_conformer_path",
    ]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in deduped:
            out = {k: row.get(k) for k in fieldnames}
            out["appears_in_seeds"] = ";".join(row.get("appears_in_seeds", []))
            out["duplicate_seed_ids"] = ";".join(row.get("duplicate_seed_ids", []))
            writer.writerow(out)

    print(json.dumps(summary, indent=2))
    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
