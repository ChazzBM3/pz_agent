from __future__ import annotations

import json
from pathlib import Path

from pz_agent.runner import run_pipeline


CSV_TEXT = """_id,smiles,source_group,sa_score,oxidation_potential,reduction_potential,groundState.solvation_energy,hole_reorganization_energy,electron_reorganization_energy\nrec_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.2,1.4,0.7,-0.8,0.2,0.3\nrec_b,CCN1c2ccccc2Sc2ccccc21,demo,2.1,0.4,0.2,0.1,1.1,1.2\nother,c1ccccc1,demo,1.0,2.0,1.5,-0.1,0.1,0.1\n"""


def test_d3tales_demo_pipeline_exercises_measurement_aware_reranking(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "demo.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")

    monkeypatch.setattr(
        "pz_agent.agents.structure_expansion.expand_structure_with_pubchem",
        lambda candidate, similarity_threshold=90, similarity_max_records=5, substructure_max_records=5, timeout=20: {
            "query_smiles": candidate.get("smiles"),
            "synonyms": ["DemoSynonym"],
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

    config_path = tmp_path / "demo.yaml"
    config_path.write_text(
        f"""
project:
  name: demo
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: test demo
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
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=tmp_path / "run")

    assert state.library_raw is not None
    assert len(state.library_raw) == 2
    assert [item["id"] for item in state.library_raw] == ["rec_a", "rec_b"]
    assert all("proposal_prior" in item for item in state.library_raw)
    assert all("prior_source" in item["proposal_prior"] for item in state.library_raw)
    assert state.structure_expansion is not None
    assert state.patent_registry is not None
    assert state.scholarly_registry is not None
    assert state.ranked is not None
    assert state.ranked[0]["id"] == "rec_a"
    assert state.ranked[0]["predicted_priority_literature_adjusted"] > state.ranked[1]["predicted_priority_literature_adjusted"]
    assert "measurement_values" in state.ranked[0]["ranking_rationale"]
    assert state.critique_notes is not None
    top_note = next(note for note in state.critique_notes if note["candidate_id"] == "rec_a")
    assert top_note["signals"]["exact_match_hits"] >= 1
    assert top_note["signals"]["patent_hit_count"] >= 1
    assert top_note["signals"]["scholarly_hit_count"] >= 1
    assert state.knowledge_graph_path is not None
    graph = __import__('json').loads(state.knowledge_graph_path.read_text())
    assert any(node["type"] == "SimulationResult" for node in graph.get("nodes", []))
    assert any(node["type"] == "ValidationOutcome" for node in graph.get("nodes", []))
    assert any(node["type"] == "EvidenceHit" for node in graph.get("nodes", []))
    assert any(node["type"] == "MolecularRepresentation" for node in graph.get("nodes", []))
    assert any(node["id"] == "dataset::d3tales" for node in graph.get("nodes", []))
    assert any(node["id"] == "dataset_record::d3tales::rec_a" for node in graph.get("nodes", []))
    assert any(edge["source"] == "rec_a" and edge["target"] == "dataset_record::d3tales::rec_a" and edge["type"] == "DERIVED_FROM" for edge in graph.get("edges", []))
    assert any(edge["source"] == "rec_a" and edge["type"] == "HAS_REPRESENTATION" for edge in graph.get("edges", []))
    rec_a_identity_target = next(edge["target"] for edge in graph.get("edges", []) if edge["source"] == "rec_a" and edge["type"] == "HAS_REPRESENTATION")
    assert any(edge["type"] == "EXACT_MATCH_OF" for edge in graph.get("edges", []))
    assert any(edge["target"] == rec_a_identity_target and edge["type"] in {"EXACT_MATCH_OF", "ANALOG_OF"} for edge in graph.get("edges", []))
    assert any(edge["target"] == rec_a_identity_target and edge["type"] == "ABOUT_REPRESENTATION" for edge in graph.get("edges", []))
    report = __import__('json').loads((tmp_path / 'run' / 'report.json').read_text())
    assert "graph_metrics" in report
    assert "expansion_proposals" in report
    assert "action_queue" in report
    assert "action_outcomes" in report
    assert "outcome_stats" in report
    assert "summary" in report
    assert "decision_summary" in report
    assert "artifacts" in report
    assert report["summary"]["top_candidate_id"] == "rec_a"
    assert report["summary"]["shortlist_count"] == 2
    assert report["decision_summary"][0]["candidate_id"] == "rec_a"
    assert "simulation_manifest" in report
    assert "simulation_queue" in report
    assert "simulation_submissions" in report
    assert (tmp_path / 'run' / 'expansion_proposals.json').exists()
    assert (tmp_path / 'run' / 'expansion_proposals.accepted.json').exists()
    assert (tmp_path / 'run' / 'expansion_proposals.rejected.json').exists()
    assert (tmp_path / 'run' / 'action_queue.json').exists()
    assert (tmp_path / 'run' / 'action_outcomes.json').exists()
    assert (tmp_path / 'run' / 'outcome_stats.json').exists()
    assert report["summary"]["queued_evidence_query_count"] >= 0
    assert report["artifacts"]["simulation_manifest_path"].endswith("simulation_manifest.json")
    assert report["artifacts"]["simulation_submissions_path"].endswith("simulation_submissions.json")
    assert state.simulation_queue is not None
    assert state.simulation_manifest is not None
    assert state.simulation_submissions is not None
    assert state.simulation_manifest["queue_size"] == len(state.simulation_queue)
    assert state.simulation_queue[0]["candidate_id"] == "rec_a"
    assert state.simulation_queue[0]["status"] == "submitted"
    assert state.simulation_submissions[0]["status"] == "submitted"
    assert "stable_identity_key" in state.simulation_queue[0]
    assert (tmp_path / 'run' / 'simulation_queue.json').exists()
    assert (tmp_path / 'run' / 'simulation_manifest.json').exists()
    assert (tmp_path / 'run' / 'simulation_submissions.json').exists()


def test_d3tales_demo_pipeline_with_validation_ingest_exercises_end_to_end_loop(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "demo_validation.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")

    monkeypatch.setattr(
        "pz_agent.agents.structure_expansion.expand_structure_with_pubchem",
        lambda candidate, similarity_threshold=90, similarity_max_records=5, substructure_max_records=5, timeout=20: {
            "query_smiles": candidate.get("smiles"),
            "synonyms": ["DemoSynonym"],
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

    run_dir = tmp_path / "run_validation"
    (run_dir / "remote_results.json").parent.mkdir(parents=True, exist_ok=True)
    (run_dir / "remote_results.json").write_text(
        json.dumps([
            {
                "candidate_id": "rec_a",
                "submission_id": "demo-submit-001",
                "status": "completed",
                "backend": "atomisticskills_orca",
                "engine": "orca",
                "simulation_type": "geometry_optimization",
                "remote_target": "cluster-demo",
                "outputs": {
                    "final_energy": -100.5,
                    "optimized_structure": "rec_a_optimized.xyz",
                    "status": "converged",
                },
            }
        ]),
        encoding="utf-8",
    )

    config_path = tmp_path / "demo_validation.yaml"
    config_path.write_text(
        f"""
project:
  name: demo-validation
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: demo validation loop
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
  remote_target: cluster-demo
simulation_submit:
  submission_prefix: demo-submit
validation_ingest:
  results_path: remote_results.json
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=run_dir)

    assert state.validation is not None
    assert len(state.validation) == 1
    assert state.validation[0]["candidate_id"] == "rec_a"
    assert state.validation[0]["outputs"]["raw_status"] == "converged"
    assert (run_dir / "validation_results.json").exists()

    report = json.loads((run_dir / "report.json").read_text())
    assert report["summary"]["validation_count"] == 1
    assert report["validation_results"][0]["candidate_id"] == "rec_a"
    assert report["artifacts"]["validation_results_path"].endswith("validation_results.json")

    graph = json.loads(state.knowledge_graph_path.read_text())
    assert any(node["type"] == "SimulationResult" and node["attrs"].get("status") == "completed" for node in graph.get("nodes", []))
    assert any(node["type"] == "ValidationOutcome" and node["attrs"].get("status") == "completed" for node in graph.get("nodes", []))


def test_d3tales_demo_pipeline_loads_prior_action_queue(tmp_path: Path) -> None:
    csv_path = tmp_path / "demo.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    prior_queue_path = tmp_path / "prior_action_queue.json"
    prior_queue_path.write_text(
        json.dumps([
            {
                "candidate_id": "rec_a",
                "priority": 0.7,
                "source": "graph_expansion",
                "proposal_type": "evidence_query_candidate",
                "critic_reason": "seeded_for_test",
                "action_type": "evidence_query",
                "payload": {"belief_status": "proposed", "confidence": 0.42},
            }
        ]),
        encoding="utf-8",
    )
    outcome_stats_path = tmp_path / "outcome_stats.json"
    outcome_stats_path.write_text(json.dumps({"decay": 0.85, "by_proposal_type": {"evidence_query_candidate": {"success": 3, "failure": 0}}, "by_proposal_reason": {"low_confidence_belief_expand": {"success": 2, "failure": 0}}}), encoding="utf-8")

    config_path = tmp_path / "demo_prior.yaml"
    config_path.write_text(
        f"""
project:
  name: demo
generation:
  engine: d3tales_csv
  d3tales_csv_path: {csv_path}
  d3tales_limit: 2
  d3tales_phenothiazine_only: true
  prompts:
    objective: test demo
screening:
  shortlist_size: 2
pipeline:
  prior_action_queue_path: {prior_queue_path}
  outcome_stats_path: {outcome_stats_path}
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
  enable_web_search: false
  max_candidates: 2
  search_fields:
    - oxidation_potential
    - solvation_energy
search:
  backend: stub
""",
        encoding="utf-8",
    )

    run_pipeline(config_path, run_dir=tmp_path / "run_prior")
    critique_notes = json.loads((tmp_path / "run_prior" / "critique_notes.json").read_text())
    action_outcomes = json.loads((tmp_path / "run_prior" / "action_outcomes.json").read_text())
    stats = json.loads((tmp_path / "run_prior" / "outcome_stats.json").read_text())
    assert any(note.get("action_queue_hints") for note in critique_notes)
    assert any(item.get("action_type") == "evidence_query" for item in action_outcomes)
    assert "by_proposal_type" in stats
    assert stats["by_proposal_type"].get("evidence_query_candidate") is not None
    assert stats["by_proposal_reason"].get("low_confidence_belief_expand") is not None
    assert float(stats.get("decay", 0.0)) > 0.0
