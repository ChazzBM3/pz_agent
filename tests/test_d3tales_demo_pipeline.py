from __future__ import annotations

import json
from pathlib import Path

from pz_agent.runner import run_pipeline


CSV_TEXT = """_id,smiles,source_group,sa_score,oxidation_potential,reduction_potential,groundState.solvation_energy,hole_reorganization_energy,electron_reorganization_energy\nrec_a,c1ccc2c(c1)Sc1ccccc1S2,demo,1.2,1.4,0.7,-0.8,0.2,0.3\nrec_b,CCN1c2ccccc2Sc2ccccc21,demo,2.1,0.4,0.2,0.1,1.1,1.2\nother,c1ccccc1,demo,1.0,2.0,1.5,-0.1,0.1,0.1\n"""


def test_d3tales_demo_pipeline_exercises_measurement_aware_reranking(tmp_path: Path) -> None:
    csv_path = tmp_path / "demo.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")

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
    - surrogate_screen
    - benchmark
    - knowledge_graph
    - ranker
    - critique
    - critique_reranker
    - knowledge_graph
    - graph_expansion
    - reporter
    - dft_handoff
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
    assert state.ranked is not None
    assert state.ranked[0]["id"] == "rec_a"
    assert state.ranked[0]["predicted_priority_literature_adjusted"] > state.ranked[1]["predicted_priority_literature_adjusted"]
    assert "measurement_values" in state.ranked[0]["ranking_rationale"]
    assert state.knowledge_graph_path is not None
    graph = __import__('json').loads(state.knowledge_graph_path.read_text())
    assert any(node["type"] == "SimulationResult" for node in graph.get("nodes", []))
    assert any(node["type"] == "ValidationOutcome" for node in graph.get("nodes", []))
    report = __import__('json').loads((tmp_path / 'run' / 'report.json').read_text())
    assert "graph_metrics" in report
    assert "expansion_proposals" in report
    assert "action_queue" in report
    assert "action_outcomes" in report
    assert "outcome_stats" in report
    assert "queued_evidence_query_count" in report
    assert (tmp_path / 'run' / 'expansion_proposals.json').exists()
    assert (tmp_path / 'run' / 'expansion_proposals.accepted.json').exists()
    assert (tmp_path / 'run' / 'expansion_proposals.rejected.json').exists()
    assert (tmp_path / 'run' / 'action_queue.json').exists()
    assert (tmp_path / 'run' / 'action_outcomes.json').exists()
    assert (tmp_path / 'run' / 'outcome_stats.json').exists()
    assert report["queued_evidence_query_count"] >= 0


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
    outcome_stats_path.write_text(json.dumps({"by_proposal_type": {"evidence_query_candidate": {"success": 3, "failure": 0}}, "by_proposal_reason": {"low_confidence_belief_expand": {"success": 2, "failure": 0}}}), encoding="utf-8")

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
    - surrogate_screen
    - benchmark
    - knowledge_graph
    - ranker
    - critique
    - critique_reranker
    - knowledge_graph
    - graph_expansion
    - reporter
    - dft_handoff
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
    accepted = json.loads((tmp_path / "run_prior" / "expansion_proposals.accepted.json").read_text())
    rejected = json.loads((tmp_path / "run_prior" / "expansion_proposals.rejected.json").read_text())
    assert any(note.get("action_queue_hints") for note in critique_notes)
    assert any(item.get("action_type") == "evidence_query" for item in action_outcomes)
    assert "by_proposal_type" in stats
    evidence_item = next((item for item in accepted + rejected if item.get("proposal_type") == "evidence_query_candidate"), None)
    assert evidence_item is not None
    assert float(evidence_item["priority_bias"]["final"]) >= float(evidence_item["priority_bias"]["base"])
