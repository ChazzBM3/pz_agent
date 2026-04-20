from __future__ import annotations

from datetime import datetime, timezone


CONTRACT_VERSION = "atomisticskills.request_response.v1"


class AtomisticSkillsBackend:
    name = "atomisticskills"

    def submit(
        self,
        *,
        candidate_id: str,
        queue_rank: int | None,
        job_spec_path: str,
        simulation: dict,
        submit_config: dict,
    ) -> dict:
        submission_prefix = str(submit_config.get("submission_prefix", "stub-submit"))
        remote_target = submit_config.get("remote_target") or simulation.get("parameters", {}).get("remote_target")
        submission_id = f"{submission_prefix}-{(queue_rank or 0):03d}"
        return {
            "contract_version": CONTRACT_VERSION,
            "request_type": "submit_simulation",
            "response_type": "submission_ack",
            "candidate_id": candidate_id,
            "queue_rank": queue_rank,
            "status": "submitted",
            "backend": simulation.get("backend"),
            "engine": simulation.get("engine"),
            "skill": simulation.get("skill"),
            "execution_mode": simulation.get("execution_mode"),
            "remote_target": remote_target,
            "job_spec_path": job_spec_path,
            "submission_id": submission_id,
            "job_id": None,
            "check_only": False,
            "remote_settings": {"target": remote_target},
            "status_query": {
                "check_only": True,
                "submission_id": submission_id,
                "job_id": None,
            },
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
