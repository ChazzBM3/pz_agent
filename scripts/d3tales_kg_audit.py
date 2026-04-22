from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from pz_agent.data.d3tales_loader import MEASUREMENT_FIELDS
from pz_agent.kg.d3tales_ingest import ingest_d3tales_csv


def _count_zero_information_rows(csv_path: Path) -> tuple[int, list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nonempty_measurements = [field for field in MEASUREMENT_FIELDS if (row.get(field) or "").strip()]
            if nonempty_measurements:
                continue
            rows.append(
                {
                    "_id": (row.get("_id") or "").strip(),
                    "smiles": (row.get("smiles") or "").strip(),
                    "source_group": (row.get("source_group") or "").strip() or None,
                    "nonempty_measurements": nonempty_measurements,
                }
            )
    return len(rows), rows


def _graph_counts(graph: dict) -> dict[str, object]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types": dict(Counter(node.get("type") for node in nodes)),
        "edge_types": dict(Counter(edge.get("type") for edge in edges)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and audit D3TaLES KG artifacts.")
    parser.add_argument("--csv", default="data/d3tales.csv")
    parser.add_argument("--outdir", default="artifacts/kg_prod_2026_04_22")
    parser.add_argument("--limit", type=int, default=50000)
    args = parser.parse_args()

    csv_path = Path(args.csv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    raw_path = outdir / "d3tales_kg.json"
    filtered_path = outdir / "d3tales_kg.filtered.json"
    audit_path = outdir / "d3tales_kg_audit.json"

    raw_graph = ingest_d3tales_csv(csv_path, output_graph_path=raw_path, limit=args.limit, exclude_zero_information_rows=False)
    filtered_graph = ingest_d3tales_csv(csv_path, output_graph_path=filtered_path, limit=args.limit, exclude_zero_information_rows=True)

    zero_count, zero_rows = _count_zero_information_rows(csv_path)
    audit = {
        "csv_path": str(csv_path),
        "limit": args.limit,
        "zero_information_row_count": zero_count,
        "zero_information_rows": zero_rows,
        "raw_graph": _graph_counts(raw_graph),
        "filtered_graph": _graph_counts(filtered_graph),
        "diff": {
            "node_count_removed": len(raw_graph.get("nodes", [])) - len(filtered_graph.get("nodes", [])),
            "edge_count_removed": len(raw_graph.get("edges", [])) - len(filtered_graph.get("edges", [])),
        },
    }
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
