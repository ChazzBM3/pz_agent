from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_rows(path: Path, preferred_keys: list[str] | None = None) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        keys = list(preferred_keys or []) + ["ranked", "novelty_ranked", "rows", "items"]
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
    raise ValueError(f"Could not find ranking rows in {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare support-aware and novelty-aware ranker outputs.")
    parser.add_argument("--support", help="JSON file with support-aware ranked rows")
    parser.add_argument("--novelty", help="JSON file with novelty-aware ranked rows")
    parser.add_argument("--state", help="Optional single JSON file containing both ranked and novelty_ranked")
    parser.add_argument("--out", required=True, help="Output JSON report path")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    if args.state:
        state_path = Path(args.state)
        support_rows = _load_rows(state_path, preferred_keys=["ranked"])
        novelty_rows = _load_rows(state_path, preferred_keys=["novelty_ranked"])
    else:
        if not args.support or not args.novelty:
            raise ValueError("Provide either --state or both --support and --novelty")
        support_rows = _load_rows(Path(args.support), preferred_keys=["ranked"])
        novelty_rows = _load_rows(Path(args.novelty), preferred_keys=["novelty_ranked"])
    support_pos = {row.get("id"): idx + 1 for idx, row in enumerate(support_rows) if row.get("id")}
    novelty_pos = {row.get("id"): idx + 1 for idx, row in enumerate(novelty_rows) if row.get("id")}

    common_ids = [row_id for row_id in support_pos if row_id in novelty_pos]
    movement = []
    for row_id in common_ids:
        movement.append(
            {
                "id": row_id,
                "support_rank": support_pos[row_id],
                "novelty_rank": novelty_pos[row_id],
                "rank_delta": support_pos[row_id] - novelty_pos[row_id],
            }
        )

    biggest_novelty_risers = sorted(movement, key=lambda item: (-item["rank_delta"], item["id"]))[: args.top]
    biggest_support_risers = sorted(movement, key=lambda item: (item["rank_delta"], item["id"]))[: args.top]

    report = {
        "support_path": args.support or args.state,
        "novelty_path": args.novelty or args.state,
        "top_n": args.top,
        "support_top_ids": [row.get("id") for row in support_rows[: args.top]],
        "novelty_top_ids": [row.get("id") for row in novelty_rows[: args.top]],
        "top_overlap_count": len(set(row.get("id") for row in support_rows[: args.top]) & set(row.get("id") for row in novelty_rows[: args.top])),
        "biggest_novelty_risers": biggest_novelty_risers,
        "biggest_support_risers": biggest_support_risers,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
