from __future__ import annotations

from typing import Protocol


class SimulationBackend(Protocol):
    name: str

    def submit(
        self,
        *,
        candidate_id: str,
        queue_rank: int | None,
        job_spec_path: str,
        simulation: dict,
        submit_config: dict,
    ) -> dict:
        ...
