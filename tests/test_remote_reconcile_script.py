from __future__ import annotations

import json
import subprocess
from pathlib import Path

from runpy import run_path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "docs" / "remote_reconcile_orca_job.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_remote_reconcile_marks_running_from_squeue(tmp_path: Path, monkeypatch) -> None:
    remote_root = tmp_path / "remote_root"
    running_dir = remote_root / "running" / "pzjob-rec_a-001"
    running_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        running_dir / "orca_job.json",
        {
            "candidate_id": "rec_a",
            "backend": "orca_slurm",
            "engine": "orca",
            "job_driver": "direct_orca",
            "simulation_type": "geometry_optimization",
            "operation": {"submission_id": "submit-001", "remote_settings": {"target": "cluster-alpha"}},
        },
    )
    _write_json(running_dir / "scheduler.json", {"scheduler_job_id": "12345"})

    calls: list[list[str]] = []

    def fake_run(args, text, capture_output):
        calls.append(args)
        if args[0] == "sacct":
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="12345|RUNNING\n", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("sys.argv", [str(SCRIPT_PATH), str(running_dir)])

    try:
        run_path(str(SCRIPT_PATH), run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 0

    status = json.loads((running_dir / "status.json").read_text())
    scheduler = json.loads((running_dir / "scheduler.json").read_text())
    assert status["status"] == "running"
    assert scheduler["source"] == "squeue"
    assert any(call[0] == "sacct" for call in calls)
    assert any(call[0] == "squeue" for call in calls)


def test_remote_reconcile_synthesizes_failure_and_moves_job(tmp_path: Path, monkeypatch) -> None:
    remote_root = tmp_path / "remote_root"
    running_dir = remote_root / "running" / "pzjob-rec_a-001"
    running_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        running_dir / "orca_job.json",
        {
            "candidate_id": "rec_a",
            "backend": "orca_slurm",
            "engine": "orca",
            "job_driver": "direct_orca",
            "simulation_type": "geometry_optimization",
            "operation": {"submission_id": "submit-001", "remote_settings": {"target": "cluster-alpha"}},
            "provenance": {"request_id": "simreq::x::rec_a"},
        },
    )
    _write_json(running_dir / "scheduler.json", {"scheduler_job_id": "12345"})

    def fake_run(args, text, capture_output):
        if args[0] == "sacct":
            return subprocess.CompletedProcess(args, 0, stdout="12345|FAILED|1:0\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("sys.argv", [str(SCRIPT_PATH), str(running_dir)])

    try:
        run_path(str(SCRIPT_PATH), run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 0

    failed_dir = remote_root / "failed" / "pzjob-rec_a-001"
    assert failed_dir.exists()
    failure = json.loads((failed_dir / "failure.json").read_text())
    status = json.loads((failed_dir / "status.json").read_text())
    assert failure["failure_kind"] == "scheduler_terminal_failure"
    assert status["status"] == "failed"
