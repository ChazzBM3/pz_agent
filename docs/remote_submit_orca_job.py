#!/usr/bin/env python3
from __future__ import annotations

"""Thin remote wrapper template for AtomisticSkills ORCA submission.

This script is intentionally conservative. It is a template for the supercomputer
side, not a drop-in final production runner.

Expected usage:
    python remote_submit_orca_job.py /path/to/remote_root/inbox/<job_id>

Recommended behavior:
- validate `orca_job.json` and `input_structure.xyz`
- move job directory into `running/`
- update `status.json`
- invoke AtomisticSkills and or the scheduler wrapper
- write `result.json` or `failure.json`
- move the directory into `completed/` or `failed/`
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "atomisticskills.request_response.v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def status_payload(job_spec: dict[str, Any], *, status: str, job_id: str, scheduler: dict[str, Any] | None = None, message: str | None = None) -> dict[str, Any]:
    operation = dict(job_spec.get("operation") or {})
    remote_settings = dict(operation.get("remote_settings") or {})
    payload = {
        "contract_version": CONTRACT_VERSION,
        "request_type": "check_simulation",
        "response_type": "status_envelope",
        "candidate_id": job_spec.get("candidate_id"),
        "submission_id": operation.get("submission_id"),
        "job_id": job_id,
        "status": status,
        "authoritative": True,
        "backend": job_spec.get("backend"),
        "engine": job_spec.get("engine"),
        "skill": job_spec.get("orca_skill"),
        "execution_mode": job_spec.get("execution_mode", "remote"),
        "remote_target": remote_settings.get("target"),
        "scheduler": scheduler or {},
        "paths": {
            "run_log": "run.log",
            "result": "result.json",
            "failure": "failure.json",
        },
        "message": message,
        "checked_at": now_iso(),
    }
    return payload


def result_payload(job_spec: dict[str, Any], *, job_id: str, outputs: dict[str, Any]) -> dict[str, Any]:
    operation = dict(job_spec.get("operation") or {})
    return {
        "contract_version": CONTRACT_VERSION,
        "request_type": "extract_simulation_result",
        "response_type": "result_envelope",
        "candidate_id": job_spec.get("candidate_id"),
        "submission_id": operation.get("submission_id"),
        "job_id": job_id,
        "status": "completed",
        "backend": job_spec.get("backend"),
        "engine": job_spec.get("engine"),
        "simulation_type": job_spec.get("simulation_type"),
        "outputs": outputs,
        "operation": operation,
        "provenance": dict(job_spec.get("provenance") or {}),
    }


def failure_payload(job_spec: dict[str, Any], *, job_id: str, failure_kind: str, failure_message: str) -> dict[str, Any]:
    operation = dict(job_spec.get("operation") or {})
    return {
        "contract_version": CONTRACT_VERSION,
        "request_type": "extract_simulation_result",
        "response_type": "failure_envelope",
        "candidate_id": job_spec.get("candidate_id"),
        "submission_id": operation.get("submission_id"),
        "job_id": job_id,
        "status": "failed",
        "backend": job_spec.get("backend"),
        "engine": job_spec.get("engine"),
        "simulation_type": job_spec.get("simulation_type"),
        "failure_kind": failure_kind,
        "failure_message": failure_message,
        "operation": operation,
        "provenance": dict(job_spec.get("provenance") or {}),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: remote_submit_orca_job.py <job_dir>", file=sys.stderr)
        return 2

    inbox_job_dir = Path(argv[1]).resolve()
    if not inbox_job_dir.exists():
        print(f"Job directory not found: {inbox_job_dir}", file=sys.stderr)
        return 2

    job_spec_path = inbox_job_dir / "orca_job.json"
    structure_path = inbox_job_dir / "input_structure.xyz"
    if not job_spec_path.exists() or not structure_path.exists():
        print("Missing required job bundle files", file=sys.stderr)
        return 2

    job_spec = read_json(job_spec_path)
    job_id = inbox_job_dir.name
    remote_root = inbox_job_dir.parent.parent
    running_dir = remote_root / "running" / job_id
    completed_dir = remote_root / "completed" / job_id
    failed_dir = remote_root / "failed" / job_id

    running_dir.parent.mkdir(parents=True, exist_ok=True)
    completed_dir.parent.mkdir(parents=True, exist_ok=True)
    failed_dir.parent.mkdir(parents=True, exist_ok=True)

    if inbox_job_dir != running_dir:
        if running_dir.exists():
            shutil.rmtree(running_dir)
        shutil.move(str(inbox_job_dir), str(running_dir))

    run_log = running_dir / "run.log"
    run_log.write_text("Starting remote AtomisticSkills ORCA job\n", encoding="utf-8")

    write_json(running_dir / "status.json", status_payload(job_spec, status="running", job_id=job_id))

    try:
        # Replace this placeholder command with your real scheduler or AtomisticSkills invocation.
        # Example direction only:
        # subprocess.run(["python", "-m", "atomisticskills.cli", ...], cwd=running_dir, check=True)
        subprocess.run(["/bin/sh", "-lc", "echo TODO: invoke AtomisticSkills ORCA workflow >> run.log"], cwd=running_dir, check=True)

        outputs = {
            "status": "completed",
            "note": "Template wrapper executed placeholder command only. Replace with real AtomisticSkills execution.",
        }
        write_json(running_dir / "result.json", result_payload(job_spec, job_id=job_id, outputs=outputs))
        write_json(running_dir / "status.json", status_payload(job_spec, status="completed", job_id=job_id))

        if completed_dir.exists():
            shutil.rmtree(completed_dir)
        shutil.move(str(running_dir), str(completed_dir))
        return 0
    except subprocess.CalledProcessError as exc:
        failure = failure_payload(
            job_spec,
            job_id=job_id,
            failure_kind="remote_wrapper_failure",
            failure_message=f"Remote wrapper command failed with exit code {exc.returncode}",
        )
        write_json(running_dir / "failure.json", failure)
        write_json(running_dir / "status.json", status_payload(job_spec, status="failed", job_id=job_id, message=failure["failure_message"]))
        if failed_dir.exists():
            shutil.rmtree(failed_dir)
        shutil.move(str(running_dir), str(failed_dir))
        return exc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
