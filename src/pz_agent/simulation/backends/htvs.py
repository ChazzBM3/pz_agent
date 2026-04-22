from __future__ import annotations

import json
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pz_agent.io import read_json, write_json


CONTRACT_VERSION = "htvs.request_response.v1"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _run(command: str) -> dict:
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "ok": result.returncode == 0,
    }


def _candidate_job_root(job_roots: list[str], submission_id: str) -> Path:
    if job_roots:
        return Path(job_roots[0]).expanduser() / submission_id / "jobs"
    return Path(submission_id) / "jobs"


def _job_directories(job_root: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for bucket in ("inbox", "pending", "completed"):
        bucket_path = job_root / bucket
        if bucket_path.exists():
            result[bucket] = sorted(path.name for path in bucket_path.iterdir() if path.is_dir())
        else:
            result[bucket] = []
    return result


def _jobdir_status(job_root: Path) -> tuple[str, str | None, Path | None]:
    buckets = _job_directories(job_root)
    if buckets["completed"]:
        jobdir = job_root / "completed" / buckets["completed"][0]
        return "completed", buckets["completed"][0], jobdir
    if buckets["pending"]:
        jobdir = job_root / "pending" / buckets["pending"][0]
        return "pending", buckets["pending"][0], jobdir
    if buckets["inbox"]:
        jobdir = job_root / "inbox" / buckets["inbox"][0]
        return "inbox", buckets["inbox"][0], jobdir
    return "submitted", None, None


def _jobdir_artifacts(jobdir: Path | None) -> dict:
    if not jobdir:
        return {}
    artifacts = {
        "jobdir": str(jobdir),
        "files": sorted(path.name for path in jobdir.iterdir()),
    }
    job_id_path = jobdir / "job_manager-job_id"
    if job_id_path.exists():
        artifacts["scheduler_job_id"] = job_id_path.read_text(encoding="utf-8").strip()
    slurm_logs = sorted(path.name for path in jobdir.glob("slurm-*.out"))
    if slurm_logs:
        artifacts["slurm_logs"] = slurm_logs
    return artifacts


def _coerce_float(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _read_text_if_exists(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _load_json_if_exists(path: Path):
    if not path.exists() or not path.is_file():
        return None
    try:
        return read_json(path)
    except Exception:
        return None


def _find_first_existing(jobdir: Path, names: list[str]) -> Path | None:
    for name in names:
        path = jobdir / name
        if path.exists():
            return path
    return None


def _parse_orca_output_metrics(jobdir: Path) -> dict:
    metrics: dict[str, object] = {}
    out_path = _find_first_existing(jobdir, ["job.out", "orca.out", "output.out"])
    if not out_path:
        return metrics
    text = _read_text_if_exists(out_path)
    if not text:
        return metrics

    energy_patterns = [
        r"FINAL SINGLE POINT ENERGY\s+(-?\d+(?:\.\d+)?)",
        r"Total Energy\s*[:=]\s*(-?\d+(?:\.\d+)?)",
    ]
    for pattern in energy_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = _coerce_float(match.group(1))
            if value is not None:
                metrics["final_energy"] = value
                break

    dipole_match = re.search(r"Magnitude \(a\.u\.\)\s*[:=]?\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if dipole_match:
        value = _coerce_float(dipole_match.group(1))
        if value is not None:
            metrics["groundState.dipole_moment"] = value

    homo_lumo_match = re.search(r"HOMO-LUMO GAP\s*[:=]?\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if homo_lumo_match:
        value = _coerce_float(homo_lumo_match.group(1))
        if value is not None:
            metrics["groundState.homo_lumo_gap"] = value

    if "ORCA TERMINATED NORMALLY" in text:
        metrics.setdefault("status", "completed")
    return metrics


def _extract_outputs_from_jobdir(jobdir: Path) -> dict:
    outputs: dict[str, object] = {}

    direct_result = _load_json_if_exists(jobdir / "result.json")
    if isinstance(direct_result, dict):
        direct_outputs = direct_result.get("outputs")
        if isinstance(direct_outputs, dict):
            outputs.update(direct_outputs)

    pz_result = _load_json_if_exists(jobdir / "pz_agent_result.json")
    if isinstance(pz_result, dict):
        pz_outputs = pz_result.get("outputs")
        if isinstance(pz_outputs, dict):
            outputs.update(pz_outputs)

    summary_json = _find_first_existing(jobdir, ["summary.json", "parsed_results.json", "job_summary.json"])
    summary_payload = _load_json_if_exists(summary_json) if summary_json else None
    if isinstance(summary_payload, dict):
        for key in (
            "final_energy",
            "optimized_structure",
            "groundState.solvation_energy",
            "groundState.homo",
            "groundState.lumo",
            "groundState.homo_lumo_gap",
            "groundState.dipole_moment",
            "status",
        ):
            if key in summary_payload and key not in outputs:
                outputs[key] = summary_payload.get(key)
        nested_outputs = summary_payload.get("outputs")
        if isinstance(nested_outputs, dict):
            for key, value in nested_outputs.items():
                outputs.setdefault(key, value)

    metrics = _parse_orca_output_metrics(jobdir)
    for key, value in metrics.items():
        outputs.setdefault(key, value)

    optimized_structure = _find_first_existing(
        jobdir,
        [
            "optimized_structure.xyz",
            "final.xyz",
            "opt.xyz",
            "job.xyz",
            "xtbopt.xyz",
        ],
    )
    if optimized_structure:
        outputs.setdefault("optimized_structure", optimized_structure.read_text(encoding="utf-8"))

    outputs.setdefault("status", "completed")
    return outputs


def _remote_snapshot(*, ssh_host: str, remote_job_root: str) -> dict | None:
    if not ssh_host or not remote_job_root:
        return None
    remote_job_root = remote_job_root.rstrip("/")
    script = f"""
set -euo pipefail
JOB_ROOT={shlex.quote(remote_job_root)}
python3 - <<'PY'
import json
import os
from pathlib import Path
job_root = Path(os.environ['JOB_ROOT'])
result = {{
    'job_root': str(job_root),
    'exists': job_root.exists(),
    'buckets': {{'inbox': [], 'pending': [], 'completed': []}},
}}
if job_root.exists():
    for bucket in ('inbox', 'pending', 'completed'):
        bucket_path = job_root / bucket
        if bucket_path.exists():
            result['buckets'][bucket] = sorted(path.name for path in bucket_path.iterdir() if path.is_dir())
    status = 'submitted'
    jobdir_name = None
    for bucket, label in (('completed', 'completed'), ('pending', 'pending'), ('inbox', 'inbox')):
        names = result['buckets'][bucket]
        if names:
            status = label
            jobdir_name = names[0]
            break
    result['status'] = status
    result['jobdir_name'] = jobdir_name
    if jobdir_name:
        bucket = 'completed' if status == 'completed' else ('pending' if status == 'pending' else 'inbox')
        jobdir = job_root / bucket / jobdir_name
        result['jobdir'] = str(jobdir)
        result['files'] = sorted(path.name for path in jobdir.iterdir())
        job_id_path = jobdir / 'job_manager-job_id'
        if job_id_path.exists():
            result['scheduler_job_id'] = job_id_path.read_text(encoding='utf-8').strip()
        result['slurm_logs'] = sorted(path.name for path in jobdir.glob('slurm-*.out'))
print(json.dumps(result))
PY
"""
    command = "ssh -T " + shlex.quote(ssh_host) + " 'bash -s' <<'EOF'\n" + script + "\nEOF"
    result = _run(command)
    if not result.get("ok") or not result.get("stdout"):
        return {
            "ok": False,
            "command": command,
            "error": result.get("stderr") or result.get("stdout") or "remote snapshot failed",
        }
    try:
        payload = json.loads(result.get("stdout") or "{}")
    except Exception as exc:
        return {
            "ok": False,
            "command": command,
            "error": f"invalid remote snapshot json: {exc}",
        }
    return {
        "ok": True,
        "command": command,
        "payload": payload,
    }


def _submission_id(candidate_id: str, queue_rank: int | None, submit_config: dict) -> str:
    prefix = str(submit_config.get("submission_prefix", "htvs")).strip() or "htvs"
    rank = int(queue_rank or 0)
    return f"{prefix}-{candidate_id}-{rank:03d}"


def _remote_job_name(jobdir_name: str | None, submission_id: str) -> str:
    return jobdir_name or submission_id


class HtvsBackend:
    name = "htvs"

    def submit(
        self,
        *,
        candidate_id: str,
        queue_rank: int | None,
        job_spec_path: str,
        simulation: dict,
        submit_config: dict,
    ) -> dict:
        remote_target = submit_config.get("remote_target") or (simulation.get("parameters", {}) or {}).get("remote_target")
        ssh_host = str(submit_config.get("ssh_host") or "").strip()
        htvs_root = str(submit_config.get("htvs_root") or "").strip()
        python_bin = str(submit_config.get("python_bin") or "python").strip()
        settings_module = str(submit_config.get("settings_module") or "djangochem.settings.orgel").strip()
        project = str(submit_config.get("project") or submit_config.get("project_prefix") or "pz_agent_htvs").strip()
        source_jobconfig = str(submit_config.get("source_jobconfig") or "seed_xyz_import").strip()
        source_method = str(submit_config.get("source_method") or "seed_xyz_import").strip()
        source_mode = str(submit_config.get("source_mode") or "geoms").strip()
        job_package = dict(submit_config.get("job_package") or {})
        geometry_path = str(
            submit_config.get("geometry_path")
            or job_package.get("structure_path")
            or job_spec_path
            or ""
        ).strip()
        job_roots = list(submit_config.get("job_roots") or [])
        local_job_root_base = str(submit_config.get("local_job_root_base") or "").strip()
        remote_job_root_base = str(submit_config.get("remote_job_root_base") or "").strip()
        request_limit = submit_config.get("request_limit")
        build_limit = submit_config.get("build_limit")
        queue_rank = int(queue_rank or 0)
        submission_id = _submission_id(candidate_id, queue_rank, submit_config)
        if job_roots:
            job_root = Path(job_roots[0]).expanduser()
        elif local_job_root_base:
            job_root = Path(local_job_root_base).expanduser() / submission_id / "jobs"
        else:
            job_root = Path(submission_id) / "jobs"
        remote_job_root = f"{remote_job_root_base.rstrip('/')}/{submission_id}/jobs" if remote_job_root_base else str(job_root)
        details = dict(submit_config.get("details") or {})
        compute_platform = str(details.get("compute_platform") or submit_config.get("compute_platform") or "supercloud")

        if not ssh_host or not htvs_root:
            raise ValueError("HTVS backend requires submit_config.ssh_host and submit_config.htvs_root")
        if not geometry_path:
            raise ValueError("HTVS backend requires a geometry_path or job_spec_path")

        remote_script = [
            "set -euo pipefail",
            f"HTVS_ROOT={shlex.quote(htvs_root)}",
            f"PYTHON={shlex.quote(python_bin)}",
            f"PROJECT={shlex.quote(project)}",
            f"JOB_ROOT={shlex.quote(remote_job_root)}",
            f"GEOM_PATH={shlex.quote(geometry_path)}",
            "cd \"$HTVS_ROOT/djangochem\"",
            "export PYTHONPATH=\"$HTVS_ROOT:$HTVS_ROOT/djangochem\"",
            "$PYTHON - <<'PY'",
            "import os",
            f"os.environ.setdefault('DJANGO_SETTINGS_MODULE', {json.dumps(settings_module)})",
            "import django",
            "django.setup()",
            "from django.contrib.auth.models import Group",
            "Group.objects.get_or_create(name=os.environ['PROJECT'])",
            "print('GROUP_OK')",
            "PY",
            "mkdir -p \"$JOB_ROOT/inbox\" \"$JOB_ROOT/pending\" \"$JOB_ROOT/completed\"",
        ]

        addxyz_cmd = [
            "$PYTHON",
            "manage.py",
            "addxyz",
            "$PROJECT",
            "$GEOM_PATH",
            source_mode,
            "--jobconfig",
            source_jobconfig,
            "--method",
            source_method,
            "--charge",
            str(submit_config.get("charge", 0)),
            "--ionization",
            str(submit_config.get("ionization", 0)),
            "--force",
            f"--settings={settings_module}",
        ]
        request_cmd = [
            "$PYTHON",
            "manage.py",
            "requestjobs",
            "$PROJECT",
            str(submit_config.get("job_config") or "dft_opt_orca"),
            "--parent_config",
            source_jobconfig,
            "--details",
            json.dumps(details),
            f"--settings={settings_module}",
            "--unconverged_geoms",
            "--force",
        ]
        if request_limit is not None:
            request_cmd.extend(["--limit", str(request_limit)])
        build_cmd = [
            "$PYTHON",
            "manage.py",
            "buildjobs",
            "$PROJECT",
            "$JOB_ROOT/inbox",
            "-c",
            str(submit_config.get("job_config") or "dft_opt_orca"),
            "-p",
            compute_platform,
            f"--settings={settings_module}",
        ]
        if build_limit is not None:
            build_cmd.extend(["-l", str(build_limit)])

        remote_script.extend([
            _shell_join(addxyz_cmd),
            _shell_join(request_cmd),
            _shell_join(build_cmd),
            "find \"$JOB_ROOT\" -maxdepth 2 -type d | sort",
        ])
        remote_script_text = "\n".join(remote_script)
        ssh_command = "ssh -T " + shlex.quote(ssh_host) + " 'bash -s' <<'EOF'\n" + remote_script_text + "\nEOF"
        handoff = _run(ssh_command)

        status, jobdir_name, jobdir_path = _jobdir_status(job_root)
        artifacts = _jobdir_artifacts(jobdir_path)
        return {
            "contract_version": CONTRACT_VERSION,
            "request_type": "submit_simulation",
            "response_type": "submission_ack" if handoff.get("ok") else "submission_failure",
            "candidate_id": candidate_id,
            "queue_rank": queue_rank,
            "status": status if handoff.get("ok") else "failed",
            "backend": simulation.get("backend") or self.name,
            "engine": simulation.get("engine"),
            "job_driver": simulation.get("job_driver"),
            "execution_mode": simulation.get("execution_mode"),
            "remote_target": remote_target,
            "submission_id": submission_id,
            "job_id": _remote_job_name(jobdir_name, submission_id),
            "job_spec_path": job_spec_path,
            "geometry_path": geometry_path,
            "remote_settings": {
                "target": remote_target,
                "ssh_host": ssh_host,
                "htvs_root": htvs_root,
                "settings_module": settings_module,
                "project": project,
                "job_root": str(job_root),
                "remote_job_root": remote_job_root,
                "compute_platform": compute_platform,
            },
            "handoff_execution": {
                "executed": True,
                "command": ssh_command,
                "result": handoff,
            },
            "jobdir_snapshot": {
                "status": status,
                "jobdir_name": jobdir_name,
                **artifacts,
            },
            "submitted_at": _utcnow(),
        }

    def check(
        self,
        *,
        candidate_id: str,
        submission: dict,
        simulation: dict,
        check_config: dict,
    ) -> dict:
        remote_settings = dict(submission.get("remote_settings") or {})
        job_root = Path(str(remote_settings.get("job_root") or "")).expanduser() if remote_settings.get("job_root") else None
        remote_job_root = str(remote_settings.get("remote_job_root") or "").strip()
        ssh_host = str(check_config.get("ssh_host") or remote_settings.get("ssh_host") or "").strip()
        remote_target = submission.get("remote_target") or (simulation.get("parameters", {}) or {}).get("remote_target")

        status = str(submission.get("status") or "submitted")
        artifacts: dict = {}
        authoritative = False
        status_source = "submission_record"
        remote_snapshot = None
        if job_root and job_root.exists():
            status, jobdir_name, jobdir_path = _jobdir_status(job_root)
            artifacts = {
                "job_root": str(job_root),
                "jobdir_name": jobdir_name,
                **_jobdir_artifacts(jobdir_path),
            }
            authoritative = True
            status_source = "local_job_root_snapshot"
        elif ssh_host and remote_job_root:
            remote_snapshot = _remote_snapshot(ssh_host=ssh_host, remote_job_root=remote_job_root)
            if remote_snapshot and remote_snapshot.get("ok"):
                payload = dict(remote_snapshot.get("payload") or {})
                status = str(payload.get("status") or status)
                artifacts = payload
                authoritative = bool(payload.get("exists"))
                status_source = "remote_job_root_snapshot"

        response_type = "status_envelope"
        if status in {"failed", "error"}:
            response_type = "failure_envelope"

        envelope = {
            "contract_version": CONTRACT_VERSION,
            "request_type": "check_simulation",
            "response_type": response_type,
            "candidate_id": candidate_id,
            "submission_id": submission.get("submission_id"),
            "job_id": submission.get("job_id"),
            "status": status,
            "backend": submission.get("backend") or simulation.get("backend") or self.name,
            "engine": submission.get("engine") or simulation.get("engine"),
            "job_driver": submission.get("job_driver") or simulation.get("job_driver"),
            "execution_mode": submission.get("execution_mode") or simulation.get("execution_mode"),
            "remote_target": remote_target,
            "check_only": True,
            "authoritative": authoritative,
            "remote_settings": remote_settings,
            "checked_at": _utcnow(),
            "status_source": status_source,
            "jobdir_snapshot": artifacts,
            "status_fetch_error": None if (not remote_snapshot or remote_snapshot.get("ok")) else remote_snapshot.get("error"),
        }
        writeback_path = check_config.get("writeback_status_path")
        if writeback_path:
            write_json(Path(writeback_path), envelope)
        return envelope

    def extract(
        self,
        *,
        candidate_id: str,
        submission: dict,
        simulation: dict,
        extract_config: dict,
    ) -> dict | None:
        remote_settings = dict(submission.get("remote_settings") or {})
        job_root = Path(str(remote_settings.get("job_root") or "")).expanduser() if remote_settings.get("job_root") else None
        if not job_root or not job_root.exists():
            return None
        status, jobdir_name, jobdir_path = _jobdir_status(job_root)
        if status != "completed" or not jobdir_path:
            return None

        jobdir_snapshot = {
            "job_root": str(job_root),
            "jobdir_name": jobdir_name,
            **_jobdir_artifacts(jobdir_path),
        }
        outputs = {
            **_extract_outputs_from_jobdir(jobdir_path),
            "job_root": str(job_root),
            "jobdir_name": jobdir_name,
            "jobdir": str(jobdir_path),
        }
        result = {
            "contract_version": CONTRACT_VERSION,
            "request_type": "extract_simulation_result",
            "response_type": "result_envelope",
            "candidate_id": candidate_id,
            "submission_id": submission.get("submission_id"),
            "job_id": submission.get("job_id"),
            "status": status,
            "backend": submission.get("backend") or simulation.get("backend") or self.name,
            "engine": submission.get("engine") or simulation.get("engine"),
            "simulation_type": simulation.get("simulation_type"),
            "remote_target": submission.get("remote_target") or (simulation.get("parameters", {}) or {}).get("remote_target"),
            "outputs": outputs,
            "raw_result": {
                "remote_settings": remote_settings,
                "jobdir_snapshot": jobdir_snapshot,
            },
        }
        result_path = jobdir_path / "pz_agent_result.json"
        write_json(result_path, result)
        return result
