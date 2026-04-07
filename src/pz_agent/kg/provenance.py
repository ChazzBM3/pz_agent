from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Provenance:
    source_type: str
    source_id: str
    confidence: float | None = None
    model_version: str | None = None
    note: str | None = None
