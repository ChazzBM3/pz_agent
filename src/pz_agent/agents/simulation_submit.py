from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.simulation.backends import get_simulation_backend
from pz_agent.state import RunState


class SimulationSubmitAgent(BaseAgent):
    name = "simulation_submit"

    def run(self, state: RunState) -> RunState:
        queue = list(state.simulation_queue or [])
        submit_cfg = dict((state.config.get("simulation_submit", {}) or {}))
        remote_target = submit_cfg.get("remote_target") or (state.config.get("simulation", {}) or {}).get("remote_target")
        submission_prefix = str(submit_cfg.get("submission_prefix", "stub-submit"))

        submissions: list[dict] = []
        for idx, item in enumerate(queue, start=1):
            simulation = dict(item.get("simulation") or {})
            backend = get_simulation_backend(str(simulation.get("backend") or "atomisticskills"))
            submission = backend.submit(
                candidate_id=str(item.get("candidate_id") or item.get("id") or f"candidate-{idx}"),
                queue_rank=item.get("queue_rank"),
                job_spec_path=str((item.get("job_package") or {}).get("job_spec_path") or ""),
                simulation=simulation,
                submit_config={
                    **submit_cfg,
                    "remote_target": remote_target,
                    "submission_prefix": submission_prefix,
                },
            )
            submissions.append(submission)
            tracking = dict(item.get("tracking") or {})
            tracking.update(
                {
                    "submission_id": submission.get("submission_id"),
                    "job_id": submission.get("job_id"),
                    "status": submission.get("status", "submitted"),
                    "remote_target": submission.get("remote_target") or tracking.get("remote_target"),
                    "last_submission": submission,
                }
            )
            item["tracking"] = tracking
            item["status"] = "submitted"
            item["submission"] = submission

        state.simulation_submissions = submissions
        write_json(state.run_dir / "simulation_submissions.json", submissions)
        write_json(state.run_dir / "simulation_queue.json", queue)
        state.log(f"Simulation submit staged {len(submissions)} submission records for remote execution")
        return state
