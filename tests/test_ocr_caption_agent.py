from __future__ import annotations

from pathlib import Path

from pz_agent.agents.ocr_caption import OCRCaptionAgent
from pz_agent.state import RunState



def test_ocr_caption_agent_updates_figures(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.ocr_caption.assemble_ocr_caption_for_candidate",
        lambda figure_bundle, artifacts_dir: {
            "candidate_id": figure_bundle.get("candidate_id"),
            "entry_count": 1,
            "entries": [{"figure_id": "f1", "caption_text": "Fig. 1 caption", "ocr_text": "compound 7", "caption_status": "ok", "ocr_status": "ok"}],
            "status": "ok",
        },
    )

    state = RunState(
        config={"ocr_caption": {"enabled": True}},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "figure_corpus": {"figures": [{"figure_id": "f1", "caption": None}]}}],
    )
    state.figure_registry = [{"candidate_id": "cand_1", "figures": [{"figure_id": "f1", "caption": None}]}]
    updated = OCRCaptionAgent(config=state.config).run(state)

    assert updated.ocr_registry is not None
    assert updated.ocr_registry[0]["candidate_id"] == "cand_1"
    assert updated.library_clean[0]["figure_corpus"]["figures"][0]["caption"] == "Fig. 1 caption"
    assert updated.library_clean[0]["figure_corpus"]["figures"][0]["ocr_text"] == "compound 7"
    assert (tmp_path / "ocr_caption.json").exists()
