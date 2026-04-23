from __future__ import annotations

import shlex
import subprocess
from datetime import datetime, timezone

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.state import RunState


class GenerationIterationExecuteAgent(BaseAgent):
    name = "generation_iteration_execute"

    def run(self, state: RunState) -> RunState:
        submit_cfg = dict((state.config.get("generation", {}) or {}).get("submit", {}) or {})
        execute_launch = bool(submit_cfg.get("execute_launch", False))
        launch_mode = str(submit_cfg.get("launch_mode", "noop")).strip().lower() or "noop"
        submissions = list(state.generation_iteration_submissions or [])

        execution_records: list[dict] = []
        for submission in submissions:
            command = str(submission.get("command") or "").strip()
            candidate_id = str(submission.get("candidate_id") or "")
            record = {
                "candidate_id": candidate_id,
                "launcher_mode": submission.get("launcher_mode"),
                "execute_launch": execute_launch,
                "launch_mode": launch_mode,
                "command": command,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            if not execute_launch or not command:
                record.update({
                    "status": "skipped",
                    "reason": "execute_launch_disabled" if not execute_launch else "missing_command",
                    "executed": False,
                })
                execution_records.append(record)
                continue

            if launch_mode == "subprocess_run":
                result = subprocess.run(command, shell=True, text=True, capture_output=True)
                record.update(
                    {
                        "status": "launched" if result.returncode == 0 else "failed",
                        "executed": True,
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }
                )
            elif launch_mode == "nohup_background":
                background_command = f"nohup bash -lc {shlex.quote(command)} >/dev/null 2>&1 &"
                result = subprocess.run(background_command, shell=True, text=True, capture_output=True)
                record.update(
                    {
                        "status": "launched" if result.returncode == 0 else "failed",
                        "executed": True,
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "background_command": background_command,
                    }
                )
            else:
                record.update(
                    {
                        "status": "skipped",
                        "reason": f"unsupported_launch_mode:{launch_mode}",
                        "executed": False,
                    }
                )
            record["finished_at"] = datetime.now(timezone.utc).isoformat()
            execution_records.append(record)

        state.generation_iteration_execution = execution_records
        write_json(state.run_dir / "generation_iteration_execution.json", execution_records)
        launched = sum(1 for item in execution_records if item.get("status") == "launched")
        failed = sum(1 for item in execution_records if item.get("status") == "failed")
        state.log(f"Generation iteration execute processed {len(execution_records)} launch requests ({launched} launched, {failed} failed)")
        return state
