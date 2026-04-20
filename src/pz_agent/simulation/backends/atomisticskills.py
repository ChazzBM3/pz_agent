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
        retry_suffix = str(submit_config.get("retry_suffix") or "").strip()
        base_submission_id = f"{submission_prefix}-{(queue_rank or 0):03d}"
        submission_id = f"{base_submission_id}-{retry_suffix}" if retry_suffix else base_submission_id
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
            "retry_suffix": retry_suffix or None,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

    def check(
        self,
        *,
        candidate_id: str,
        submission: dict,
        simulation: dict,
        check_config: dict,
    ) -> dict:
        remote_target = submission.get("remote_target") or simulation.get("parameters", {}).get("remote_target")
        status = str(check_config.get("default_status", submission.get("status", "submitted")))
        authoritative = "default_status" in check_config
        return {
            "contract_version": CONTRACT_VERSION,
            "request_type": "check_simulation",
            "response_type": "status_envelope",
            "candidate_id": candidate_id,
            "submission_id": submission.get("submission_id"),
            "job_id": submission.get("job_id"),
            "status": status,
            "backend": submission.get("backend") or simulation.get("backend"),
            "engine": submission.get("engine") or simulation.get("engine"),
            "skill": submission.get("skill") or simulation.get("skill"),
            "execution_mode": submission.get("execution_mode") or simulation.get("execution_mode"),
            "remote_target": remote_target,
            "check_only": True,
            "authoritative": authoritative,
            "remote_settings": {"target": remote_target},
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
