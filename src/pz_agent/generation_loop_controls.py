from __future__ import annotations

from typing import Any, Mapping, Sequence


SUPPORTED_OBJECTIVES = ("solubility", "synthesizability")


def _normalize_primary_objectives(primary_objectives: Sequence[str] | None) -> list[str]:
    normalized: list[str] = []
    for item in primary_objectives or []:
        value = str(item)
        if value in SUPPORTED_OBJECTIVES and value not in normalized:
            normalized.append(value)
    return normalized or ["solubility", "synthesizability"]


def _normalize_metric_controls(raw: Mapping[str, Any] | None, defaults: Mapping[str, float]) -> dict[str, float]:
    normalized = {metric: float(value) for metric, value in defaults.items()}
    for metric in SUPPORTED_OBJECTIVES:
        if raw is not None and metric in raw and raw.get(metric) is not None:
            normalized[metric] = float(raw.get(metric) or 0.0)
    return normalized


def build_loop_controls(
    *,
    config: Mapping[str, Any] | None = None,
    primary_objectives: Sequence[str] | None = None,
    convergence_tolerance: Mapping[str, Any] | None = None,
    taper_min_improvement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config_dict = dict(config or {})
    generation_cfg = dict(config_dict.get("generation", {}) or {})
    loop_cfg = dict(generation_cfg.get("loop", {}) or {})
    screening_cfg = dict(config_dict.get("screening", {}) or {})
    default_convergence = _normalize_metric_controls(
        loop_cfg.get("convergence_tolerance"),
        {"solubility": 0.01, "synthesizability": 0.01},
    )
    default_taper = _normalize_metric_controls(
        loop_cfg.get("taper_min_improvement"),
        {"solubility": 0.0, "synthesizability": 0.0},
    )

    resolved_primary_objectives = _normalize_primary_objectives(
        primary_objectives if primary_objectives is not None else (screening_cfg.get("primary_objectives") or [])
    )
    resolved_convergence = _normalize_metric_controls(
        convergence_tolerance,
        default_convergence,
    )
    resolved_taper = _normalize_metric_controls(
        taper_min_improvement,
        default_taper,
    )

    return {
        "primary_objectives": resolved_primary_objectives,
        "convergence_tolerance": resolved_convergence,
        "taper_min_improvement": resolved_taper,
    }
