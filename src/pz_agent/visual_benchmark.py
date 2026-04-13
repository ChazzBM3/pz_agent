from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pz_agent.chemistry.normalize import normalize_molecule_identity
from pz_agent.chemistry.visual_identity import (
    PHENOTHIAZINE_VISUAL_PROMPT,
    attach_visual_identity,
    build_visual_identity_stub,
    render_candidate_structure_image,
)
from pz_agent.chemistry.vision_client import DEFAULT_VISION_MODEL, extract_visual_identity_with_gemini
from pz_agent.data.d3tales_loader import load_d3tales_csv
from pz_agent.kg.retrieval import build_candidate_queries


DEFAULT_BENCHMARK_IDS = ["05TRCY", "05PJTD", "05BCMO", "05JHCB"]
DEFAULT_D3TALES_PATH = Path("data/d3tales.csv")


def _load_candidates(candidate_ids: list[str], d3tales_path: str | Path = DEFAULT_D3TALES_PATH) -> list[dict[str, Any]]:
    wanted = {candidate_id.strip() for candidate_id in candidate_ids if candidate_id.strip()}
    records = load_d3tales_csv(d3tales_path)
    found = {record.record_id: record for record in records if record.record_id in wanted}
    missing = [candidate_id for candidate_id in candidate_ids if candidate_id not in found]
    if missing:
        raise ValueError(f"Missing candidate ids in {d3tales_path}: {', '.join(missing)}")
    return [normalize_molecule_identity(found[candidate_id].to_candidate()) for candidate_id in candidate_ids]


def build_visual_benchmark_report(
    candidate_ids: list[str] | None = None,
    out_dir: str | Path = "artifacts/visual_benchmark",
    d3tales_path: str | Path = DEFAULT_D3TALES_PATH,
    model: str = DEFAULT_VISION_MODEL,
) -> dict[str, Any]:
    selected_ids = candidate_ids or list(DEFAULT_BENCHMARK_IDS)
    output_dir = Path(out_dir)
    image_dir = output_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    candidates = _load_candidates(selected_ids, d3tales_path=d3tales_path)
    benchmark_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        candidate_id = str(candidate.get("id"))
        image_path = render_candidate_structure_image(candidate, image_dir)
        stub_bundle = build_visual_identity_stub(candidate, image_path)
        live_bundle = extract_visual_identity_with_gemini(
            image_path=image_path,
            prompt=PHENOTHIAZINE_VISUAL_PROMPT,
            model=model,
        ) if image_path else {
            "vision_status": "image_unavailable",
            "vision_model": model,
            "visual_identity": None,
            "raw_output": None,
        }
        fused_candidate = attach_visual_identity(candidate, image_dir, model=model)

        benchmark_rows.append(
            {
                "candidate_id": candidate_id,
                "smiles": candidate.get("smiles"),
                "image_path": image_path,
                "identity": candidate.get("identity"),
                "stub_visual_identity": stub_bundle.get("visual_identity"),
                "stub_queries": build_candidate_queries({**candidate, "visual_bundle": stub_bundle}),
                "gemini_status": live_bundle.get("vision_status"),
                "gemini_model": live_bundle.get("vision_model"),
                "gemini_visual_identity": live_bundle.get("visual_identity"),
                "gemini_raw_output": live_bundle.get("raw_output"),
                "fused_queries": build_candidate_queries(fused_candidate),
            }
        )

    report = {
        "candidate_ids": selected_ids,
        "model": model,
        "d3tales_path": str(d3tales_path),
        "out_dir": str(output_dir),
        "results": benchmark_rows,
    }
    (output_dir / "visual_benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
