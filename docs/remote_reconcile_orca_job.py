#!/usr/bin/env python3
from __future__ import annotations

"""Remote reconciliation helper for ORCA-over-Slurm job directories.

Expected usage:
    python remote_reconcile_orca_job.py /path/to/remote_root/running/<job_id>

Purpose:
- refresh status.json from scheduler state when the payload script has not yet
  produced a terminal artifact or when status drift needs repair
- keep the file-backed protocol authoritative and scheduler-aware
- serve as a good target for cluster-side cron
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "orca_slurm.request_response.v1"
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "PREEMPTED", "BOOT_FAIL", "DEADLINE"}


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
    return {
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
        "job_driver": job_spec.get("job_driver"),
        "execution_mode": job_spec.get("execution_mode", "remote"),
        "remote_target": remote_settings.get("target"),
        "scheduler": scheduler or {},
        "paths": {
            "run_log": "run.log",
            "result": "result.json",
            "failure": "failure.json",
            "orca_input": "job.inp",
            "orca_output": "job.out",
        },
        "message": message,
        "checked_at": now_iso(),
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


def slurm_state(scheduler_job_id: str) -> dict[str, Any]:
    sacct = subprocess.run(
        ["sacct", "-j", scheduler_job_id, "--format=JobIDRaw,State,ExitCode", "--parsable2", "--noheader"],
        text=True,
        capture_output=True,
    )
    if sacct.returncode == 0 and sacct.stdout.strip():
        first = sacct.stdout.strip().splitlines()[0].split("|")
        if len(first) >= 3:
            return {
                "source": "sacct",
                "scheduler_job_id": scheduler_job_id,
                "scheduler_state": first[1].strip(),
                "exit_code": first[2].strip(),
                "query_ok": True,
            }

    squeue = subprocess.run(
        ["squeue", "-h", "-j", scheduler_job_id, "-o", "%i|%T"],
        text=True,
        capture_output=True,
    )
    if squeue.returncode == 0 and squeue.stdout.strip():
        first = squeue.stdout.strip().splitlines()[0].split("|")
        if len(first) >= 2:
            return {
                "source": "squeue",
                "scheduler_job_id": scheduler_job_id,
                "scheduler_state": first[1].strip().upper(),
                "exit_code": None,
                "query_ok": True,
            }

    return {
        "source": "none",
        "scheduler_job_id": scheduler_job_id,
        "scheduler_state": "UNKNOWN",
        "exit_code": None,
        "query_ok": False,
        "sacct_stderr": sacct.stderr.strip(),
        "squeue_stderr": squeue.stderr.strip(),
    }


def protocol_status_from_scheduler_state(scheduler_state: str, running_dir: Path) -> tuple[str, str | None]:
    state = (scheduler_state or "UNKNOWN").upper()
    if (running_dir / "result.json").exists():
        return "completed", None
    if (running_dir / "failure.json").exists():
        return "failed", None
    if state in {"PENDING", "CONFIGURING"}:
        return "submitted", None
    if state in {"RUNNING", "COMPLETING"}:
        return "running", None
    if state == "COMPLETED":
        return "completed", "scheduler completed but result.json not found yet"
    if state in TERMINAL_STATES:
        return "failed", f"scheduler reached terminal state {state}"
    return "running", f"unmapped scheduler state {state}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: remote_reconcile_orca_job.py <running_job_dir>", file=sys.stderr)
        return 2

    running_dir = Path(argv[1]).resolve()
    if not running_dir.exists():
        print(f"Job directory not found: {running_dir}", file=sys.stderr)
        return 2

    job_spec = read_json(running_dir / "orca_job.json")
    scheduler = read_json(running_dir / "scheduler.json") if (running_dir / "scheduler.json").exists() else {}
    job_id = running_dir.name
    scheduler_job_id = str(scheduler.get("scheduler_job_id") or "").strip()
    if not scheduler_job_id:
        write_json(
            running_dir / "status.json",
            status_payload(job_spec, status="submitted", job_id=job_id, scheduler=scheduler, message="reconcile skipped: missing scheduler_job_id"),
        )
        return 0

    slurm = slurm_state(scheduler_job_id)
    merged_scheduler = {**scheduler, **slurm, "reconciled_at": now_iso()}
    protocol_status, message = protocol_status_from_scheduler_state(slurm.get("scheduler_state", "UNKNOWN"), running_dir)

    if protocol_status == "failed" and not (running_dir / "failure.json").exists() and slurm.get("scheduler_state") in TERMINAL_STATES:
        write_json(
            running_dir / "failure.json",
            failure_payload(
                job_spec,
                job_id=job_id,
                failure_kind="scheduler_terminal_failure",
                failure_message=message or f"scheduler reached terminal state {slurm.get('scheduler_state')}",
            ),
        )

    write_json(running_dir / "scheduler.json", merged_scheduler)
    write_json(running_dir / "status.json", status_payload(job_spec, status=protocol_status, job_id=job_id, scheduler=merged_scheduler, message=message))

    remote_root = running_dir.parent.parent
    if protocol_status == "completed" and (running_dir / "result.json").exists():
        target = remote_root / "completed" / job_id
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(running_dir), str(target))
    elif protocol_status == "failed" and (running_dir / "failure.json").exists():
        target = remote_root / "failed" / job_id
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(running_dir), str(target))

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
