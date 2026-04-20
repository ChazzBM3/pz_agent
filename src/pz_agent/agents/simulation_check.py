from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.simulation.backends import get_simulation_backend
from pz_agent.state import RunState


class SimulationCheckAgent(BaseAgent):
    name = "simulation_check"

    def run(self, state: RunState) -> RunState:
        queue = list(state.simulation_queue or [])
        check_cfg = dict((state.config.get("simulation_check", {}) or {}))

        checks: list[dict] = []
        failures: list[dict] = []
        for item in queue:
            simulation = dict(item.get("simulation") or {})
            submission = dict(item.get("submission") or {})
            if not submission:
                continue
            backend = get_simulation_backend(str(simulation.get("backend") or submission.get("backend") or "atomisticskills"))
            check = backend.check(
                candidate_id=str(item.get("candidate_id") or item.get("id") or "unknown_candidate"),
                submission=submission,
                simulation=simulation,
                check_config=check_cfg,
            )
            checks.append(check)
            if str(check.get("status") or "").strip().lower() == "failed":
                failures.append(check)
            tracking = dict(item.get("tracking") or {})
            tracking["last_check"] = check
            tracking["status"] = check.get("status", tracking.get("status"))
            item["tracking"] = tracking
            item["status"] = check.get("status", item.get("status"))
            item["check"] = check

        state.simulation_checks = checks
        state.simulation_failures = failures
        state.simulation_queue = queue
        write_json(state.run_dir / "simulation_checks.json", checks)
        write_json(state.run_dir / "simulation_failures.json", failures)
        write_json(state.run_dir / "simulation_queue.json", queue)
        state.log(f"Simulation check recorded {len(checks)} status envelopes for submitted jobs and {len(failures)} failures")
        return state
