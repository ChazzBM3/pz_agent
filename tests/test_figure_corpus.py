from __future__ import annotations

from pathlib import Path

from pz_agent.retrieval.figure_corpus import assemble_figure_corpus_for_candidate, infer_figure_candidates



def test_infer_figure_candidates_uses_pdf_and_figure_hints(tmp_path: Path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 mock")
    document = {
        "candidate_id": "cand_1",
        "document_kind": "pdf",
        "fetch_status": "fetched",
        "title": "Figure-rich phenothiazine study",
        "snippet": "Figure 2 shows electrochemistry",
        "trusted_host": True,
        "local_artifact_path": str(pdf_path),
        "metadata_path": str(tmp_path / "doc.json"),
        "url": "https://doi.org/10.1000/example",
    }
    figures = infer_figure_candidates(document)
    assert len(figures) >= 1
    assert figures[0]["crop_status"] == "pending"



def test_assemble_figure_corpus_for_candidate_builds_storage_refs(tmp_path: Path) -> None:
    html_path = tmp_path / "doc.html"
    html_path.write_text("<html><body><img src='fig1.png'/><figure>Scheme 1</figure></body></html>", encoding="utf-8")
    bundle = {
        "candidate_id": "cand_1",
        "documents": [
            {
                "candidate_id": "cand_1",
                "document_kind": "html",
                "fetch_status": "fetched",
                "title": "Paper",
                "snippet": "Figure 1",
                "trusted_host": True,
                "local_artifact_path": str(html_path),
                "metadata_path": str(tmp_path / "doc.json"),
                "url": "https://doi.org/10.1000/example",
            }
        ],
    }
    result = assemble_figure_corpus_for_candidate(bundle, tmp_path)
    assert result["status"] == "ok"
    assert result["figure_count"] >= 1
    assert result["figures"][0]["storage_ref"].endswith(".png")
    assert result["figures"][0]["crop_status"] == "extracted"
    assert Path(result["figures"][0]["storage_ref"]).exists()
