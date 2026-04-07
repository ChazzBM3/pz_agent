from __future__ import annotations

from typing import Any


def compute_basic_descriptors(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidates:
        rows.append({
            "id": item["id"],
            "mw": None,
            "logp": None,
            "hbd": None,
            "hba": None,
            "tpsa": None,
        })
    return rows
