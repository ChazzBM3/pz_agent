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


def test_report_exposes_simulation_failures_and_retries(tmp_path: Path, monkeypatch) -> None:
    _patch_retrieval(monkeypatch)
    csv_path = tmp_path / "visibility.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    run_dir = tmp_path / "run_visibility"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "remote_results.json").write_text(
        json.dumps([
            {
                "candidate_id": "rec_a",
                "submission_id": "visible-submit-001",
                "status": "failed",
                "backend": "orca_slurm",
                "engine": "orca",
                "simulation_type": "geometry_optimization",
                "outputs": {"status": "failed"},
            }
        ]),
        encoding="utf-8",
    )
    config_path = tmp_path / "visibility.yaml"
    config_path.write_text(
        f"""
project:
  name: simulation-visibility-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: simulation visibility test
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
    - knowledge_graph
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
  submission_prefix: visible-submit
  use_rerun_queue: true
simulation_extract:
  results_path: remote_results.json
simulation_rerun_prepare:
  retry_prefix: retry-visible
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=run_dir)
    report = json.loads((run_dir / "report.json").read_text())
    assert "rec_a" in report["simulation_history_summary"]["failed_candidates"]
    assert "rec_a" in report["simulation_history_summary"]["rerun_candidates"]
    decision = next(item for item in report["decision_summary"] if item["candidate_id"] == "rec_a")
    assert decision["simulation_history"]["failure_count"] >= 1
    assert decision["simulation_history"]["rerun_count"] >= 1
    assert len(report["deferred_reruns"]) == 1
    assert report["deferred_reruns"][0]["candidate_id"] == "rec_a"
    assert report["deferred_reruns"][0]["orca_adjustments"]["soscf_enabled"] is True

    graph = json.loads(state.knowledge_graph_path.read_text())
    assert not any(node["type"] == "SimulationFailure" for node in graph.get("nodes", []))
    assert not any(node["type"] == "SimulationRetry" for node in graph.get("nodes", []))
