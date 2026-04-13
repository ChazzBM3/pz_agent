from __future__ import annotations

from pathlib import Path

from pz_agent.agents.multimodal_rerank import MultimodalRerankAgent
from pz_agent.state import RunState



def test_multimodal_rerank_agent_writes_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.multimodal_rerank.assemble_multimodal_rerank_for_candidate",
        lambda candidate: {"candidate_id": candidate.get("id"), "bundle_count": 1, "bundles": [{"bundle_id": "b1"}], "backend": "gemma_planned", "status": "ok"},
    )

    state = RunState(
        config={"multimodal_rerank": {"enabled": True}},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "page_image_retrieval": {"targets": []}, "document_fetch": {"documents": []}, "identity": {}}],
    )
    updated = MultimodalRerankAgent(config=state.config).run(state)

    assert updated.multimodal_registry is not None
    assert updated.multimodal_registry[0]["candidate_id"] == "cand_1"
    assert updated.library_clean[0]["multimodal_rerank"]["status"] == "ok"
    assert (tmp_path / "multimodal_rerank.json").exists()
