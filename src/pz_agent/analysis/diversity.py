from __future__ import annotations

from typing import Any


def diversify_placeholder(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    diversified: list[dict[str, Any]] = []
    for row in rows:
        key = row.get("id")
        if key in seen:
            continue
        seen.add(key)
        diversified.append(row)
    return diversified
