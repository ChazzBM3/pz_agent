from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PredictionProvenance:
    model_name: str
    model_version: str | None = None
    source_type: str = "internal"
    confidence: float | None = None
    units: dict[str, str] | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
