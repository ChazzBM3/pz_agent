from __future__ import annotations

from typing import Any

from pz_agent.chemistry.normalize import normalize_library


def standardize_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return normalize_library(candidates)
