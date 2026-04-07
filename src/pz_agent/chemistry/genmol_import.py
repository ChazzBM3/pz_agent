from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pz_agent.io import read_csv, read_json


SUPPORTED_SUFFIXES = {".json", ".csv"}


class ImportedGenMolCandidate(BaseModel):
    id: str | None = None
    smiles: str = Field(min_length=1)
    name: str | None = None
    prompt: str | None = None
    seed: str | int | None = None
    score: float | None = None
    generation_round: str | int | None = None
    notes: str | None = None



def load_external_genmol_candidates(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported GenMol import format: {suffix}")

    if suffix == ".json":
        data = read_json(path)
        if isinstance(data, dict) and "candidates" in data:
            rows = list(data["candidates"])
        elif isinstance(data, list):
            rows = list(data)
        else:
            raise ValueError("JSON GenMol import must be a list or contain a 'candidates' field")
    else:
        rows = read_csv(path)

    validated: list[dict[str, Any]] = []
    for row in rows:
        validated.append(ImportedGenMolCandidate.model_validate(row).model_dump())
    return validated



def attach_genmol_provenance(candidates: list[dict[str, Any]], source_path: str | Path, run_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for idx, item in enumerate(candidates, start=1):
        candidate = dict(item)
        candidate.setdefault("id", f"genmol_{idx:04d}")
        candidate["generation_engine"] = "genmol_external"
        candidate["generation_source_path"] = str(source_path)
        candidate["generation_metadata"] = run_metadata
        enriched.append(candidate)
    return enriched
