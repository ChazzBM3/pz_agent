from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique_reranker import CritiqueRerankerAgent
from pz_agent.io import write_json
from pz_agent.kg.rag import summarize_support_contradiction
from pz_agent.state import RunState



def test_summarize_support_contradiction_counts_patent_and_scholarly_hits(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    write_json(
        graph_path,
        {
            "nodes": [
                {"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1"}},
                {
                    "id": "e1",
                    "type": "EvidenceHit",
                    "attrs": {
                        "match_type": "analog",
                        "provenance": {"source_type": "surechembl", "evidence_level": "patent_retrieval"},
                    },
                },
                {
                    "id": "e2",
                    "type": "EvidenceHit",
                    "attrs": {
                        "match_type": "unknown",
                        "provenance": {"source_type": "openalex", "evidence_level": "scholarly_retrieval"},
                    },
                },
            ],
            "edges": [
                {"source": "e1", "target": "cand_1", "type": "ANALOG_OF"},
                {"source": "e2", "target": "cand_1", "type": "ABOUT_MOLECULE"},
            ],
        },
    )

    summary = summarize_support_contradiction(graph_path, "cand_1")
    assert summary["analog_match_hits"] >= 1
    assert summary["patent_hit_count"] >= 1
    assert summary["scholarly_hit_count"] >= 1



def test_critique_reranker_preserves_patent_and_scholarly_counts(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    write_json(
        graph_path,
        {
            "nodes": [
                {"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1"}},
                {
                    "id": "claim::cand_1",
                    "type": "Claim",
                    "attrs": {
                        "summary": "Support for cand_1.",
                        "signals": {
                            "exact_match_hits": 1,
                            "analog_match_hits": 2,
                            "patent_hit_count": 3,
                            "scholarly_hit_count": 4,
                            "support_score": 5.0,
                            "contradiction_score": 0.0,
                        },
                    },
                },
            ],
            "edges": [
                {"source": "claim::cand_1", "target": "cand_1", "type": "ABOUT_MOLECULE"},
            ],
        },
    )

    state = RunState(config={"screening": {"shortlist_size": 3}}, run_dir=tmp_path)
    state.knowledge_graph_path = graph_path
    state.ranked = [{"id": "cand_1", "predicted_priority": 0.5, "identity": {}}]
    state.critique_notes = [{"candidate_id": "cand_1", "signals": {"exact_match_hits": 0, "analog_match_hits": 0, "patent_hit_count": 0, "scholarly_hit_count": 0, "support_score": 0.0, "contradiction_score": 0.0}}]

    updated = CritiqueRerankerAgent(config=state.config).run(state)
    note = updated.ranked[0]["ranking_rationale"]["kg_summary"]
    assert note["patent_hit_count"] >= 3
    assert note["scholarly_hit_count"] >= 4
    assert updated.ranked[0]["predicted_priority_literature_adjusted"] > 0.5
