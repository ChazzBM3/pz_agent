from __future__ import annotations

from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.io import read_json, write_json
from pz_agent.state import RunState


def _load_rerun_candidates(state: RunState) -> list[dict]:
    path = state.run_dir / "simulation_rerun_candidates.json"
    if not path.exists():
        return []
    payload = read_json(path)
    return payload if isinstance(payload, list) else []


class SimulationRerunPrepareAgent(BaseAgent):
    name = "simulation_rerun_prepare"

    def run(self, state: RunState) -> RunState:
        rerun_cfg = dict((state.config.get("simulation_rerun_prepare", {}) or {}))
        candidates = _load_rerun_candidates(state)
        retry_prefix = str(rerun_cfg.get("retry_prefix", "retry"))

        rerun_queue: list[dict] = []
        for idx, item in enumerate(candidates, start=1):
            rerun_bundle = dict(item.get("rerun_bundle") or {})
            simulation = dict(rerun_bundle.get("simulation") or {})
            candidate_id = str(item.get("candidate_id") or rerun_bundle.get("candidate_id") or f"rerun-{idx}")
            previous_submission_id = item.get("submission_id") or rerun_bundle.get("submission_id")
            original_job_spec_path = rerun_bundle.get("job_spec_path")
            parameters = dict(simulation.get("parameters") or {})
            parameters["special_option"] = ""
            simulation["parameters"] = parameters
            retry_id = f"{retry_prefix}-{idx:03d}"
            rerun_record = {
                "candidate_id": candidate_id,
                "retry_id": retry_id,
                "retry_index": idx,
                "status": "queued_for_later_rerun",
                "source_failure": {
                    "submission_id": previous_submission_id,
                    "job_id": item.get("job_id"),
                    "failure_source": item.get("failure_source"),
                    "raw_status": item.get("status"),
                },
                "simulation": simulation,
                "job_spec_path": original_job_spec_path,
                "retry_metadata": {
                    "retry_prefix": retry_prefix,
                    "previous_submission_id": previous_submission_id,
                    "original_job_spec_path": original_job_spec_path,
                    "rerun_ready": bool(item.get("rerun_ready")),
                    "deferred": True,
                    "adjustments": {
                        "special_option": parameters.get("special_option"),
                        "soscf_enabled": True,
                    },
                },
            }
            rerun_queue.append(rerun_record)

        state.simulation_rerun_queue = rerun_queue
        write_json(state.run_dir / "simulation_rerun_queue.json", rerun_queue)
        state.log(f"Simulation rerun prepare built {len(rerun_queue)} deferred rerun queue records from preserved failures")
        return state
