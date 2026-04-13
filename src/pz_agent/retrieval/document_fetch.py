from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pz_agent.io import ensure_dir, write_json


USER_AGENT = "pz-agent/0.1"


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


def _fetch_url(url: str, timeout: int = 20) -> tuple[bytes, str | None]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        content = response.read()
        content_type = response.headers.get("Content-Type")
    return content, content_type


def _persist_document(record: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    url = record.get("url")
    if not url:
        updated = dict(record)
        updated["fetch_status"] = "missing_url"
        return updated

    updated = dict(record)
    local_path = Path(updated["local_artifact_path"])
    metadata_path = Path(updated["metadata_path"])

    try:
        content, content_type = _fetch_url(str(url), timeout=timeout)
        ensure_dir(local_path.parent)
        local_path.write_bytes(content)
        updated["fetch_status"] = "fetched"
        updated["content_type"] = content_type
        updated["byte_count"] = len(content)
    except Exception as exc:
        updated["fetch_status"] = "failed"
        updated["fetch_error"] = str(exc)

    write_json(metadata_path, updated)
    return updated


def assemble_document_artifacts_for_candidate(page_bundle: dict[str, Any], artifacts_dir: str | Path, timeout: int = 20, fetch_live: bool = True) -> dict[str, Any]:
    candidate_id = str(page_bundle.get("candidate_id") or "candidate")
    pages = [enrich_page_record(page, artifacts_dir) for page in (page_bundle.get("pages") or [])]
    if fetch_live:
        pages = [_persist_document(page, timeout=timeout) for page in pages]
    return {
        "candidate_id": candidate_id,
        "document_count": len(pages),
        "documents": pages,
        "status": "ok" if pages else "empty",
    }
