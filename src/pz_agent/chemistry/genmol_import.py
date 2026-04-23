from __future__ import annotations

import math
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
    external_synthesizability: float | None = None
    external_solubility: float | None = None
    external_solubility_units: str | None = None
    sa_score: float | None = None
    logS_mol_L: float | None = None
    S_mg_mL: float | None = None
    Sol_Class: str | None = None
    solp_logS: float | None = None
    generated_index: int | None = None
    lowest_energy: float | None = None
    lowest_energy_conformer_id: int | None = None
    force_field: str | None = None
    num_conformers_embedded: int | None = None
    atom_symbols: list[str] | None = None
    coordinates_angstrom: list[list[float]] | None = None
    generation_metadata: dict[str, Any] | None = None
    site_fragments: list[dict[str, Any]] | None = None
    site_outputs: list[dict[str, Any]] | None = None


def _clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _normalize_sa_score(sa_score: Any) -> float | None:
    value = _safe_float(sa_score)
    if value is None:
        return None
    return _clip((10.0 - value) / 9.0)


def _normalize_logs(logs_value: Any) -> float | None:
    value = _safe_float(logs_value)
    if value is None:
        return None
    return _clip((value + 8.0) / 8.0)


def _normalize_genmol_result_row(row: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    item = dict(row)
    solubility_log = _safe_float(item.get("solp_logS"))
    if solubility_log is None:
        solubility_log = _safe_float(item.get("logS_mol_L"))

    item.setdefault("external_synthesizability", _normalize_sa_score(item.get("sa_score")))
    item.setdefault("external_solubility", _normalize_logs(solubility_log))
    if item.get("external_solubility_units") is None and solubility_log is not None:
        item["external_solubility_units"] = "normalized_from_logS_mol_L"

    if payload:
        item.setdefault("generation_metadata", payload.get("metadata") or {})
        item.setdefault("site_fragments", payload.get("site_fragments") or [])
        item.setdefault("site_outputs", payload.get("site_outputs") or [])

    return item


def _load_json_candidates(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
        return [_normalize_genmol_result_row(row, payload=data) for row in data["results"] if isinstance(row, dict)]
    if isinstance(data, dict) and "candidates" in data:
        return list(data["candidates"])
    if isinstance(data, list):
        return list(data)
    raise ValueError("JSON GenMol import must be a list, contain 'candidates', or be a workflow payload with 'results'")


def _resolve_import_path(path: Path) -> Path:
    if path.is_dir():
        candidates = [
            path / "lowest_energy_conformers.json",
            path / "global_ranked.json",
            path / "combined_results.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise ValueError(
            f"GenMol import directory {path} did not contain a supported payload "
            f"(expected one of: {', '.join(p.name for p in candidates)})"
        )
    return path


def load_external_genmol_candidates(path: str | Path) -> list[dict[str, Any]]:
    path = _resolve_import_path(Path(path))
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported GenMol import format: {suffix}")

    if suffix == ".json":
        rows = _load_json_candidates(path)
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
        if not candidate.get("id"):
            candidate["id"] = f"genmol_{idx:04d}"
        candidate["generation_engine"] = "genmol_external"
        candidate["generation_source_path"] = str(source_path)
        candidate.setdefault("generation_metadata", run_metadata)
        enriched.append(candidate)
    return enriched
