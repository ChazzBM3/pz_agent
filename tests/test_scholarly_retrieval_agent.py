from __future__ import annotations

from pathlib import Path

from pz_agent.agents.scholarly_retrieval import ScholarlyRetrievalAgent
from pz_agent.state import RunState



def test_scholarly_retrieval_agent_writes_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.scholarly_retrieval.retrieve_openalex_evidence_for_candidate",
        lambda candidate, count=5, mode="balanced", max_queries=6, exact_query_budget=None, analog_query_budget=None, exploratory_query_budget=None: {
            "queries": ["foo chemistry"],
            "openalex": [],
            "errors": [],
            "status": "ok",
        },
    )

    state = RunState(
        config={"scholarly_retrieval": {"enabled": True}},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "smiles": "CC", "structure_expansion": {}, "patent_retrieval": {}}],
    )
    agent = ScholarlyRetrievalAgent(config=state.config)
    updated = agent.run(state)

    assert updated.scholarly_registry is not None
    assert updated.scholarly_registry[0]["candidate_id"] == "cand_1"
    assert updated.library_clean[0]["scholarly_retrieval"]["queries"] == ["foo chemistry"]
    assert (tmp_path / "scholarly_retrieval.json").exists()
