from __future__ import annotations

from pathlib import Path

from pz_agent.retrieval.document_fetch import (
    _persist_document,
    assemble_document_artifacts_for_candidate,
    enrich_page_record,
    infer_document_kind,
)


class _FakeHeaders:
    def __init__(self, content_type: str) -> None:
        self._content_type = content_type

    def get(self, key: str, default=None):
        if key.lower() == "content-type":
            return self._content_type
        return default


class _FakeResponse:
    def __init__(self, content: bytes, content_type: str) -> None:
        self._content = content
        self.headers = _FakeHeaders(content_type)

    def read(self) -> bytes:
        return self._content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False



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



def test_persist_document_fetches_and_writes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.retrieval.document_fetch.urlopen",
        lambda request, timeout=20: _FakeResponse(b"<html>ok</html>", "text/html"),
    )
    record = enrich_page_record({"candidate_id": "cand_1", "url": "https://doi.org/10.1000/example", "title": "Paper"}, tmp_path)
    updated = _persist_document(record, timeout=5)
    assert updated["fetch_status"] == "fetched"
    assert updated["byte_count"] == len(b"<html>ok</html>")
    assert Path(updated["local_artifact_path"]).exists()
    assert Path(updated["metadata_path"]).exists()



def test_assemble_document_artifacts_for_candidate_builds_documents(tmp_path: Path) -> None:
    bundle = {
        "candidate_id": "cand_1",
        "pages": [
            {"candidate_id": "cand_1", "url": "https://doi.org/10.1000/example", "title": "Paper"},
            {"candidate_id": "cand_1", "url": "https://example.org/file.pdf", "title": "PDF"},
        ],
    }
    result = assemble_document_artifacts_for_candidate(bundle, tmp_path, fetch_live=False)
    assert result["status"] == "ok"
    assert result["document_count"] == 2
    assert any(doc["document_kind"] == "pdf" for doc in result["documents"])
