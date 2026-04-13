from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pz_agent.io import ensure_dir


def _safe_stem(candidate_id: str, url: str | None, title: str | None) -> str:
    base = url or title or candidate_id or "page"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]
    return f"{candidate_id}_{digest}"


def infer_document_kind(url: str | None, title: str | None = None) -> str:
    text = f"{url or ''} {title or ''}".lower()
    if ".pdf" in text:
        return "pdf"
    if any(token in text for token in ["patent", "patcid", "surechembl"]):
        return "patent_page"
    return "html"


def enrich_page_record(page: dict[str, Any], artifacts_dir: str | Path) -> dict[str, Any]:
    candidate_id = str(page.get("candidate_id") or "candidate")
    url = page.get("url")
    title = page.get("title")
    stem = _safe_stem(candidate_id, url, title)
    doc_kind = infer_document_kind(url, title)
    host = (urlparse(url).netloc or "").lower() if url else ""

    base_dir = Path(artifacts_dir) / candidate_id / "documents"
    ensure_dir(base_dir)
    extension = ".pdf" if doc_kind == "pdf" else ".html"
    local_path = base_dir / f"{stem}{extension}"
    metadata_path = base_dir / f"{stem}.json"

    enriched = dict(page)
    enriched.update(
        {
            "document_kind": doc_kind,
            "fetch_status": "pending",
            "local_artifact_path": str(local_path),
            "metadata_path": str(metadata_path),
            "host": host,
        }
    )
    return enriched


def assemble_document_artifacts_for_candidate(page_bundle: dict[str, Any], artifacts_dir: str | Path) -> dict[str, Any]:
    candidate_id = str(page_bundle.get("candidate_id") or "candidate")
    pages = [enrich_page_record(page, artifacts_dir) for page in (page_bundle.get("pages") or [])]
    return {
        "candidate_id": candidate_id,
        "document_count": len(pages),
        "documents": pages,
        "status": "ok" if pages else "empty",
    }
