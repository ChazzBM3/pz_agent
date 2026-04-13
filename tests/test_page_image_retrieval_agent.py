from __future__ import annotations

from pathlib import Path

from pz_agent.agents.page_image_retrieval import PageImageRetrievalAgent
from pz_agent.state import RunState



def test_page_image_retrieval_agent_writes_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.page_image_retrieval.assemble_page_image_retrieval_for_candidate",
        lambda candidate, artifacts_dir: {"candidate_id": candidate.get("id"), "target_count": 1, "targets": [{"figure_id": "f1"}], "backend": "colpali_planned", "status": "ok"},
    )

    state = RunState(
        config={"page_image_retrieval": {"enabled": True, "artifacts_dir": str(tmp_path / 'pir')}},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "figure_corpus": {"figures": []}}],
    )
    updated = PageImageRetrievalAgent(config=state.config).run(state)

    assert updated.page_image_registry is not None
    assert updated.page_image_registry[0]["candidate_id"] == "cand_1"
    assert updated.library_clean[0]["page_image_retrieval"]["status"] == "ok"
    assert (tmp_path / "page_image_retrieval.json").exists()
