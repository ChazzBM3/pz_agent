from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique import CritiqueAgent
from pz_agent.kg.builder import build_graph_snapshot
from pz_agent.state import RunState



def test_macro_critique_agent_populates_belief_lifecycle_and_bridge_registry(monkeypatch, tmp_path: Path) -> None:
    for target in [
        "PatentRetrievalAgent.run",
        "ScholarlyRetrievalAgent.run",
        "PageCorpusAgent.run",
        "DocumentFetchAgent.run",
        "FigureCorpusAgent.run",
        "OCRCaptionAgent.run",
        "PageImageRetrievalAgent.run",
        "MultimodalRerankAgent.run",
    ]:
        monkeypatch.setattr(f"pz_agent.agents.critique.{target}", lambda self, state: state)

    monkeypatch.setattr(
        "pz_agent.agents.critique.attach_critique_placeholders",
        lambda shortlist, enable_web_search, max_candidates, search_fields, graph_path: [{"candidate_id": "cand_1", "signals": {}, "queries": []}],
    )
    monkeypatch.setattr(
        "pz_agent.agents.critique.synthesize_evidence_from_queries",
        lambda notes: [{**notes[0], "signals": {"support_score": 0.4, "contradiction_score": 0.1}, "evidence": []}],
    )

    state = RunState(config={"critique": {"enable_web_search": False}}, run_dir=tmp_path, shortlist=[{"id": "cand_1"}], multimodal_registry=[])
    updated = CritiqueAgent(config=state.config).run(state)
    assert updated.belief_registry is not None
    assert updated.bridge_registry is not None
    assert updated.belief_registry[0]["status"] in {"open", "testing", "supported", "contradicted"}
    assert updated.bridge_registry[0]["source_family"] == "chem_qn::quinone_abstract"



def test_graph_snapshot_includes_bridge_nodes(tmp_path: Path) -> None:
    state = RunState(
        config={},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1"}],
        bridge_registry=[{"candidate_id": "cand_1", "source_family": "chem_qn::quinone_abstract", "target_family": "chem_pt::phenothiazine", "transfer_reason": "analogy_seed", "status": "proposed"}],
    )
    graph = build_graph_snapshot(state)
    node_ids = {node["id"] for node in graph["nodes"]}
    assert any(node_id.startswith("bridge::cand_1::") for node_id in node_ids)
