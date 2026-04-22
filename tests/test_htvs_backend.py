from __future__ import annotations

import json
from pathlib import Path

from pz_agent.agents.simulation_check import _normalize_check_config
from pz_agent.agents.simulation_submit import _normalize_submit_config
from pz_agent.simulation.backends.htvs import HtvsBackend


def test_htvs_submit_config_normalizer_maps_legacy_wrapper_fields() -> None:
    simulation = {"backend": "htvs_supercloud"}
    job_package = {"structure_path": "/tmp/input_structure.xyz"}
    normalized = _normalize_submit_config(
        {
            "remote_host": "user@cluster.example.edu",
            "remote_root": "/scratch/pz_agent_jobs",
            "remote_submit_command": "/opt/pz_agent/bin/remote_submit_orca_job.py",
        },
        simulation,
        job_package,
    )

    assert normalized["ssh_host"] == "user@cluster.example.edu"
    assert normalized["htvs_root"] == "/scratch/pz_agent_jobs"
    assert normalized["geometry_path"] == "/tmp/input_structure.xyz"
    assert normalized["remote_job_root_base"] == "/scratch/pz_agent_jobs/inbox"
    assert normalized["remote_submit_command_legacy"] == "/opt/pz_agent/bin/remote_submit_orca_job.py"


def test_htvs_check_config_normalizer_maps_legacy_wrapper_fields() -> None:
    normalized = _normalize_check_config(
        {"remote_host": "user@cluster.example.edu", "remote_root": "/scratch/pz_agent_jobs"},
        {"remote_settings": {}},
        {"backend": "htvs_supercloud"},
    )

    assert normalized["ssh_host"] == "user@cluster.example.edu"
    assert normalized["htvs_root"] == "/scratch/pz_agent_jobs"


def test_htvs_extract_reads_completed_jobdir_outputs(tmp_path: Path) -> None:
    job_root = tmp_path / "htvs-demo-001" / "jobs"
    jobdir = job_root / "completed" / "50000_dft_opt_orca__demo"
    jobdir.mkdir(parents=True, exist_ok=True)

    (jobdir / "job_manager-job_id").write_text("4570482\n", encoding="utf-8")
    (jobdir / "orca_dft_opt.xyz").write_text(
        "2\nopt\nH 0.0 0.0 0.0\nH 0.0 0.0 0.7\n",
        encoding="utf-8",
    )
    (jobdir / "orca_dft_opt.out").write_text(
        "FINAL SINGLE POINT ENERGY      -123.456789\n"
        "ORCA TERMINATED NORMALLY\n",
        encoding="utf-8",
    )
    (jobdir / "orca_dft_opt.property.txt").write_text(
        "HOMO                                     -5.10 eV\n"
        "LUMO                                     -1.20 eV\n"
        "HOMO-LUMO GAP                             3.90 eV\n"
        "Magnitude (Debye)                         2.34\n",
        encoding="utf-8",
    )
    (jobdir / "summary.json").write_text(
        json.dumps(
            {
                "groundState.solvation_energy": -0.42,
                "status": "completed",
            }
        ),
        encoding="utf-8",
    )

    backend = HtvsBackend()
    result = backend.extract(
        candidate_id="rec_a",
        submission={
            "submission_id": "htvs-demo-rec_a-001",
            "job_id": "50000_dft_opt_orca__demo",
            "backend": "htvs_supercloud",
            "engine": "orca",
            "remote_target": "supercloud",
            "remote_settings": {"job_root": str(job_root)},
        },
        simulation={
            "backend": "htvs_supercloud",
            "engine": "orca",
            "simulation_type": "geometry_optimization",
            "parameters": {"remote_target": "supercloud"},
        },
        extract_config={},
    )

    assert result is not None
    assert result["status"] == "completed"
    assert result["outputs"]["final_energy"] == -123.456789
    assert result["outputs"]["groundState.homo"] == -5.1
    assert result["outputs"]["groundState.lumo"] == -1.2
    assert result["outputs"]["groundState.homo_lumo_gap"] == 3.9
    assert result["outputs"]["groundState.solvation_energy"] == -0.42
    assert result["outputs"]["groundState.dipole_moment"] == 2.34
    assert "H 0.0 0.0 0.7" in str(result["outputs"]["optimized_structure"])
    assert result["raw_result"]["jobdir_snapshot"]["scheduler_job_id"] == "4570482"
    assert (jobdir / "pz_agent_result.json").exists()


def test_htvs_extract_marks_slurm_side_failure_even_in_completed_bucket(tmp_path: Path) -> None:
    job_root = tmp_path / "htvs-demo-002" / "jobs"
    jobdir = job_root / "completed" / "job123"
    jobdir.mkdir(parents=True, exist_ok=True)
    (jobdir / "job_manager-job_id").write_text("999\n", encoding="utf-8")
    (jobdir / "orca_dft_opt.out").write_text("", encoding="utf-8")
    (jobdir / "slurm-999.out").write_text(
        "Running ORCA\n"
        "/path/to/orca: Permission denied\n"
        "Finished cleaning up\n",
        encoding="utf-8",
    )

    backend = HtvsBackend()
    result = backend.extract(
        candidate_id="rec_b",
        submission={
            "submission_id": "htvs-demo-rec_b-001",
            "job_id": "job123",
            "backend": "htvs_supercloud",
            "engine": "orca",
            "remote_settings": {"job_root": str(job_root)},
        },
        simulation={"simulation_type": "geometry_optimization", "parameters": {}},
        extract_config={},
    )

    assert result is not None
    assert result["status"] == "failed"
    assert result["response_type"] == "failure_envelope"
    assert result["outputs"]["status"] == "failed"


def test_htvs_extract_returns_none_when_not_completed(tmp_path: Path) -> None:
    job_root = tmp_path / "htvs-demo-003" / "jobs"
    (job_root / "pending" / "job123").mkdir(parents=True, exist_ok=True)

    backend = HtvsBackend()
    result = backend.extract(
        candidate_id="rec_c",
        submission={
            "submission_id": "htvs-demo-rec_c-001",
            "job_id": "job123",
            "remote_settings": {"job_root": str(job_root)},
        },
        simulation={"simulation_type": "geometry_optimization", "parameters": {}},
        extract_config={},
    )

    assert result is None
