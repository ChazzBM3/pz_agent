from __future__ import annotations

import json
from pathlib import Path

from pz_agent.runner import run_pipeline


CSV_TEXT = """_id,smiles,source_group,sa_score,oxidation_potential,reduction_potential,groundState.solvation_energy,hole_reorganization_energy,electron_reorganization_energy\nrec_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.2,1.4,0.7,-0.8,0.2,0.3\nrec_b,CCN1c2ccccc2Sc2ccccc21,demo,2.1,0.4,0.2,0.1,1.1,1.2\nother,c1ccccc1,demo,1.0,2.0,1.5,-0.1,0.1,0.1\n"""



def test_small_fixed_pilot_fixture_run(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "pilot.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")

    monkeypatch.setattr(
        "pz_agent.agents.structure_expansion.expand_structure_with_pubchem",
        lambda candidate, similarity_threshold=90, similarity_max_records=5, substructure_max_records=5, timeout=20: {
            "query_smiles": candidate.get("smiles"),
            "synonyms": ["PilotSynonym"],
            "exact_matches": [{"cid": 1, "title": "Exact PT hit", "molecular_formula": "C12H9NS2", "pubchem_url": "https://pubchem.ncbi.nlm.nih.gov/compound/1"}],
            "similarity_matches": [{"cid": 2, "title": "Analog PT hit", "molecular_formula": "C13H11NS2", "pubchem_url": "https://pubchem.ncbi.nlm.nih.gov/compound/2"}],
            "substructure_matches": [],
            "status": "ok",
        },
    )
    monkeypatch.setattr(
        "pz_agent.agents.patent_retrieval.retrieve_patent_evidence_for_candidate",
        lambda candidate, count=5, timeout=20: {
            "queries": [f"{candidate.get('id')} patent"],
            "surechembl": [{"query": "pt patent", "hits": [{"title": "Phenothiazine patent", "url": "https://example.com/patent", "snippet": "battery electrolyte phenothiazine", "match_type": "analog", "confidence": 0.7}]}],
            "patcid": [],
            "errors": [],
            "status": "ok",
        },
    )
    monkeypatch.setattr(
        "pz_agent.agents.scholarly_retrieval.retrieve_openalex_evidence_for_candidate",
        lambda candidate, count=5, mode="balanced", max_queries=6, exact_query_budget=None, analog_query_budget=None, exploratory_query_budget=None: {
            "queries": [f"{candidate.get('id')} chemistry"],
            "openalex": [{"query": "pt chemistry", "hits": [{"title": "Phenothiazine electrochemistry", "url": "https://example.com/paper", "snippet": "oxidation potential and solubility", "match_type": "analog", "confidence": 0.8}]}],
            "errors": [],
            "status": "ok",
        },
    )

    config_path = tmp_path / "pilot.yaml"
    config_path.write_text(
        f"""
project:
  name: pseudo-production-pilot
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: fixed pilot fixture run
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
    - reporter
kg:
  backend: json
  path: artifacts/knowledge_graph.json
critique:
  enable_web_search: true
  max_candidates: 2
  search_fields:
    - oxidation_potential
    - solvation_energy
search:
  backend: stub
simulation:
  max_candidates: 2
  simulation_type: geometry_optimization
  compute_tier: pilot
  budget_tag: fixed_fixture
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=tmp_path / "run")

    assert state.ranked is not None
    assert [item["id"] for item in state.ranked[:2]] == ["rec_a", "rec_b"]
    assert state.simulation_manifest is not None
    assert state.simulation_manifest["queue_size"] == 2
    assert state.simulation_manifest["simulation_defaults"]["compute_tier"] == "pilot"
    assert state.simulation_manifest["queue"][0]["candidate_id"] == "rec_a"
    assert state.simulation_manifest["queue"][0]["simulation"]["simulation_type"] == "geometry_optimization"
    assert state.simulation_manifest["queue"][0]["simulation"]["budget_tag"] == "fixed_fixture"
    assert state.simulation_manifest["simulation_defaults"]["backend"] == "atomisticskills_orca"
    assert state.simulation_manifest["simulation_defaults"]["execution_mode"] == "remote"
    assert state.simulation_manifest["simulation_defaults"]["skill"] == "chem-dft-orca-optimization"
    assert state.simulation_manifest["queue"][0]["simulation"]["parameters"]["opt_type"] == "min"
    assert state.simulation_manifest["queue"][0]["job_package"]["job_spec_path"].endswith("orca_job.json")

    job_spec = json.loads((tmp_path / "run" / "orca_jobs" / "rec_a" / "orca_job.json").read_text())
    assert job_spec["candidate_id"] == "rec_a"
    assert job_spec["simulation_type"] == "geometry_optimization"
    assert job_spec["orca_skill"] == "chem-dft-orca-optimization"
    assert job_spec["structure_file"] == "input_structure.xyz"
    assert job_spec["parameters"]["opt_type"] == "min"
    assert job_spec["parameters"]["functional"] == "PBE"
    assert job_spec["parameters"]["basis_set"] == "def2-SVP"
    assert job_spec["provenance"]["remote_backend"] == "atomisticskills_orca"

    structure_stub = (tmp_path / "run" / "orca_jobs" / "rec_a" / "input_structure.xyz").read_text()
    assert "rec_a" in structure_stub
    submissions = json.loads((tmp_path / "run" / "simulation_submissions.json").read_text())
    assert len(submissions) == 2
    assert submissions[0]["status"] == "submitted"
    assert submissions[0]["job_spec_path"].endswith("orca_job.json")

    graph = json.loads(state.knowledge_graph_path.read_text())
    assert any(node["id"] == "dataset_record::d3tales::rec_a" for node in graph.get("nodes", []))
    assert any(node["type"] == "MolecularRepresentation" for node in graph.get("nodes", []))
    assert any(edge["type"] == "ABOUT_REPRESENTATION" for edge in graph.get("edges", []))

    report = json.loads((tmp_path / "run" / "report.json").read_text())
    assert report["summary"]["top_candidate_id"] == "rec_a"
    assert report["summary"]["simulation_queue_count"] == 2
    assert report["summary"]["simulation_submission_count"] == 2
    assert len(report["decision_summary"]) == 2
    assert report["decision_summary"][0]["candidate_id"] == "rec_a"
    assert report["decision_summary"][0]["queue_status"] == "submitted"
    assert report["decision_summary"][0]["submission_id"].startswith("stub-submit-")
    assert report["artifacts"]["simulation_queue_path"].endswith("simulation_queue.json")
    assert report["artifacts"]["simulation_manifest_path"].endswith("simulation_manifest.json")
    assert report["artifacts"]["simulation_submissions_path"].endswith("simulation_submissions.json")
