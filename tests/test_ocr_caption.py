from __future__ import annotations

from pathlib import Path

from pz_agent.retrieval.ocr_caption import assemble_ocr_caption_for_candidate, build_ocr_caption_stub



def test_build_ocr_caption_stub_extracts_clean_caption_from_html_and_asset(tmp_path: Path) -> None:
    html_path = tmp_path / "paper.html"
    html_path.write_text(
        "<html><body><div>noise</div><figure><b>Figure 2.</b> Phenothiazine redox series for compound 7</figure></body></html>",
        encoding="utf-8",
    )
    asset_path = tmp_path / "figure_phenothiazine.png"
    asset_path.write_bytes(b"png")

    figure = {"figure_id": "f1", "source_document_path": str(html_path), "storage_ref": str(asset_path), "caption": None}
    result = build_ocr_caption_stub(figure)
    assert "Figure 2." in result["caption_text"]
    assert "Phenothiazine redox series" in result["caption_text"]
    assert "<figure>" not in result["caption_text"]
    assert result["caption_status"] == "ok"
    assert result["ocr_status"] == "ok"



def test_build_ocr_caption_stub_prefers_richer_caption_candidate(tmp_path: Path) -> None:
    html_path = tmp_path / "paper.html"
    html_path.write_text(
        "<html><body><p>Figure 1. Generic plot</p><p>Scheme 2. Phenothiazine compound redox cycle</p></body></html>",
        encoding="utf-8",
    )
    asset_path = tmp_path / "figure_asset.png"
    asset_path.write_bytes(b"png")
    figure = {"figure_id": "f1", "source_document_path": str(html_path), "storage_ref": str(asset_path), "caption": None}
    result = build_ocr_caption_stub(figure)
    assert "Phenothiazine compound redox cycle" in result["caption_text"]



def test_assemble_ocr_caption_for_candidate_collects_entries(tmp_path: Path) -> None:
    html_path = tmp_path / "paper.html"
    html_path.write_text("<html><body><figure>Scheme 1. Caption</figure></body></html>", encoding="utf-8")
    asset_path = tmp_path / "figure_asset.png"
    asset_path.write_bytes(b"png")
    bundle = {"candidate_id": "cand_1", "figures": [{"figure_id": "f1", "source_document_path": str(html_path), "storage_ref": str(asset_path), "caption": None}]}
    result = assemble_ocr_caption_for_candidate(bundle, tmp_path)
    assert result["status"] == "ok"
    assert result["entry_count"] == 1
    assert result["entries"][0]["figure_id"] == "f1"
    assert result["entries"][0]["caption_status"] == "ok"
