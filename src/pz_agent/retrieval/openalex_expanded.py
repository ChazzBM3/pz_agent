from __future__ import annotations

from typing import Any

from pz_agent.search.backends import OpenAlexSearchBackend


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def build_openalex_queries(candidate: dict[str, Any], max_queries: int = 6) -> list[str]:
    identity = candidate.get("identity", {}) or {}
    expansion = candidate.get("structure_expansion", {}) or {}
    patent_bundle = candidate.get("patent_retrieval", {}) or {}

    iupac_name = _clean_text(identity.get("iupac_name"))
    scaffold = _clean_text(identity.get("core_assumption") or identity.get("scaffold") or "phenothiazine")
    substitution_pattern = _clean_text(identity.get("substitution_pattern")).replace("_", " ")
    synonyms = [_clean_text(item) for item in (expansion.get("synonyms") or []) if _clean_text(item)]

    patent_queries = [_clean_text(item) for item in (patent_bundle.get("queries") or []) if _clean_text(item)]

    queries: list[str] = []
    if iupac_name:
        queries.append(f'"{iupac_name}" redox solubility synthesis')
    for synonym in synonyms[:2]:
        queries.append(f'"{synonym}" phenothiazine redox')
    if scaffold:
        queries.append(f'"{scaffold}" {substitution_pattern} redox solubility')
        queries.append(f'"{scaffold}" derivative electrochemistry')
    for patent_query in patent_queries[:2]:
        queries.append(patent_query.replace(" patent", " chemistry"))

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = query.lower()
        if query and key not in seen:
            seen.add(key)
            deduped.append(query)
        if len(deduped) >= max_queries:
            break
    return deduped


def retrieve_openalex_evidence_for_candidate(candidate: dict[str, Any], count: int = 5) -> dict[str, Any]:
    backend = OpenAlexSearchBackend()
    queries = build_openalex_queries(candidate)
    bundles: list[dict[str, Any]] = []
    errors: list[str] = []

    for query in queries:
        try:
            hits = backend.search(query, count=count)
            bundles.append({"query": query, "hits": [hit.__dict__ for hit in hits]})
        except Exception as exc:
            errors.append(f"OpenAlex: {query}: {exc}")

    status = "ok" if bundles else "unavailable"
    return {
        "queries": queries,
        "openalex": bundles,
        "errors": errors,
        "status": status,
    }
