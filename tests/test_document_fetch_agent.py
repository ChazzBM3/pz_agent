from __future__ import annotations

from pathlib import Path

from pz_agent.agents.document_fetch import DocumentFetchAgent
from pz_agent.state import RunState



def test_document_fetch_agent_writes_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.document_fetch.assemble_document_artifacts_for_candidate",
        lambda page_bundle, artifacts_dir: {"candidate_id": page_bundle.get("candidate_id"), "document_count": 1, "documents": [{"title": "Doc"}], "status": "ok"},
    )

    state = RunState(
        config={"document_fetch": {"enabled": True, "artifacts_dir": str(tmp_path / 'assets')}},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "page_corpus": {}}],
    )
    state.page_registry = [{"candidate_id": "cand_1", "pages": []}]
    updated = DocumentFetchAgent(config=state.config).run(state)

    assert updated.document_registry is not None
    assert updated.document_registry[0]["candidate_id"] == "cand_1"
    assert updated.library_clean[0]["document_fetch"]["status"] == "ok"
    assert (tmp_path / "document_fetch.json").exists()
