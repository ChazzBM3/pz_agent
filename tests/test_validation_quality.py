from __future__ import annotations

import json
from pathlib import Path

from pz_agent.runner import run_pipeline


CSV_TEXT = """_id,smiles,source_group,sa_score,oxidation_potential,reduction_potential,groundState.solvation_energy,hole_reorganization_energy,electron_reorganization_energy\nrec_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.2,1.4,0.7,-0.8,0.2,0.3\nrec_b,CCN1c2ccccc2Sc2ccccc21,demo,2.1,0.4,0.2,0.1,1.1,1.2\n"""


def _base_config(csv_path: Path, results_name: str) -> str:
    return f"""
project:
  name: validation-quality-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: validation quality test
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
  remote_target: cluster-alpha
simulation_submit:
  submission_prefix: quality-submit
simulation_extract:
  results_path: {results_name}
validation_ingest:
  results_path: {results_name}
"""


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


def test_validation_ingest_marks_partial_when_requested_outputs_missing(tmp_path: Path, monkeypatch) -> None:
    _patch_retrieval(monkeypatch)
    csv_path = tmp_path / "partial.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    run_dir = tmp_path / "run_partial"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "partial_results.json").write_text(
        json.dumps([
            {
                "candidate_id": "rec_a",
                "submission_id": "quality-submit-001",
                "status": "completed",
                "outputs": {
                    "final_energy": -50.0,
                    "groundState.solvation_energy": -0.25,
                    "groundState.homo": -5.1,
                    "groundState.lumo": -1.0,
                    "status": "converged",
                },
            }
        ]),
        encoding="utf-8",
    )
    config_path = tmp_path / "partial.yaml"
    config_path.write_text(_base_config(csv_path, "partial_results.json"), encoding="utf-8")

    state = run_pipeline(config_path, run_dir=run_dir)
    quality = state.validation[0]["quality_assessment"]
    assert quality["quality"] == "partial"
    assert quality["requested_outputs_complete"] is False
    assert "optimized_structure" in quality["missing_requested_outputs"]
    assert "groundState.solvation_energy" not in quality["missing_requested_outputs"]
    assert "groundState.homo" not in quality["missing_requested_outputs"]
    assert "groundState.lumo" not in quality["missing_requested_outputs"]

    report = json.loads((run_dir / "report.json").read_text())
    assert report["summary"]["partial_validation_count"] == 1

    graph_path = run_dir / "artifacts" / "knowledge_graph.json"
    if graph_path.exists():
        graph = json.loads(graph_path.read_text())
        assert not any(node["type"] == "SimulationResult" for node in graph.get("nodes", []))
        assert not any(node["type"] == "ValidationOutcome" for node in graph.get("nodes", []))


def test_validation_ingest_skips_failed_runs(tmp_path: Path, monkeypatch) -> None:
    _patch_retrieval(monkeypatch)
    csv_path = tmp_path / "failed.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    run_dir = tmp_path / "run_failed"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "failed_results.json").write_text(
        json.dumps([
            {
                "candidate_id": "rec_a",
                "submission_id": "quality-submit-001",
                "status": "failed",
                "outputs": {
                    "status": "failed",
                },
            }
        ]),
        encoding="utf-8",
    )
    config_path = tmp_path / "failed.yaml"
    config_path.write_text(_base_config(csv_path, "failed_results.json"), encoding="utf-8")

    state = run_pipeline(config_path, run_dir=run_dir)
    assert state.validation == []
    assert state.simulation_failures is not None
    assert len(state.simulation_failures) == 1
    assert state.simulation_failures[0]["candidate_id"] == "rec_a"
    assert state.simulation_failures[0]["status"] == "failed"

    report = json.loads((run_dir / "report.json").read_text())
    assert report["summary"]["failed_validation_count"] == 0
    assert report["summary"]["validation_count"] == 0
    assert report["summary"]["simulation_failure_count"] == 1

    graph_path = run_dir / "artifacts" / "knowledge_graph.json"
    if graph_path.exists():
        graph = json.loads(graph_path.read_text())
        assert not any(node["type"] == "SimulationResult" for node in graph.get("nodes", []))
        assert not any(node["type"] == "ValidationOutcome" for node in graph.get("nodes", []))
