from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunState:
    config: dict[str, Any]
    run_dir: Path
    library_raw: list[dict[str, Any]] | None = None
    library_clean: list[dict[str, Any]] | None = None
    descriptors: list[dict[str, Any]] | None = None
    predictions: list[dict[str, Any]] | None = None
    benchmark: dict[str, Any] | None = None
    ranked: list[dict[str, Any]] | None = None
    shortlist: list[dict[str, Any]] | None = None
    dft_queue: list[dict[str, Any]] | None = None
    validation: list[dict[str, Any]] | None = None
    knowledge_graph_path: Path | None = None
    critique_notes: list[dict[str, Any]] | None = None
    media_registry: list[dict[str, Any]] | None = None
    generation_registry: list[dict[str, Any]] | None = None
    visual_registry: list[dict[str, Any]] | None = None
    structure_expansion: list[dict[str, Any]] | None = None
    patent_registry: list[dict[str, Any]] | None = None
    scholarly_registry: list[dict[str, Any]] | None = None
    page_registry: list[dict[str, Any]] | None = None
    document_registry: list[dict[str, Any]] | None = None
    figure_registry: list[dict[str, Any]] | None = None
    page_image_registry: list[dict[str, Any]] | None = None
    multimodal_registry: list[dict[str, Any]] | None = None
    ocr_registry: list[dict[str, Any]] | None = None
    expansion_registry: list[dict[str, Any]] | None = None
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(message)
