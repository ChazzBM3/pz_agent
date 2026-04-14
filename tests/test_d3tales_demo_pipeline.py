from __future__ import annotations

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
    assert state.ranked is not None
    assert state.ranked[0]["id"] == "rec_a"
    assert state.ranked[0]["predicted_priority_literature_adjusted"] > state.ranked[1]["predicted_priority_literature_adjusted"]
    assert "measurement_values" in state.ranked[0]["ranking_rationale"]
    assert state.knowledge_graph_path is not None
    graph = __import__('json').loads(state.knowledge_graph_path.read_text())
    assert any(node["type"] == "SimulationResult" for node in graph.get("nodes", []))
    assert any(node["type"] == "ValidationOutcome" for node in graph.get("nodes", []))
