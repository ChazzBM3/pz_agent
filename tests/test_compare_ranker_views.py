from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_compare_ranker_views_accepts_single_state_file(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    out_path = tmp_path / "report.json"
    state_path.write_text(
        json.dumps(
            {
                "ranked": [
                    {"id": "cand-a"},
                    {"id": "cand-b"},
                    {"id": "cand-c"},
                ],
                "novelty_ranked": [
                    {"id": "cand-b"},
                    {"id": "cand-c"},
                    {"id": "cand-a"},
                ],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            ".venv/bin/python",
            "scripts/compare_ranker_views.py",
            "--state",
            str(state_path),
            "--out",
            str(out_path),
            "--top",
            "2",
        ],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
    )

    report = json.loads(out_path.read_text())
    assert report["support_top_ids"] == ["cand-a", "cand-b"]
    assert report["novelty_top_ids"] == ["cand-b", "cand-c"]
    assert report["top_overlap_count"] == 1
    assert report["biggest_novelty_risers"][0]["id"] == "cand-b"
