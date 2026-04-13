from __future__ import annotations

from pathlib import Path

from pz_agent.retrieval.document_fetch import assemble_document_artifacts_for_candidate, enrich_page_record, infer_document_kind



def test_infer_document_kind_detects_pdf_and_patent() -> None:
    assert infer_document_kind("https://example.org/paper.pdf") == "pdf"
    assert infer_document_kind("https://patents.example/doc1", title="patent application") == "patent_page"
    assert infer_document_kind("https://doi.org/10.1000/example") == "html"



def test_enrich_page_record_adds_local_paths(tmp_path: Path) -> None:
    page = {"candidate_id": "cand_1", "url": "https://doi.org/10.1000/example", "title": "Paper"}
    enriched = enrich_page_record(page, tmp_path)
    assert enriched["fetch_status"] == "pending"
    assert enriched["local_artifact_path"].endswith(".html")
    assert enriched["metadata_path"].endswith(".json")



def test_assemble_document_artifacts_for_candidate_builds_documents(tmp_path: Path) -> None:
    bundle = {
        "candidate_id": "cand_1",
        "pages": [
            {"candidate_id": "cand_1", "url": "https://doi.org/10.1000/example", "title": "Paper"},
            {"candidate_id": "cand_1", "url": "https://example.org/file.pdf", "title": "PDF"},
        ],
    }
    result = assemble_document_artifacts_for_candidate(bundle, tmp_path)
    assert result["status"] == "ok"
    assert result["document_count"] == 2
    assert any(doc["document_kind"] == "pdf" for doc in result["documents"])
