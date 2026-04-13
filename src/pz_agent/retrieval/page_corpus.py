from __future__ import annotations

from urllib.parse import urlparse
from typing import Any


TRUSTED_PAGE_HOSTS = (
    "doi.org",
    "pubs.acs.org",
    "sciencedirect.com",
    "wiley.com",
    "nature.com",
    "pubmed.ncbi.nlm.nih.gov",
    "pubchem.ncbi.nlm.nih.gov",
    "openalex.org",
)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _host(url: str | None) -> str:
    return (urlparse(url).netloc or "").lower() if url else ""


def _page_record(candidate_id: str, source: str, query: str | None, title: str | None, url: str | None, snippet: str | None, evidence_kind: str, evidence_level: str | None = None) -> dict[str, Any]:
    host = _host(url)
    return {
        "candidate_id": candidate_id,
        "source": source,
        "query": query,
        "title": _clean_text(title),
        "url": url,
        "snippet": _clean_text(snippet),
        "host": host,
        "evidence_kind": evidence_kind,
        "evidence_level": evidence_level,
        "trusted_host": any(domain in host for domain in TRUSTED_PAGE_HOSTS),
        "page_key": url or f"{source}:{_clean_text(title)}",
    }


def assemble_page_corpus_for_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(candidate.get("id") or "candidate")
    pages: list[dict[str, Any]] = []
    seen: set[str] = set()

    structure_expansion = candidate.get("structure_expansion") or {}
    patent_retrieval = candidate.get("patent_retrieval") or {}
    scholarly_retrieval = candidate.get("scholarly_retrieval") or {}

    for match in structure_expansion.get("exact_matches") or []:
        record = _page_record(
            candidate_id,
            source="pubchem",
            query=structure_expansion.get("query_smiles"),
            title=match.get("title") or f"PubChem exact match {match.get('cid')}",
            url=match.get("pubchem_url"),
            snippet=f"Exact structure page for CID {match.get('cid')}",
            evidence_kind="exact_structure_page",
            evidence_level="exact_structure",
        )
        if record["page_key"] not in seen:
            seen.add(record["page_key"])
            pages.append(record)

    for match in (structure_expansion.get("similarity_matches") or []) + (structure_expansion.get("substructure_matches") or []):
        record = _page_record(
            candidate_id,
            source="pubchem",
            query=structure_expansion.get("query_smiles"),
            title=match.get("title") or f"PubChem analog match {match.get('cid')}",
            url=match.get("pubchem_url"),
            snippet=f"Analog structure page for CID {match.get('cid')}",
            evidence_kind="analog_structure_page",
            evidence_level="analog_structure",
        )
        if record["page_key"] not in seen:
            seen.add(record["page_key"])
            pages.append(record)

    for source_name in ["surechembl", "patcid"]:
        for bundle in patent_retrieval.get(source_name) or []:
            for hit in bundle.get("hits") or []:
                record = _page_record(
                    candidate_id,
                    source=source_name,
                    query=bundle.get("query"),
                    title=hit.get("title") or hit.get("doc_id") or hit.get("patent_id"),
                    url=hit.get("url"),
                    snippet=hit.get("snippet"),
                    evidence_kind="patent_page",
                    evidence_level="patent_retrieval",
                )
                if record["page_key"] not in seen:
                    seen.add(record["page_key"])
                    pages.append(record)

    for bundle in scholarly_retrieval.get("openalex") or []:
        for hit in bundle.get("hits") or []:
            record = _page_record(
                candidate_id,
                source="openalex",
                query=bundle.get("query"),
                title=hit.get("title"),
                url=hit.get("url"),
                snippet=hit.get("snippet"),
                evidence_kind="scholarly_page",
                evidence_level="scholarly_retrieval",
            )
            if record["page_key"] not in seen:
                seen.add(record["page_key"])
                pages.append(record)

    pages.sort(key=lambda item: (not item.get("trusted_host", False), item.get("source") or "", item.get("title") or ""))
    return {
        "candidate_id": candidate_id,
        "page_count": len(pages),
        "pages": pages,
        "status": "ok" if pages else "empty",
    }
