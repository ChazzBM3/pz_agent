from __future__ import annotations

import json
from pathlib import Path

from pz_agent.visual_benchmark import build_visual_benchmark_report



def test_build_visual_benchmark_report_writes_expected_candidates(tmp_path: Path) -> None:
    report = build_visual_benchmark_report(
        candidate_ids=["05TRCY", "05BCMO"],
        out_dir=tmp_path,
        d3tales_path=Path("data/d3tales.csv"),
    )

    assert report["candidate_ids"] == ["05TRCY", "05BCMO"]
    assert len(report["results"]) == 2
    assert {row["candidate_id"] for row in report["results"]} == {"05TRCY", "05BCMO"}
    for row in report["results"]:
        assert "stub_queries" in row
        assert "fused_queries" in row
        assert row["gemini_status"] in {"image_unavailable", "gemini_api_key_missing", "gemini_ok"}

    payload = json.loads((tmp_path / "visual_benchmark.json").read_text(encoding="utf-8"))
    assert payload["candidate_ids"] == ["05TRCY", "05BCMO"]
