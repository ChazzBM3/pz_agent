from __future__ import annotations

from datetime import datetime, timezone

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
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
            parameters = dict(simulation.get("parameters") or {})
            submission = {
                "candidate_id": item.get("candidate_id"),
                "queue_rank": item.get("queue_rank"),
                "status": "submitted",
                "backend": simulation.get("backend"),
                "engine": simulation.get("engine"),
                "skill": simulation.get("skill"),
                "execution_mode": simulation.get("execution_mode"),
                "remote_target": remote_target or parameters.get("remote_target"),
                "job_spec_path": (item.get("job_package") or {}).get("job_spec_path"),
                "submission_id": f"{submission_prefix}-{idx:03d}",
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
            submissions.append(submission)
            item["status"] = "submitted"
            item["submission"] = submission

        state.simulation_submissions = submissions
        write_json(state.run_dir / "simulation_submissions.json", submissions)
        write_json(state.run_dir / "simulation_queue.json", queue)
        state.log(f"Simulation submit staged {len(submissions)} submission records for remote execution")
        return state
