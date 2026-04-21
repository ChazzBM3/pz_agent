from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pz_agent.io import read_json


CONTRACT_VERSION = "orca_slurm.request_response.v1"


def _remote_job_id(candidate_id: str, queue_rank: int | None, submit_config: dict) -> str:
    prefix = str(submit_config.get("job_id_prefix", "pzjob")).strip() or "pzjob"
    return f"{prefix}-{candidate_id}-{(queue_rank or 0):03d}"


def _staging_details(*, job_id: str, submit_config: dict, job_spec_path: str) -> dict:
    transport = str(submit_config.get("transport", "stub")).strip().lower() or "stub"
    remote_root = submit_config.get("remote_root")
    remote_host = submit_config.get("remote_host")
    remote_submit_command = submit_config.get("remote_submit_command")
    remote_scheduler = str(submit_config.get("remote_scheduler", "slurm")).strip().lower() or "slurm"
    stage_method = str(submit_config.get("stage_method", "scp")).strip().lower() or "scp"

    if transport == "ssh" and remote_root and remote_host:
        remote_job_dir = f"{str(remote_root).rstrip('/')}/inbox/{job_id}"
        local_job_dir = str(Path(job_spec_path).resolve().parent) if job_spec_path else None
        stage_commands = [
            f"mkdir -p {remote_job_dir}",
            f"{stage_method} -r {local_job_dir}/ {remote_host}:{remote_job_dir}/" if local_job_dir else None,
            f"ssh {remote_host} '{remote_submit_command} {remote_job_dir}'" if remote_submit_command else None,
        ]
        return {
            "transport": "ssh",
            "scheduler": remote_scheduler,
            "stage_method": stage_method,
            "remote_host": remote_host,
            "remote_root": remote_root,
            "remote_job_dir": remote_job_dir,
            "local_job_dir": local_job_dir,
            "remote_submit_command": remote_submit_command,
            "expected_remote_artifacts": [
                "status.json",
                "scheduler.json",
                "run.log",
                "result.json",
                "failure.json",
            ],
            "stage_commands": [command for command in stage_commands if command],
        }
    return {"transport": transport, "scheduler": remote_scheduler if transport == "ssh" else None}


def _remote_artifact_local_path(submission: dict, artifact_name: str) -> Path | None:
    staging = dict(submission.get("staging") or {})
    local_job_dir = staging.get("local_job_dir")
    if not local_job_dir:
        return None
    return Path(local_job_dir) / artifact_name


def _run_stage_command(command: str, *, cwd: str | None = None) -> dict:
    result = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        cwd=cwd,
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "ok": result.returncode == 0,
    }


def _remote_status_fetch(submission: dict, check_config: dict) -> dict | None:
    staging = dict(submission.get("staging") or {})
    remote_job_dir = staging.get("remote_job_dir")
    remote_host = check_config.get("remote_host") or staging.get("remote_host")
    transport = str(check_config.get("transport") or staging.get("transport") or "").strip().lower()
    if transport != "ssh" or not remote_job_dir or not remote_host:
        return None

    command = f"ssh {remote_host} 'cat {remote_job_dir.rstrip('/')}/status.json'"
    result = _run_stage_command(command)
    if not result.get("ok") or not result.get("stdout"):
        return {
            "ok": False,
            "command": command,
            "error": result.get("stderr") or result.get("stdout") or "remote status fetch failed",
        }

    import json as _json

    try:
        parsed = _json.loads(result.get("stdout") or "{}")
    except Exception as exc:
        return {
            "ok": False,
            "command": command,
            "error": f"invalid remote status json: {exc}",
        }
    return {
        "ok": True,
        "command": command,
        "payload": parsed,
    }


class AtomisticSkillsBackend:
    name = "orca_slurm"

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
        job_id = _remote_job_id(candidate_id, queue_rank, submit_config)
        staging = _staging_details(job_id=job_id, submit_config=submit_config, job_spec_path=job_spec_path)
        execute_handoff = bool(submit_config.get("execute_handoff", False))
        command_results: list[dict] = []
        status = "submitted"
        response_type = "submission_ack"
        error_message = None

        if execute_handoff and staging.get("transport") == "ssh":
            local_job_dir = staging.get("local_job_dir")
            if local_job_dir:
                Path(local_job_dir, ".submit_handoff_started").write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
            for command in staging.get("stage_commands", []):
                result = _run_stage_command(command)
                command_results.append(result)
                if not result.get("ok"):
                    status = "failed"
                    response_type = "submission_failure"
                    error_message = result.get("stderr") or result.get("stdout") or "remote handoff command failed"
                    break

        return {
            "contract_version": CONTRACT_VERSION,
            "request_type": "submit_simulation",
            "response_type": response_type,
            "candidate_id": candidate_id,
            "queue_rank": queue_rank,
            "status": status,
            "backend": simulation.get("backend"),
            "engine": simulation.get("engine"),
            "job_driver": simulation.get("job_driver"),
            "execution_mode": simulation.get("execution_mode"),
            "remote_target": remote_target,
            "job_spec_path": job_spec_path,
            "submission_id": submission_id,
            "job_id": job_id,
            "check_only": False,
            "remote_settings": {"target": remote_target},
            "staging": staging,
            "handoff_execution": {
                "executed": execute_handoff and staging.get("transport") == "ssh",
                "command_results": command_results,
                "error_message": error_message,
            },
            "status_query": {
                "check_only": True,
                "submission_id": submission_id,
                "job_id": job_id,
                "transport": staging.get("transport"),
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
        status_path = _remote_artifact_local_path(submission, "status.json")
        if status_path and status_path.exists():
            payload = read_json(status_path)
            payload.setdefault("contract_version", CONTRACT_VERSION)
            payload.setdefault("request_type", "check_simulation")
            payload.setdefault("response_type", "status_envelope")
            payload.setdefault("candidate_id", candidate_id)
            payload.setdefault("submission_id", submission.get("submission_id"))
            payload.setdefault("job_id", submission.get("job_id"))
            payload.setdefault("backend", submission.get("backend") or simulation.get("backend"))
            payload.setdefault("engine", submission.get("engine") or simulation.get("engine"))
            payload.setdefault("job_driver", submission.get("job_driver") or simulation.get("job_driver"))
            payload.setdefault("execution_mode", submission.get("execution_mode") or simulation.get("execution_mode"))
            payload.setdefault("remote_target", remote_target)
            payload["check_only"] = True
            payload["authoritative"] = bool(payload.get("authoritative", True))
            payload["remote_settings"] = {"target": remote_target}
            payload["checked_at"] = datetime.now(timezone.utc).isoformat()
            payload["status_source"] = "remote_status_artifact"
            payload["status_path"] = str(status_path)
            return payload

        remote_fetch = _remote_status_fetch(submission, check_config)
        if remote_fetch and remote_fetch.get("ok"):
            payload = dict(remote_fetch.get("payload") or {})
            payload.setdefault("contract_version", CONTRACT_VERSION)
            payload.setdefault("request_type", "check_simulation")
            payload.setdefault("response_type", "status_envelope")
            payload.setdefault("candidate_id", candidate_id)
            payload.setdefault("submission_id", submission.get("submission_id"))
            payload.setdefault("job_id", submission.get("job_id"))
            payload.setdefault("backend", submission.get("backend") or simulation.get("backend"))
            payload.setdefault("engine", submission.get("engine") or simulation.get("engine"))
            payload.setdefault("job_driver", submission.get("job_driver") or simulation.get("job_driver"))
            payload.setdefault("execution_mode", submission.get("execution_mode") or simulation.get("execution_mode"))
            payload.setdefault("remote_target", remote_target)
            payload["check_only"] = True
            payload["authoritative"] = bool(payload.get("authoritative", True))
            payload["remote_settings"] = {"target": remote_target}
            payload["checked_at"] = datetime.now(timezone.utc).isoformat()
            payload["status_source"] = "remote_status_ssh"
            payload["status_fetch"] = {"command": remote_fetch.get("command")}
            return payload

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
            "job_driver": submission.get("job_driver") or simulation.get("job_driver"),
            "execution_mode": submission.get("execution_mode") or simulation.get("execution_mode"),
            "remote_target": remote_target,
            "check_only": True,
            "authoritative": authoritative,
            "remote_settings": {"target": remote_target},
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "status_source": "default_status",
            "status_fetch_error": remote_fetch.get("error") if remote_fetch else None,
        }
