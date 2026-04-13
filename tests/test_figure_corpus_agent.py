from __future__ import annotations

from pathlib import Path

from pz_agent.agents.figure_corpus import FigureCorpusAgent
from pz_agent.state import RunState



def test_figure_corpus_agent_writes_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.figure_corpus.assemble_figure_corpus_for_candidate",
        lambda document_bundle, artifacts_dir: {"candidate_id": document_bundle.get("candidate_id"), "figure_count": 1, "figures": [{"figure_id": "f1"}], "status": "ok"},
    )

    state = RunState(
        config={"figure_corpus": {"enabled": True, "artifacts_dir": str(tmp_path / 'figs')}},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "document_fetch": {}}],
    )
    state.document_registry = [{"candidate_id": "cand_1", "documents": []}]
    updated = FigureCorpusAgent(config=state.config).run(state)

    assert updated.figure_registry is not None
    assert updated.figure_registry[0]["candidate_id"] == "cand_1"
    assert updated.library_clean[0]["figure_corpus"]["status"] == "ok"
    assert (tmp_path / "figure_corpus.json").exists()
