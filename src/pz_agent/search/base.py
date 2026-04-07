from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SearchHit:
    title: str | None
    url: str | None
    snippet: str | None
    source: str
    confidence: float | None = None
    match_type: str = "unknown"


class SearchBackend(Protocol):
    name: str

    def search(self, query: str, count: int = 5) -> list[SearchHit]:
        ...
