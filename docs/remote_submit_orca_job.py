#!/usr/bin/env python3
from __future__ import annotations

"""Thin remote wrapper template for direct ORCA submission over Slurm.

This script is intentionally conservative. It is a template for the supercomputer
side, not a drop-in final production runner.

Expected usage:
    python remote_submit_orca_job.py /path/to/remote_root/inbox/<job_id>

This template is intentionally split-brain:
- this submit wrapper handles remote validation, directory movement, and scheduler submission
- the scheduled payload script should perform the actual ORCA run and final artifact writing

Recommended behavior:
- validate `orca_job.json` and `input_structure.xyz`
- move job directory into `running/`
- update `status.json`
- submit a scheduler job, ideally via Slurm `sbatch`
- record scheduler metadata in `scheduler.json` and `status.json`
- later execution writes `result.json` or `failure.json`
- move the directory into `completed/` or `failed/`
"""

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "orca_slurm.request_response.v1"


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


def render_orca_input(job_spec: dict[str, Any], structure_text: str) -> str:
    parameters = dict(job_spec.get("parameters") or {})
    functional = parameters.get("functional", "PBE")
    basis_set = parameters.get("basis_set", "def2-SVP")
    dispersion = parameters.get("dispersion", "D3")
    solvation = parameters.get("solvation", "CPCM")
    solvent = parameters.get("solvent", "water")
    opt_type = parameters.get("opt_type", "min")
    charge = int(parameters.get("charge", 0) or 0)
    multiplicity = int(parameters.get("spin_multiplicity", 1) or 1)
    special_option = str(parameters.get("special_option", "") or "").strip()
    maxiter = int(parameters.get("convergence_max_iterations", 200) or 200)

    keywords = [functional, basis_set, dispersion]
    if str(job_spec.get("simulation_type", "")).strip().lower() == "geometry_optimization":
        keywords.append("Opt")
    if opt_type and str(opt_type).lower() != "min":
        keywords.append(str(opt_type))
    if special_option:
        keywords.append(special_option)

    header = f"! {' '.join(str(k) for k in keywords if k)}"
    blocks = [
        header,
        f"%scf MaxIter {maxiter} end",
        f"%pal nprocs {int(parameters.get('nprocs', 1) or 1)} end",
        f"%cpcm smd false epsilon 80.4 end" if solvation.upper() == "CPCM" and solvent.lower() == "water" else f"%cpcm end",
        f"* xyz {charge} {multiplicity}",
    ]
    xyz_lines = structure_text.splitlines()[2:] if len(structure_text.splitlines()) >= 3 else []
    blocks.extend(xyz_lines)
    blocks.append("*")
    return "\n".join(blocks) + "\n"


def write_scheduler_script(running_dir: Path, job_spec: dict[str, Any]) -> Path:
    parameters = dict(job_spec.get("parameters") or {})
    scheduler = dict(job_spec.get("scheduler") or {})
    nprocs = int(parameters.get("nprocs", 1) or 1)
    partition = scheduler.get("partition", "xeon-p8")
    walltime = scheduler.get("time", "00:10:00")
    mem_per_cpu = scheduler.get("mem_per_cpu", "2000")
    job_name = scheduler.get("job_name") or f"orca_{job_spec.get('candidate_id', 'job')}"
    mpi_module = scheduler.get("mpi_module", "mpi/openmpi-4.1.8")
    orca_dir = scheduler.get("orca_dir", "/home/gridsan/groups/rgb_shared/software/orca/orca_6_0_0_linux_x86-64_shared_openmpi416")
    script_path = running_dir / "run_orca_job.sh"
    script_path.write_text(
        "#!/bin/bash\n"
        f"#SBATCH -J {job_name}\n"
        "#SBATCH -N 1\n"
        f"#SBATCH -n {nprocs}\n"
        f"#SBATCH -t {walltime}\n"
        f"#SBATCH -p {partition}\n"
        f"#SBATCH --mem-per-cpu={mem_per_cpu}\n"
        "#SBATCH --no-requeue\n\n"
        "set -euo pipefail\n\n"
        "source /etc/profile\n"
        "source ~/.bashrc\n\n"
        f"MPI_MODULE=\"{mpi_module}\"\n"
        f"ORCA_DIR=\"{orca_dir}\"\n"
        "ORCA_BIN=\"${ORCA_DIR}/orca\"\n\n"
        "module load \"${MPI_MODULE}\"\n\n"
        "userid=$(id -u \"${USER}\")\n"
        "if [ -d \"/localscratch/${USER}\" ]; then\n"
        "SCRATCH_ROOT=\"/localscratch/${USER}/orcatmp\"\n"
        "else\n"
        "size=$(df -l /tmp | awk 'NR==2 { print $4 }')\n"
        "if [ \"${size}\" -gt 25000000 ]; then\n"
        "SCRATCH_ROOT=\"/tmp/user/${userid}/${USER}/orcatmp\"\n"
        "else\n"
        "SCRATCH_ROOT=\"/state/partition1/user/${USER}/orcatmp\"\n"
        "fi\n"
        "fi\n\n"
        "mkdir -p \"${SCRATCH_ROOT}\"\n"
        "SCRATCH_DIR=\"${SCRATCH_ROOT}/orca_${SLURM_JOB_ID}\"\n"
        "mkdir -p \"${SCRATCH_DIR}\"\n\n"
        "echo \"Scratch root: ${SCRATCH_ROOT}\" | tee -a run.log\n"
        "echo \"Scratch dir: ${SCRATCH_DIR}\" | tee -a run.log\n"
        "echo \"ORCA binary: ${ORCA_BIN}\" | tee -a run.log\n\n"
        "cp -f job.inp \"${SCRATCH_DIR}/job.inp\"\n"
        "cp -f input_structure.xyz \"${SCRATCH_DIR}/input_structure.xyz\"\n\n"
        "cd \"${SCRATCH_DIR}\"\n"
        "export PATH=\"${ORCA_DIR}:${PATH}\"\n"
        "export LD_LIBRARY_PATH=\"${ORCA_DIR}:${LD_LIBRARY_PATH:-}\"\n"
        "export OMP_NUM_THREADS=1\n\n"
        "\"${ORCA_BIN}\" job.inp > \"${SLURM_SUBMIT_DIR}/job.out\" 2>&1\n\n"
        "cp -f job.inp \"${SLURM_SUBMIT_DIR}/\"\n"
        "cp -f ./* \"${SLURM_SUBMIT_DIR}/\" 2>/dev/null || true\n"
        "rm -rf \"${SCRATCH_DIR}\"\n\n"
        "python - <<'PY'\n"
        "import json\n"
        "from pathlib import Path\n"
        "job_spec = json.loads(Path('orca_job.json').read_text())\n"
        "job_out = Path('job.out').read_text(errors='ignore') if Path('job.out').exists() else ''\n"
        "completed = 'ORCA TERMINATED NORMALLY' in job_out\n"
        "result = {\n"
        "  'contract_version': 'orca_slurm.request_response.v1',\n"
        "  'request_type': 'extract_simulation_result',\n"
        "  'response_type': 'result_envelope' if completed else 'failure_envelope',\n"
        "  'candidate_id': job_spec.get('candidate_id'),\n"
        "  'submission_id': (job_spec.get('operation') or {}).get('submission_id'),\n"
        "  'job_id': Path.cwd().name,\n"
        "  'status': 'completed' if completed else 'failed',\n"
        "  'backend': job_spec.get('backend'),\n"
        "  'engine': job_spec.get('engine'),\n"
        "  'simulation_type': job_spec.get('simulation_type'),\n"
        "  'outputs': {\n"
        "    'status': 'completed' if completed else 'failed',\n"
        "    'orca_output_path': 'job.out'\n"
        "  },\n"
        "  'operation': job_spec.get('operation'),\n"
        "  'provenance': job_spec.get('provenance'),\n"
        "}\n"
        "target = 'result.json' if completed else 'failure.json'\n"
        "Path(target).write_text(json.dumps(result, indent=2))\n"
        "PY\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path


def parse_sbatch_job_id(stdout: str) -> str | None:
    match = re.search(r"Submitted batch job\s+(\d+)", stdout)
    return match.group(1) if match else None


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
    run_log.write_text("Starting remote ORCA job submission wrapper\n", encoding="utf-8")

    structure_text = structure_path.read_text(encoding="utf-8")
    (running_dir / "job.inp").write_text(render_orca_input(job_spec, structure_text), encoding="utf-8")

    scheduler_script = write_scheduler_script(running_dir, job_spec)
    scheduler_config = {
        "system": "slurm",
        "submit_command": ["sbatch", str(scheduler_script.name)],
        "script_path": str(scheduler_script),
        "partition": "xeon-p8",
        "time": "00:10:00",
        "mem_per_cpu": "2000",
        "mpi_module": "mpi/openmpi-4.1.8",
        "orca_dir": "/home/gridsan/groups/rgb_shared/software/orca/orca_6_0_0_linux_x86-64_shared_openmpi416",
    }
    write_json(running_dir / "scheduler.json", scheduler_config)
    write_json(running_dir / "status.json", status_payload(job_spec, status="staged", job_id=job_id, scheduler=scheduler_config))

    try:
        submit = subprocess.run(
            ["sbatch", scheduler_script.name],
            cwd=running_dir,
            check=True,
            text=True,
            capture_output=True,
        )
        scheduler_job_id = parse_sbatch_job_id(submit.stdout)
        scheduler_details = {
            **scheduler_config,
            "scheduler_job_id": scheduler_job_id,
            "submit_stdout": submit.stdout.strip(),
            "submit_stderr": submit.stderr.strip(),
        }
        write_json(running_dir / "scheduler.json", scheduler_details)
        write_json(running_dir / "status.json", status_payload(job_spec, status="submitted", job_id=job_id, scheduler=scheduler_details))
        return 0
    except subprocess.CalledProcessError as exc:
        failure = failure_payload(
            job_spec,
            job_id=job_id,
            failure_kind="scheduler_submission_failure",
            failure_message=f"sbatch failed with exit code {exc.returncode}",
        )
        write_json(running_dir / "failure.json", failure)
        scheduler_details = {
            **scheduler_config,
            "submit_stdout": (exc.stdout or "").strip() if hasattr(exc, "stdout") else "",
            "submit_stderr": (exc.stderr or "").strip() if hasattr(exc, "stderr") else "",
        }
        write_json(running_dir / "scheduler.json", scheduler_details)
        write_json(running_dir / "status.json", status_payload(job_spec, status="failed", job_id=job_id, scheduler=scheduler_details, message=failure["failure_message"]))
        if failed_dir.exists():
            shutil.rmtree(failed_dir)
        shutil.move(str(running_dir), str(failed_dir))
        return exc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
