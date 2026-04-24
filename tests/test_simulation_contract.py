from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pz_agent.runner import run_pipeline


CSV_TEXT = """_id,smiles,source_group,sa_score,oxidation_potential,reduction_potential,groundState.solvation_energy,hole_reorganization_energy,electron_reorganization_energy\nrec_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.2,1.4,0.7,-0.8,0.2,0.3\nrec_b,CCN1c2ccccc2Sc2ccccc21,demo,2.1,0.4,0.2,0.1,1.1,1.2\n"""


def _run_contract_fixture(tmp_path: Path, monkeypatch) -> Path:
    csv_path = tmp_path / "contract.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")

    monkeypatch.setattr(
        "pz_agent.agents.structure_expansion.expand_structure_with_pubchem",
        lambda candidate, similarity_threshold=90, similarity_max_records=5, substructure_max_records=5, timeout=20: {
            "query_smiles": candidate.get("smiles"),
            "synonyms": ["ContractSynonym"],
            "exact_matches": [],
            "similarity_matches": [],
            "substructure_matches": [],
            "status": "ok",
        },
    )
    monkeypatch.setattr(
        "pz_agent.agents.patent_retrieval.retrieve_patent_evidence_for_candidate",
        lambda candidate, count=5, timeout=20: {
            "queries": [f"{candidate.get('id')} patent"],
            "surechembl": [],
            "patcid": [],
            "errors": [],
            "status": "ok",
        },
    )
    monkeypatch.setattr(
        "pz_agent.agents.scholarly_retrieval.retrieve_openalex_evidence_for_candidate",
        lambda candidate, count=5, mode="balanced", max_queries=6, exact_query_budget=None, analog_query_budget=None, exploratory_query_budget=None: {
            "queries": [f"{candidate.get('id')} chemistry"],
            "openalex": [],
            "errors": [],
            "status": "ok",
        },
    )

    config_path = tmp_path / "contract.yaml"
    config_path.write_text(
        f"""
project:
  name: simulation-contract-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: simulation contract validation
screening:
  shortlist_size: 2
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
  max_candidates: 2
search:
  backend: stub
simulation:
  max_candidates: 2
  backend: htvs_supercloud
  engine: xtb
  job_driver: htvs_jobconfig
  job_config: xtb_opt
  source_jobconfig: seed_xyz_import
  remote_target: cluster-alpha
  scheduler:
    system: slurm
    partition: xeon-p8
    nodes: 1
    time: 00:10:00
    mem_per_cpu: 2000
    no_requeue: true
    job_name_prefix: pztest
    mpi_module: mpi/openmpi-4.1.8
    orca_dir: /home/gridsan/groups/rgb_shared/software/orca/orca_6_0_0_linux_x86-64_shared_openmpi416
simulation_submit:
  submission_prefix: contract-submit
  transport: ssh
  remote_host: user@cluster.example.edu
  remote_root: /scratch/pz_agent_jobs
  remote_submit_command: /opt/pz_agent/bin/remote_submit_orca_job.py
  stage_method: rsync
  job_id_prefix: pzjob
""",
        encoding="utf-8",
    )

    run_dir = tmp_path / "run"
    run_pipeline(config_path, run_dir=run_dir)
    return run_dir


def test_htvs_xtb_contract_fixture_uses_explicit_htvs_backend(tmp_path: Path, monkeypatch) -> None:
    run_dir = _run_contract_fixture(tmp_path, monkeypatch)
    manifest = json.loads((run_dir / "simulation_manifest.json").read_text())

    defaults = manifest["simulation_defaults"]
    params = defaults["parameters"]

    assert manifest["contract_version"] == "htvs.request_response.v1"
    assert defaults["simulation_type"] == "geometry_optimization"
    assert defaults["backend"] == "htvs_supercloud"
    assert defaults["engine"] == "xtb"
    assert defaults["job_driver"] == "htvs_jobconfig"
    assert defaults["execution_mode"] == "remote"
    assert defaults["requested_outputs"] == [
        "optimized_structure",
        "final_energy",
        "groundState.solvation_energy",
        "groundState.homo",
        "groundState.lumo",
        "groundState.homo_lumo_gap",
        "groundState.dipole_moment",
        "status",
    ]

    assert params["opt_type"] == "min"
    assert params["job_config"] == "xtb_opt"
    assert params["source_jobconfig"] == "seed_xyz_import"
    assert params["xtb_method"] == "GFN2-xTB"
    assert params["solvent"] == "water"
    assert params["solvation_model"] == "ALPB"
    assert params["remote_target"] == "cluster-alpha"


def test_htvs_xtb_submission_records_match_contract(tmp_path: Path, monkeypatch) -> None:
    run_dir = _run_contract_fixture(tmp_path, monkeypatch)

    queue = json.loads((run_dir / "simulation_queue.json").read_text())
    submissions = json.loads((run_dir / "simulation_submissions.json").read_text())
    checks = json.loads((run_dir / "simulation_checks.json").read_text())
    job_spec = json.loads((run_dir / "orca_jobs" / "rec_a" / "orca_job.json").read_text())

    assert queue[0]["simulation"]["parameters"]["job_config"] == "xtb_opt"
    assert queue[0]["simulation"]["parameters"]["source_jobconfig"] == "seed_xyz_import"
    assert queue[0]["simulation"]["parameters"]["solvent"] == "water"
    assert queue[0]["simulation"]["parameters"]["remote_target"] == "cluster-alpha"

    assert job_spec["contract_version"] == "htvs.request_response.v1"
    assert job_spec["request_type"] == "submit_simulation"
    assert job_spec["operation"]["check_only"] is False
    assert job_spec["parameters"]["job_config"] == "xtb_opt"
    assert job_spec["parameters"]["source_jobconfig"] == "seed_xyz_import"
    assert job_spec["parameters"]["solvent"] == "water"
    assert job_spec["parameters"]["remote_target"] == "cluster-alpha"
    assert job_spec["requested_outputs"] == [
        "optimized_structure",
        "final_energy",
        "groundState.solvation_energy",
        "groundState.homo",
        "groundState.lumo",
        "groundState.homo_lumo_gap",
        "groundState.dipole_moment",
        "status",
    ]
    assert job_spec["provenance"]["remote_target"] == "cluster-alpha"
    assert job_spec["engine"] == "xtb"
    assert job_spec["parameters"]["xtb_method"] == "GFN2-xTB"
    assert job_spec["parameters"]["solvation_model"] == "ALPB"
    assert job_spec["parameters"]["solvent"] == "water"
    assert job_spec["scheduler"]["system"] == "slurm"
    assert job_spec["scheduler"]["partition"] == "xeon-p8"
    assert job_spec["scheduler"]["job_name"] == "pztest_rec_a"
    assert job_spec["scheduler"]["mpi_module"] == "mpi/openmpi-4.1.8"

    assert submissions[0]["response_type"] in {"submission_ack", "submission_failure"}
    assert submissions[0]["status"] in {"failed", "submitted", "inbox", "pending", "completed"}
    assert submissions[0]["backend"] == "htvs_supercloud"
    assert submissions[0]["engine"] == "xtb"
    assert submissions[0]["job_driver"] == "htvs_jobconfig"
    assert submissions[0]["remote_target"] == "cluster-alpha"
    assert submissions[0].get("retry_suffix") is None
    assert submissions[0]["submission_id"].startswith("contract-submit-")
    assert submissions[0]["remote_settings"]["ssh_host"] == "user@cluster.example.edu"
    assert submissions[0]["remote_settings"]["htvs_root"] == "/scratch/pz_agent_jobs"
    if submissions[0]["response_type"] == "submission_ack":
        assert checks[0]["request_type"] == "check_simulation"
        assert checks[0]["response_type"] == "status_envelope"
        assert checks[0]["backend"] == "htvs_supercloud"
        assert checks[0]["status"] in {"submitted", "inbox", "pending", "completed"}


def test_htvs_check_prefers_remote_job_root_snapshot(tmp_path: Path, monkeypatch) -> None:
    run_dir = _run_contract_fixture(tmp_path, monkeypatch)

    job_root = run_dir / "htvs-local" / "contract-submit-rec_a-001" / "jobs"
    jobdir = job_root / "pending" / "50000_xtb_opt__demo"
    jobdir.mkdir(parents=True, exist_ok=True)
    (jobdir / "job_manager-job_id").write_text("123456\n", encoding="utf-8")

    from pz_agent.simulation.backends.htvs import HtvsBackend

    backend = HtvsBackend()
    queue = json.loads((run_dir / "simulation_queue.json").read_text())
    queue_item = queue[0]
    submission = {
        **queue_item["submission"],
        "remote_settings": {
            **queue_item["submission"].get("remote_settings", {}),
            "job_root": str(job_root),
        },
    }
    check = backend.check(
        candidate_id="rec_a",
        submission=submission,
        simulation=queue_item["simulation"],
        check_config={},
    )

    assert check["status"] == "pending"
    assert check["authoritative"] is True
    assert check["status_source"] == "local_job_root_snapshot"
    assert check["jobdir_snapshot"]["scheduler_job_id"] == "123456"


def test_legacy_wrapper_submit_can_execute_real_handoff_commands(tmp_path: Path, monkeypatch) -> None:
    run_dir = _run_contract_fixture(tmp_path, monkeypatch)

    command_log: list[str] = []

    def fake_run(command, shell, text, capture_output, cwd=None):
        assert shell is True
        assert text is True
        assert capture_output is True
        command_log.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("pz_agent.simulation.backends.atomisticskills.subprocess.run", fake_run)

    from pz_agent.simulation.backends.atomisticskills import AtomisticSkillsBackend

    queue = json.loads((run_dir / "simulation_queue.json").read_text())
    queue_item = queue[0]
    backend = AtomisticSkillsBackend()
    submission = backend.submit(
        candidate_id="rec_a",
        queue_rank=1,
        job_spec_path=queue_item["job_package"]["job_spec_path"],
        simulation=queue_item["simulation"],
        submit_config={
            "submission_prefix": "contract-submit",
            "transport": "ssh",
            "remote_host": "user@cluster.example.edu",
            "remote_root": "/scratch/pz_agent_jobs",
            "remote_submit_command": "/opt/pz_agent/bin/remote_submit_orca_job.py",
            "stage_method": "rsync",
            "job_id_prefix": "pzjob",
            "remote_target": "cluster-alpha",
            "execute_handoff": True,
        },
    )

    assert submission["status"] == "submitted"
    assert submission["response_type"] == "submission_ack"
    assert submission["handoff_execution"]["executed"] is True
    assert len(submission["handoff_execution"]["command_results"]) == 3
    assert all(item["ok"] is True for item in submission["handoff_execution"]["command_results"])
    assert command_log[0].startswith("mkdir -p /scratch/pz_agent_jobs/inbox/pzjob-rec_a-001")
    assert "rsync -r" in command_log[1]
    assert "ssh user@cluster.example.edu '/opt/pz_agent/bin/remote_submit_orca_job.py /scratch/pz_agent_jobs/inbox/pzjob-rec_a-001'" == command_log[2]


def test_legacy_wrapper_submit_marks_failed_handoff_command(tmp_path: Path, monkeypatch) -> None:
    run_dir = _run_contract_fixture(tmp_path, monkeypatch)

    def fake_run(command, shell, text, capture_output, cwd=None):
        if command.startswith("rsync"):
            return subprocess.CompletedProcess(command, 23, stdout="", stderr="rsync failed")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("pz_agent.simulation.backends.atomisticskills.subprocess.run", fake_run)

    from pz_agent.simulation.backends.atomisticskills import AtomisticSkillsBackend

    queue = json.loads((run_dir / "simulation_queue.json").read_text())
    queue_item = queue[0]
    backend = AtomisticSkillsBackend()
    submission = backend.submit(
        candidate_id="rec_a",
        queue_rank=1,
        job_spec_path=queue_item["job_package"]["job_spec_path"],
        simulation=queue_item["simulation"],
        submit_config={
            "submission_prefix": "contract-submit",
            "transport": "ssh",
            "remote_host": "user@cluster.example.edu",
            "remote_root": "/scratch/pz_agent_jobs",
            "remote_submit_command": "/opt/pz_agent/bin/remote_submit_orca_job.py",
            "stage_method": "rsync",
            "job_id_prefix": "pzjob",
            "remote_target": "cluster-alpha",
            "execute_handoff": True,
        },
    )

    assert submission["status"] == "failed"
    assert submission["response_type"] == "submission_failure"
    assert submission["handoff_execution"]["executed"] is True
    assert submission["handoff_execution"]["error_message"] == "rsync failed"
    assert len(submission["handoff_execution"]["command_results"]) == 2
    assert submission["handoff_execution"]["command_results"][1]["ok"] is False


def test_htvs_check_can_fetch_remote_status_over_ssh(tmp_path: Path, monkeypatch) -> None:
    run_dir = _run_contract_fixture(tmp_path, monkeypatch)

    def fake_run(command, shell, text, capture_output, cwd=None):
        if "python - <<'PY'" in command or "python3 - <<'PY'" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "job_root": "/scratch/pz_agent_jobs/inbox/contract-submit-rec_a-001/jobs",
                        "exists": True,
                        "buckets": {"inbox": [], "pending": ["50000_xtb_opt__demo"], "completed": []},
                        "status": "pending",
                        "jobdir_name": "50000_xtb_opt__demo",
                        "jobdir": "/scratch/pz_agent_jobs/inbox/contract-submit-rec_a-001/jobs/pending/50000_xtb_opt__demo",
                        "files": ["job_manager-job_id"],
                        "scheduler_job_id": "123456",
                        "slurm_logs": [],
                    }
                ),
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr("pz_agent.simulation.backends.htvs.subprocess.run", fake_run)

    from pz_agent.simulation.backends.htvs import HtvsBackend

    queue = json.loads((run_dir / "simulation_queue.json").read_text())
    queue_item = queue[0]

    backend = HtvsBackend()
    check = backend.check(
        candidate_id="rec_a",
        submission=queue_item["submission"],
        simulation=queue_item["simulation"],
        check_config={
            "ssh_host": "user@cluster.example.edu",
            "htvs_root": "/scratch/pz_agent_jobs",
        },
    )

    assert check["status"] == "pending"
    assert check["authoritative"] is True
    assert check["status_source"] == "remote_job_root_snapshot"
    assert check["jobdir_snapshot"]["scheduler_job_id"] == "123456"
