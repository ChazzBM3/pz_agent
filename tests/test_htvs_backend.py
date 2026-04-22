from __future__ import annotations

import json
from pathlib import Path

from pz_agent.simulation.backends.htvs import HtvsBackend


def test_htvs_extract_reads_completed_jobdir_outputs(tmp_path: Path) -> None:
    job_root = tmp_path / "htvs-demo-001" / "jobs"
    jobdir = job_root / "completed" / "50000_dft_opt_orca__demo"
    jobdir.mkdir(parents=True, exist_ok=True)

    (jobdir / "job_manager-job_id").write_text("4570482\n", encoding="utf-8")
    (jobdir / "optimized_structure.xyz").write_text(
        "2\nopt\nH 0.0 0.0 0.0\nH 0.0 0.0 0.7\n",
        encoding="utf-8",
    )
    (jobdir / "job.out").write_text(
        "FINAL SINGLE POINT ENERGY      -123.456789\n"
        "Magnitude (a.u.)              :    2.3456\n"
        "ORCA TERMINATED NORMALLY\n",
        encoding="utf-8",
    )
    (jobdir / "summary.json").write_text(
        json.dumps(
            {
                "groundState.homo": -5.1,
                "groundState.lumo": -1.2,
                "groundState.homo_lumo_gap": 3.9,
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
    assert result["outputs"]["groundState.solvation_energy"] == -0.42
    assert result["outputs"]["groundState.dipole_moment"] == 2.3456
    assert "H 0.0 0.0 0.7" in str(result["outputs"]["optimized_structure"])
    assert result["raw_result"]["jobdir_snapshot"]["scheduler_job_id"] == "4570482"
    assert (jobdir / "pz_agent_result.json").exists()


def test_htvs_extract_returns_none_when_not_completed(tmp_path: Path) -> None:
    job_root = tmp_path / "htvs-demo-002" / "jobs"
    (job_root / "pending" / "job123").mkdir(parents=True, exist_ok=True)

    backend = HtvsBackend()
    result = backend.extract(
        candidate_id="rec_b",
        submission={
            "submission_id": "htvs-demo-rec_b-001",
            "job_id": "job123",
            "remote_settings": {"job_root": str(job_root)},
        },
        simulation={"simulation_type": "geometry_optimization", "parameters": {}},
        extract_config={},
    )

    assert result is None
