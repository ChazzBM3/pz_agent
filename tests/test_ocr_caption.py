from __future__ import annotations

from pz_agent.retrieval.ocr_caption import assemble_ocr_caption_for_candidate, build_ocr_caption_stub



def test_build_ocr_caption_stub_infers_pending_fields() -> None:
    figure = {"figure_id": "f1", "source_document_path": "paper.pdf", "caption": None}
    result = build_ocr_caption_stub(figure)
    assert result["caption_text"] == "Caption extraction pending"
    assert result["ocr_status"] == "pending"
    assert "OCR extraction pending" in result["ocr_text"]



def test_assemble_ocr_caption_for_candidate_collects_entries(tmp_path) -> None:
    bundle = {"candidate_id": "cand_1", "figures": [{"figure_id": "f1", "source_document_path": "paper.pdf", "caption": "Fig. 1"}]}
    result = assemble_ocr_caption_for_candidate(bundle, tmp_path)
    assert result["status"] == "ok"
    assert result["entry_count"] == 1
    assert result["entries"][0]["figure_id"] == "f1"
