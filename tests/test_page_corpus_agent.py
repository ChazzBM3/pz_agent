from __future__ import annotations

from pathlib import Path

from pz_agent.agents.page_corpus import PageCorpusAgent
from pz_agent.state import RunState



def test_page_corpus_agent_writes_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.page_corpus.assemble_page_corpus_for_candidate",
        lambda candidate: {"candidate_id": candidate.get("id"), "page_count": 1, "pages": [{"title": "Page"}], "status": "ok"},
    )

    state = RunState(
        config={"page_corpus": {"enabled": True}},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "scholarly_retrieval": {}, "patent_retrieval": {}, "structure_expansion": {}}],
    )
    updated = PageCorpusAgent(config=state.config).run(state)

    assert updated.page_registry is not None
    assert updated.page_registry[0]["candidate_id"] == "cand_1"
    assert updated.library_clean[0]["page_corpus"]["status"] == "ok"
    assert (tmp_path / "page_corpus.json").exists()
