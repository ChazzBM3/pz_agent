from __future__ import annotations

import json
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
  remote_target: cluster-alpha
simulation_submit:
  submission_prefix: contract-submit
""",
        encoding="utf-8",
    )

    run_dir = tmp_path / "run"
    run_pipeline(config_path, run_dir=run_dir)
    return run_dir


def test_simulation_manifest_declares_current_default_contract(tmp_path: Path, monkeypatch) -> None:
    run_dir = _run_contract_fixture(tmp_path, monkeypatch)
    manifest = json.loads((run_dir / "simulation_manifest.json").read_text())

    defaults = manifest["simulation_defaults"]
    params = defaults["parameters"]

    assert manifest["contract_version"] == "atomisticskills.request_response.v1"
    assert defaults["simulation_type"] == "geometry_optimization"
    assert defaults["backend"] == "atomisticskills_orca"
    assert defaults["engine"] == "orca"
    assert defaults["skill"] == "chem-dft-orca-optimization"
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
    assert params["functional"] == "PBE"
    assert params["basis_set"] == "def2-SVP"
    assert params["dispersion"] == "D3"
    assert params["solvation"] == "CPCM"
    assert params["solvent"] == "water"
    assert params["remote_target"] == "cluster-alpha"


def test_simulation_job_package_and_submission_records_match_contract(tmp_path: Path, monkeypatch) -> None:
    run_dir = _run_contract_fixture(tmp_path, monkeypatch)

    queue = json.loads((run_dir / "simulation_queue.json").read_text())
    submissions = json.loads((run_dir / "simulation_submissions.json").read_text())
    checks = json.loads((run_dir / "simulation_checks.json").read_text())
    job_spec = json.loads((run_dir / "orca_jobs" / "rec_a" / "orca_job.json").read_text())

    assert queue[0]["simulation"]["parameters"]["dispersion"] == "D3"
    assert queue[0]["simulation"]["parameters"]["solvation"] == "CPCM"
    assert queue[0]["simulation"]["parameters"]["solvent"] == "water"
    assert queue[0]["simulation"]["parameters"]["remote_target"] == "cluster-alpha"

    assert job_spec["contract_version"] == "atomisticskills.request_response.v1"
    assert job_spec["request_type"] == "submit_simulation"
    assert job_spec["operation"]["check_only"] is False
    assert job_spec["parameters"]["dispersion"] == "D3"
    assert job_spec["parameters"]["solvation"] == "CPCM"
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

    assert submissions[0]["response_type"] == "submission_ack"
    assert submissions[0]["status_query"]["check_only"] is True
    assert submissions[0]["status"] == "submitted"
    assert checks[0]["request_type"] == "check_simulation"
    assert checks[0]["response_type"] == "status_envelope"
    assert checks[0]["check_only"] is True
    assert submissions[0]["backend"] == "atomisticskills_orca"
    assert submissions[0]["remote_target"] == "cluster-alpha"
    assert submissions[0]["submission_id"].startswith("contract-submit-")
