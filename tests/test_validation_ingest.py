from __future__ import annotations

import json
from pathlib import Path

from pz_agent.runner import run_pipeline


CSV_TEXT = """_id,smiles,source_group,sa_score,oxidation_potential,reduction_potential,groundState.solvation_energy,hole_reorganization_energy,electron_reorganization_energy\nrec_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.2,1.4,0.7,-0.8,0.2,0.3\nrec_b,CCN1c2ccccc2Sc2ccccc21,demo,2.1,0.4,0.2,0.1,1.1,1.2\n"""


RESULTS_PAYLOAD = [
    {
        "contract_version": "orca_slurm.request_response.v1",
        "request_type": "submit_simulation",
        "response_type": "result_envelope",
        "candidate_id": "rec_a",
        "submission_id": "contract-submit-001",
        "status": "completed",
        "backend": "orca_slurm",
        "engine": "orca",
        "simulation_type": "geometry_optimization",
        "remote_target": "cluster-alpha",
        "status_query": {"check_only": True, "submission_id": "contract-submit-001", "job_id": None},
        "outputs": {
            "final_energy": -123.456,
            "optimized_structure": "rec_a_optimized.xyz",
            "groundState.solvation_energy": -0.42,
            "groundState.homo": -5.67,
            "groundState.lumo": -1.23,
            "groundState.homo_lumo_gap": 4.44,
            "groundState.dipole_moment": 2.78,
            "status": "converged",
        },
    }
]


def test_validation_ingest_records_completed_results_and_updates_report(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "validation.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")

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
        lambda candidate, count=5, timeout=20: {
            "queries": [],
            "surechembl": [],
            "patcid": [],
            "errors": [],
            "status": "ok",
        },
    )
    monkeypatch.setattr(
        "pz_agent.agents.scholarly_retrieval.retrieve_openalex_evidence_for_candidate",
        lambda candidate, count=5, mode="balanced", max_queries=6, exact_query_budget=None, analog_query_budget=None, exploratory_query_budget=None: {
            "queries": [],
            "openalex": [],
            "errors": [],
            "status": "ok",
        },
    )

    run_dir = tmp_path / "run"
    results_path = run_dir / "remote_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(RESULTS_PAYLOAD), encoding="utf-8")

    config_path = tmp_path / "validation_ingest.yaml"
    config_path.write_text(
        f"""
project:
  name: validation-ingest-test
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: validation ingest test
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
  submission_prefix: contract-submit
simulation_extract:
  results_path: remote_results.json
validation_ingest:
  results_path: remote_results.json
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=run_dir)

    assert state.simulation_extractions is not None
    assert len(state.simulation_extractions) == 1
    assert state.simulation_extractions[0]["response_type"] == "result_envelope"
    assert state.validation is not None
    assert len(state.validation) == 1
    assert state.validation[0]["candidate_id"] == "rec_a"
    assert state.validation[0]["status"] == "completed"
    assert state.validation[0]["outputs"]["final_energy"] == -123.456
    assert state.validation[0]["outputs"]["raw_status"] == "converged"
    assert state.validation[0]["outputs"]["has_final_energy"] is True
    assert state.validation[0]["outputs"]["has_optimized_structure"] is True
    assert state.validation[0]["outputs"]["groundState.solvation_energy"] == -0.42
    assert state.validation[0]["outputs"]["groundState.homo"] == -5.67
    assert state.validation[0]["outputs"]["groundState.lumo"] == -1.23
    assert state.validation[0]["outputs"]["groundState.homo_lumo_gap"] == 4.44
    assert state.validation[0]["outputs"]["groundState.dipole_moment"] == 2.78
    assert state.validation[0]["outputs"]["has_groundState.solvation_energy"] is True
    assert state.validation[0]["outputs"]["has_groundState.homo"] is True
    assert state.validation[0]["outputs"]["has_groundState.lumo"] is True
    assert state.validation[0]["outputs"]["has_groundState.homo_lumo_gap"] is True
    assert state.validation[0]["outputs"]["has_groundState.dipole_moment"] is True
    assert state.validation[0]["operation"]["contract_version"] == "orca_slurm.request_response.v1"
    assert state.validation[0]["operation"]["response_type"] == "result_envelope"
    assert state.validation[0]["operation"]["status_query"]["check_only"] is True
    assert state.validation[0]["predicted_reference"]["predicted_solubility"] is not None
    assert state.validation[0]["predicted_reference"]["predicted_synthesizability"] is not None
    assert "final_energy_minus_predicted_priority" in state.validation[0]["comparison"]
    assert "final_energy_minus_predicted_priority_literature_adjusted" in state.validation[0]["comparison"]
    assert state.validation[0]["comparison"]["optimized_structure_available"] is True
    assert state.validation[0]["quality_assessment"]["quality"] == "usable"
    assert state.validation[0]["quality_assessment"]["requested_outputs_complete"] is True
    assert state.validation[0]["quality_assessment"]["missing_requested_outputs"] == []
    assert state.validation[0]["quality_assessment"]["available_outputs"]["groundState.solvation_energy"] is True
    assert state.validation[0]["quality_assessment"]["available_outputs"]["groundState.homo"] is True
    assert state.validation[0]["quality_assessment"]["available_outputs"]["groundState.lumo"] is True
    assert state.validation[0]["quality_assessment"]["available_outputs"]["groundState.homo_lumo_gap"] is True
    assert state.validation[0]["quality_assessment"]["available_outputs"]["groundState.dipole_moment"] is True
    assert state.validation[0]["provenance"]["remote_target"] == "cluster-alpha"
    assert state.validation[0]["provenance"]["raw_status"] == "converged"

    validation_results = json.loads((run_dir / "validation_results.json").read_text())
    assert validation_results[0]["candidate_id"] == "rec_a"
    assert validation_results[0]["operation"]["response_type"] == "result_envelope"
    assert validation_results[0]["submission_id"] == "contract-submit-001"
    assert validation_results[0]["outputs"]["has_optimized_structure"] is True

    report = json.loads((run_dir / "report.json").read_text())
    assert report["summary"]["validation_count"] == 1
    assert report["summary"]["usable_validation_count"] == 1
    assert report["summary"]["partial_validation_count"] == 0
    assert report["summary"]["failed_validation_count"] == 0
    assert report["validation_results"][0]["candidate_id"] == "rec_a"
    assert report["validation_results"][0]["comparison"]["optimized_structure_available"] is True
    assert report["validation_results"][0]["quality_assessment"]["quality"] == "usable"
    assert report["artifacts"]["validation_results_path"].endswith("validation_results.json")

    graph = json.loads(state.knowledge_graph_path.read_text())
    assert any(node["type"] == "SimulationResult" and node["attrs"].get("status") == "completed" for node in graph.get("nodes", []))
    assert any(node["type"] == "ValidationOutcome" and node["attrs"].get("status") == "completed" for node in graph.get("nodes", []))
