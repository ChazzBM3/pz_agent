from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.simulation.backends import get_simulation_backend
from pz_agent.state import RunState


def _normalize_submit_config(submit_cfg: dict, simulation: dict, job_package: dict) -> dict:
    normalized = dict(submit_cfg)
    backend_name = str(simulation.get("backend") or "").strip().lower()
    if backend_name not in {"htvs", "htvs_orca", "htvs_supercloud"}:
        return normalized

    if not normalized.get("ssh_host"):
        normalized["ssh_host"] = normalized.get("remote_host")
    if not normalized.get("htvs_root"):
        normalized["htvs_root"] = normalized.get("remote_root")
    if not normalized.get("geometry_path"):
        normalized["geometry_path"] = job_package.get("structure_path")
    if not normalized.get("remote_job_root_base"):
        remote_root = str(normalized.get("remote_root") or "").rstrip("/")
        if remote_root:
            normalized["remote_job_root_base"] = f"{remote_root}/inbox"
    if not normalized.get("job_config") and normalized.get("remote_submit_command"):
        normalized["remote_submit_command_legacy"] = normalized.get("remote_submit_command")
    return normalized


class SimulationSubmitAgent(BaseAgent):
    name = "simulation_submit"

    def run(self, state: RunState) -> RunState:
        submit_cfg = dict((state.config.get("simulation_submit", {}) or {}))
        use_rerun_queue = bool(submit_cfg.get("use_rerun_queue", False))
        queue = list(state.simulation_rerun_queue or []) if use_rerun_queue else list(state.simulation_queue or [])
        remote_target = submit_cfg.get("remote_target") or (state.config.get("simulation", {}) or {}).get("remote_target")
        submission_prefix = str(submit_cfg.get("submission_prefix", "stub-submit"))

        submissions: list[dict] = []
        for idx, item in enumerate(queue, start=1):
            simulation = dict(item.get("simulation") or {})
            backend = get_simulation_backend(str(simulation.get("backend") or "atomisticskills"))
            retry_metadata = dict(item.get("retry_metadata") or {})
            retry_suffix = None
            if use_rerun_queue:
                retry_suffix = str(item.get("retry_id") or retry_metadata.get("retry_prefix") or f"retry-{idx:03d}")
            job_package = dict(item.get("job_package") or {})
            submit_payload = _normalize_submit_config(
                {
                    **submit_cfg,
                    "remote_target": remote_target,
                    "submission_prefix": submission_prefix,
                    "retry_suffix": retry_suffix,
                    "job_package": job_package,
                },
                simulation,
                job_package,
            )
            submission = backend.submit(
                candidate_id=str(item.get("candidate_id") or item.get("id") or f"candidate-{idx}"),
                queue_rank=item.get("queue_rank") or item.get("retry_index") or idx,
                job_spec_path=str(job_package.get("job_spec_path") or item.get("job_spec_path") or ""),
                simulation=simulation,
                submit_config=submit_payload,
            )
            submissions.append(submission)
            tracking = dict(item.get("tracking") or {})
            retry_attempt = int(retry_metadata.get("retry_attempt", 0) or 0) + (1 if use_rerun_queue else 0)
            tracking.update(
                {
                    "submission_id": submission.get("submission_id"),
                    "job_id": submission.get("job_id"),
                    "status": submission.get("status", "submitted"),
                    "remote_target": submission.get("remote_target") or tracking.get("remote_target"),
                    "last_submission": submission,
                    "retry_attempt": retry_attempt,
                    "retry_of_submission_id": retry_metadata.get("previous_submission_id"),
                }
            )
            item["tracking"] = tracking
            item["status"] = "submitted"
            item["submission"] = submission
            if use_rerun_queue:
                item["retry_metadata"] = {
                    **retry_metadata,
                    "retry_attempt": retry_attempt,
                    "submitted_retry_submission_id": submission.get("submission_id"),
                }
                item["retry_provenance"] = {
                    "retry_of_submission_id": retry_metadata.get("previous_submission_id"),
                    "retry_attempt": retry_attempt,
                    "retry_id": item.get("retry_id"),
                }

        state.simulation_submissions = submissions
        write_json(state.run_dir / "simulation_submissions.json", submissions)
        if use_rerun_queue:
            state.simulation_rerun_queue = queue
            write_json(state.run_dir / "simulation_rerun_queue.json", queue)
        else:
            state.simulation_queue = queue
            write_json(state.run_dir / "simulation_queue.json", queue)
        state.log(f"Simulation submit staged {len(submissions)} submission records for remote execution")
        return state
