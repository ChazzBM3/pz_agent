from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pz_agent.runner import run_pipeline


CSV_TEXT = """_id,smiles,source_group,sa_score,oxidation_potential,reduction_potential,groundState.solvation_energy,hole_reorganization_energy,electron_reorganization_energy\nrec_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.2,1.4,0.7,-0.8,0.2,0.3\nrec_b,CCN1c2ccccc2Sc2ccccc21,demo,2.1,0.4,0.2,0.1,1.1,1.2\n"""


def _patch_retrieval(monkeypatch) -> None:
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


def test_simulation_extract_logs_failed_runs_without_rerun_metadata(tmp_path: Path, monkeypatch) -> None:
    _patch_retrieval(monkeypatch)
    csv_path = tmp_path / "extract.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    run_dir = tmp_path / "run_extract"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "remote_results.json").write_text(
        json.dumps([
            {
                "candidate_id": "rec_a",
                "submission_id": "extract-submit-001",
                "status": "failed",
                "backend": "orca_slurm",
                "engine": "orca",
                "simulation_type": "geometry_optimization",
                "outputs": {"status": "failed"},
            }
        ]),
        encoding="utf-8",
    )
    config_path = tmp_path / "extract.yaml"
    config_path.write_text(
        f"""
project:
  name: simulation-extract-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: simulation extract test
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
    - simulation_extract
    - validation_ingest
    - reporter
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
  backend: orca_slurm
  remote_target: cluster-alpha
simulation_submit:
  submission_prefix: extract-submit
simulation_extract:
  results_path: remote_results.json
validation_ingest:
  results_path: remote_results.json
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=run_dir)

    assert state.simulation_extractions == []
    assert state.simulation_failures is not None
    assert len(state.simulation_failures) == 1
    assert state.simulation_failures[0]["response_type"] == "failure_envelope"
    assert state.simulation_failures[0]["failure_log"]["logged_for_followup"] is True
    assert state.simulation_failures[0]["failure_log"]["job_spec_path"].endswith("orca_job.json")
    assert not (run_dir / "simulation_rerun_candidates.json").exists()


def test_simulation_extract_prefers_local_artifact_results(tmp_path: Path, monkeypatch) -> None:
    _patch_retrieval(monkeypatch)
    csv_path = tmp_path / "artifact_extract.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    run_dir = tmp_path / "run_artifact_extract"
    run_dir.mkdir(parents=True, exist_ok=True)

    config_path = tmp_path / "artifact_extract.yaml"
    config_path.write_text(
        f"""
project:
  name: simulation-artifact-extract-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: simulation artifact extract test
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
  backend: orca_slurm
  remote_target: cluster-alpha
simulation_submit:
  submission_prefix: artifact-submit
simulation_extract:
  results_path: remote_results.json
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=run_dir)
    result_path = run_dir / "orca_jobs" / "rec_a" / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "contract_version": "orca_slurm.request_response.v1",
                "request_type": "extract_simulation_result",
                "response_type": "result_envelope",
                "candidate_id": "rec_a",
                "submission_id": "artifact-submit-001",
                "job_id": "stubjob-rec_a",
                "status": "completed",
                "backend": "orca_slurm",
                "engine": "orca",
                "simulation_type": "geometry_optimization",
                "outputs": {
                    "status": "completed",
                    "final_energy": -111.1,
                    "optimized_structure": "rec_a_opt.xyz"
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    from pz_agent.agents.simulation_extract import SimulationExtractAgent

    state = SimulationExtractAgent(config=state.config).run(state)

    assert len(state.simulation_extractions or []) == 1
    assert state.simulation_extractions[0]["candidate_id"] == "rec_a"
    assert state.simulation_extractions[0]["outputs"]["final_energy"] == -111.1
    assert state.simulation_extractions[0]["provenance"]["results_path"].endswith("simulation_artifact_results.json")


def test_simulation_extract_can_fetch_remote_artifact_over_ssh(tmp_path: Path, monkeypatch) -> None:
    _patch_retrieval(monkeypatch)
    csv_path = tmp_path / "remote_artifact_extract.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    run_dir = tmp_path / "run_remote_artifact_extract"
    run_dir.mkdir(parents=True, exist_ok=True)

    config_path = tmp_path / "remote_artifact_extract.yaml"
    config_path.write_text(
        f"""
project:
  name: simulation-remote-artifact-extract-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: simulation remote artifact extract test
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
  backend: orca_slurm
  remote_target: cluster-alpha
simulation_submit:
  submission_prefix: remote-artifact-submit
  transport: ssh
  remote_host: user@cluster.example.edu
  remote_root: /scratch/pz_agent_jobs
  remote_submit_command: /opt/pz_agent/bin/remote_submit_orca_job.py
  stage_method: rsync
  job_id_prefix: pzjob
simulation_extract:
  results_path: remote_results.json
  transport: ssh
  remote_host: user@cluster.example.edu
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=run_dir)

    def fake_run(command, shell, text, capture_output):
        assert shell is True
        if command.endswith("/result.json'"):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "contract_version": "orca_slurm.request_response.v1",
                        "request_type": "extract_simulation_result",
                        "response_type": "result_envelope",
                        "candidate_id": "rec_a",
                        "submission_id": "remote-artifact-submit-001",
                        "job_id": "pzjob-rec_a-001",
                        "status": "completed",
                        "backend": "orca_slurm",
                        "engine": "orca",
                        "simulation_type": "geometry_optimization",
                        "outputs": {
                            "status": "completed",
                            "final_energy": -222.2,
                            "optimized_structure": "rec_a_remote.xyz"
                        }
                    }
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="missing")

    monkeypatch.setattr("pz_agent.agents.simulation_extract.subprocess.run", fake_run)

    from pz_agent.agents.simulation_extract import SimulationExtractAgent

    state = SimulationExtractAgent(config=state.config).run(state)

    assert len(state.simulation_extractions or []) == 1
    assert state.simulation_extractions[0]["candidate_id"] == "rec_a"
    assert state.simulation_extractions[0]["outputs"]["final_energy"] == -222.2
    assert (run_dir / "simulation_remote_fetch_log.json").exists()
