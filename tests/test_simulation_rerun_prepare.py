from __future__ import annotations

import json
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


def test_simulation_rerun_prepare_builds_retry_queue(tmp_path: Path, monkeypatch) -> None:
    _patch_retrieval(monkeypatch)
    csv_path = tmp_path / "rerun.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    run_dir = tmp_path / "run_rerun"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "remote_results.json").write_text(
        json.dumps([
            {
                "candidate_id": "rec_a",
                "submission_id": "rerun-submit-001",
                "status": "failed",
                "backend": "atomisticskills_orca",
                "engine": "orca",
                "simulation_type": "geometry_optimization",
                "outputs": {"status": "failed"},
            }
        ]),
        encoding="utf-8",
    )
    config_path = tmp_path / "rerun.yaml"
    config_path.write_text(
        f"""
project:
  name: simulation-rerun-prepare-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: simulation rerun prepare test
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
    - simulation_rerun_prepare
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
  remote_target: cluster-alpha
simulation_submit:
  submission_prefix: rerun-submit
simulation_extract:
  results_path: remote_results.json
simulation_rerun_prepare:
  retry_prefix: retry-orca
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=run_dir)

    assert state.simulation_rerun_queue is not None
    assert len(state.simulation_rerun_queue) == 1
    assert state.simulation_rerun_queue[0]["candidate_id"] == "rec_a"
    assert state.simulation_rerun_queue[0]["retry_id"] == "retry-orca-001"
    assert state.simulation_rerun_queue[0]["status"] == "prepared_for_rerun"
    assert state.simulation_rerun_queue[0]["retry_metadata"]["previous_submission_id"] == "rerun-submit-001"
    assert state.simulation_rerun_queue[0]["retry_metadata"]["retry_attempt"] == 1
    assert state.simulation_rerun_queue[0]["retry_metadata"]["max_retry_attempts"] == 1
    assert state.simulation_rerun_queue[0]["simulation"]["parameters"]["convergence_max_iterations"] > 200
    assert state.simulation_rerun_queue[0]["simulation"]["parameters"]["special_option"] == ""
    assert state.simulation_rerun_queue[0]["retry_metadata"]["adjustments"]["soscf_enabled"] is True

    rerun_queue = json.loads((run_dir / "simulation_rerun_queue.json").read_text())
    assert len(rerun_queue) == 1
    assert rerun_queue[0]["job_spec_path"].endswith("orca_job.json")


def test_simulation_submit_can_consume_rerun_queue_with_retry_lineage(tmp_path: Path, monkeypatch) -> None:
    _patch_retrieval(monkeypatch)
    csv_path = tmp_path / "rerun_submit.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    run_dir = tmp_path / "run_rerun_submit"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "remote_results.json").write_text(
        json.dumps([
            {
                "candidate_id": "rec_a",
                "submission_id": "rerun-submit-001",
                "status": "failed",
                "backend": "atomisticskills_orca",
                "engine": "orca",
                "simulation_type": "geometry_optimization",
                "outputs": {"status": "failed"},
            }
        ]),
        encoding="utf-8",
    )
    config_path = tmp_path / "rerun_submit.yaml"
    config_path.write_text(
        f"""
project:
  name: simulation-rerun-submit-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: simulation rerun submit test
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
    - simulation_rerun_prepare
    - simulation_submit
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
  remote_target: cluster-alpha
simulation_submit:
  submission_prefix: rerun-submit
  use_rerun_queue: true
simulation_extract:
  results_path: remote_results.json
simulation_rerun_prepare:
  retry_prefix: retry-orca
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=run_dir)

    assert state.simulation_rerun_queue is not None
    assert state.simulation_rerun_queue[0]["retry_metadata"]["retry_attempt"] == 2
    assert state.simulation_rerun_queue[0]["retry_provenance"]["retry_of_submission_id"] == "rerun-submit-001"
    assert state.simulation_rerun_queue[0]["retry_provenance"]["retry_attempt"] == 2
    assert state.simulation_submissions is not None
    assert state.simulation_submissions[0]["submission_id"].endswith("retry-orca-001")


def test_simulation_rerun_prepare_respects_single_retry_limit(tmp_path: Path, monkeypatch) -> None:
    _patch_retrieval(monkeypatch)
    csv_path = tmp_path / "rerun_limit.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    run_dir = tmp_path / "run_rerun_limit"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "simulation_rerun_candidates.json").write_text(
        json.dumps([
            {
                "candidate_id": "rec_a",
                "submission_id": "rerun-submit-001",
                "status": "failed",
                "failure_source": "simulation_extract",
                "rerun_ready": True,
                "retry_metadata": {"retry_attempt": 1},
                "rerun_bundle": {
                    "candidate_id": "rec_a",
                    "submission_id": "rerun-submit-001",
                    "job_spec_path": str(run_dir / "orca_jobs" / "rec_a" / "orca_job.json"),
                    "simulation": {
                        "backend": "atomisticskills_orca",
                        "engine": "orca",
                        "simulation_type": "geometry_optimization",
                        "parameters": {"convergence_max_iterations": 200, "special_option": "NOSOSCF"},
                    },
                },
            }
        ]),
        encoding="utf-8",
    )
    config_path = tmp_path / "rerun_limit.yaml"
    config_path.write_text(
        f"""
project:
  name: simulation-rerun-limit-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: simulation rerun limit test
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
    - simulation_rerun_prepare
    - reporter
kg:
  backend: json
  path: artifacts/knowledge_graph.json
critique:
  enable_web_search: false
  max_candidates: 2
search:
  backend: stub
simulation_rerun_prepare:
  retry_prefix: retry-orca
  max_retry_attempts: 1
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=run_dir)
    assert state.simulation_rerun_queue == []
