from __future__ import annotations

import json
from pathlib import Path

from pz_agent.agents.simulation_check import _normalize_check_config
from pz_agent.agents.simulation_submit import _normalize_submit_config
from pz_agent.simulation.backends.htvs import HtvsBackend
from pz_agent.runner import run_pipeline


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


def test_htvs_pipeline_submit_and_check_accepts_normalized_native_config(tmp_path: Path, monkeypatch) -> None:
    csv_text = """_id,smiles,source_group,sa_score,oxidation_potential,reduction_potential,groundState.solvation_energy,hole_reorganization_energy,electron_reorganization_energy\nrec_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.2,1.4,0.7,-0.8,0.2,0.3\n"""
    csv_path = tmp_path / "htvs_contract.csv"
    csv_path.write_text(csv_text, encoding="utf-8")

    monkeypatch.setattr(
        "pz_agent.agents.structure_expansion.expand_structure_with_pubchem",
        lambda candidate, similarity_threshold=90, similarity_max_records=5, substructure_max_records=5, timeout=20: {
            "query_smiles": candidate.get("smiles"),
            "synonyms": [],
            "exact_matches": [],
            "similarity_matches": [],
            "substructure_matches": [],
            "status": "ok",
        },
    )
    monkeypatch.setattr(
        "pz_agent.agents.patent_retrieval.retrieve_patent_evidence_for_candidate",
        lambda candidate, count=5, timeout=20: {"queries": [], "surechembl": [], "patcid": [], "errors": [], "status": "ok"},
    )
    monkeypatch.setattr(
        "pz_agent.agents.scholarly_retrieval.retrieve_openalex_evidence_for_candidate",
        lambda candidate, count=5, mode="balanced", max_queries=6, exact_query_budget=None, analog_query_budget=None, exploratory_query_budget=None: {"queries": [], "openalex": [], "errors": [], "status": "ok"},
    )

    call_count = {"n": 0}

    def fake_run(command, shell, text, capture_output, cwd=None):
        assert shell is True
        call_count["n"] += 1
        if call_count["n"] == 1:
            assert command.startswith("ssh -T user@cluster.example.edu 'bash -s' <<'EOF'")
            return __import__("subprocess").CompletedProcess(command, 0, stdout="GROUP_OK\n/scratch/htvs/inbox/htvs-submit-rec_a-001/jobs\n", stderr="")
        if call_count["n"] == 2:
            assert command.startswith("ssh -T user@cluster.example.edu 'bash -s' <<'EOF'")
            payload = {
                "job_root": "/scratch/htvs/inbox/htvs-submit-rec_a-001/jobs",
                "exists": True,
                "buckets": {"inbox": [], "pending": ["50000_dft_opt_orca__demo"], "completed": []},
                "status": "pending",
                "jobdir_name": "50000_dft_opt_orca__demo",
                "jobdir": "/scratch/htvs/inbox/htvs-submit-rec_a-001/jobs/pending/50000_dft_opt_orca__demo",
                "files": ["job_manager-job_id"],
                "scheduler_job_id": "50000",
                "slurm_logs": [],
            }
            return __import__("subprocess").CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")
        raise AssertionError(command)

    monkeypatch.setattr("pz_agent.simulation.backends.htvs.subprocess.run", fake_run)

    config_path = tmp_path / "htvs_contract.yaml"
    config_path.write_text(
        f"""
project:
  name: htvs-contract-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 1
  d3tales_phenothiazine_only: true
  prompts:
    objective: htvs contract validation
screening:
  shortlist_size: 1
pipeline:
  stages:
    - library_designer
    - standardizer
    - structure_expansion
    - patent_retrieval
    - scholarly_retrieval
    - surrogate_screen
    - benchmark
    - knowledge_graph
    - ranker
    - critique
    - critique_reranker
    - knowledge_graph
    - graph_expansion
    - simulation_handoff
    - simulation_submit
    - simulation_check
kg:
  backend: json
  path: artifacts/knowledge_graph.json
critique:
  enable_web_search: false
  max_candidates: 1
search:
  backend: stub
simulation:
  max_candidates: 1
  backend: htvs_supercloud
  remote_target: cluster-alpha
simulation_submit:
  submission_prefix: htvs-submit
  transport: ssh
  remote_host: user@cluster.example.edu
  remote_root: /scratch/htvs
simulation_check:
  remote_host: user@cluster.example.edu
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=tmp_path / "run")

    assert state.simulation_submissions is not None
    assert state.simulation_checks is not None
    submission = state.simulation_submissions[0]
    check = state.simulation_checks[0]
    assert submission["backend"] == "htvs_supercloud"
    assert submission["remote_settings"]["ssh_host"] == "user@cluster.example.edu"
    assert submission["remote_settings"]["htvs_root"] == "/scratch/htvs"
    assert submission["remote_settings"]["remote_job_root"] == "/scratch/htvs/inbox/htvs-submit-rec_a-001/jobs"
    assert check["status"] == "pending"
    assert check["status_source"] == "remote_job_root_snapshot"
    assert check["authoritative"] is True


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


def test_htvs_extract_emits_partial_result_when_completed_bucket_lacks_requested_outputs(tmp_path: Path) -> None:
    job_root = tmp_path / "htvs-demo-004" / "jobs"
    jobdir = job_root / "completed" / "job124"
    jobdir.mkdir(parents=True, exist_ok=True)
    (jobdir / "job_manager-job_id").write_text("124\n", encoding="utf-8")
    (jobdir / "orca_dft_opt.out").write_text(
        "FINAL SINGLE POINT ENERGY      -98.765432\n"
        "ORCA TERMINATED NORMALLY\n",
        encoding="utf-8",
    )

    backend = HtvsBackend()
    result = backend.extract(
        candidate_id="rec_d",
        submission={
            "submission_id": "htvs-demo-rec_d-001",
            "job_id": "job124",
            "backend": "htvs_supercloud",
            "engine": "orca",
            "remote_settings": {"job_root": str(job_root)},
        },
        simulation={
            "simulation_type": "geometry_optimization",
            "parameters": {"remote_target": "supercloud"},
        },
        extract_config={},
    )

    assert result is not None
    assert result["status"] == "completed"
    assert result["response_type"] == "result_envelope"
    assert result["outputs"]["final_energy"] == -98.765432
    assert result["outputs"].get("optimized_structure") is None
    assert result["outputs"]["status"] == "completed"



def test_htvs_check_uses_local_job_root_snapshot_when_available(tmp_path: Path) -> None:
    job_root = tmp_path / "htvs-demo-005" / "jobs"
    jobdir = job_root / "completed" / "job125"
    jobdir.mkdir(parents=True, exist_ok=True)
    (jobdir / "job_manager-job_id").write_text("125\n", encoding="utf-8")

    backend = HtvsBackend()
    result = backend.check(
        candidate_id="rec_e",
        submission={
            "submission_id": "htvs-demo-rec_e-001",
            "job_id": "job125",
            "backend": "htvs_supercloud",
            "engine": "orca",
            "remote_settings": {"job_root": str(job_root)},
        },
        simulation={"backend": "htvs_supercloud", "engine": "orca", "parameters": {"remote_target": "supercloud"}},
        check_config={},
    )

    assert result["status"] == "completed"
    assert result["authoritative"] is True
    assert result["status_source"] == "local_job_root_snapshot"
    assert result["jobdir_snapshot"]["scheduler_job_id"] == "125"
