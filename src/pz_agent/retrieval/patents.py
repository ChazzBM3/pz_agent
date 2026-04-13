from __future__ import annotations

from typing import Any


DEFAULT_PATENT_QUERY_FIELDS = ("title", "abstract", "claims")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def build_patent_queries(candidate: dict[str, Any], max_queries: int = 6) -> list[str]:
    identity = candidate.get("identity", {}) or {}
    expansion = candidate.get("structure_expansion", {}) or {}
    exact_matches = list(expansion.get("exact_matches") or [])
    synonyms = [_clean_text(item) for item in (expansion.get("synonyms") or []) if _clean_text(item)]
    iupac_name = _clean_text(identity.get("iupac_name"))
    scaffold = _clean_text(identity.get("core_assumption") or identity.get("scaffold") or "phenothiazine")
    substitution_pattern = _clean_text(identity.get("substitution_pattern")).replace("_", " ")
    molecular_formula = _clean_text(identity.get("molecular_formula"))

    queries: list[str] = []

    if iupac_name:
        queries.append(f'"{iupac_name}" patent')
    for synonym in synonyms[:2]:
        queries.append(f'"{synonym}" patent')
    for match in exact_matches[:1]:
        title = _clean_text(match.get("title"))
        if title:
            queries.append(f'"{title}" patent')

    motif = " ".join(bit for bit in [scaffold, substitution_pattern] if bit)
    if motif:
        queries.append(f'"{scaffold}" {substitution_pattern} patent chemistry')
        queries.append(f'"{scaffold}" compound patent')
    if molecular_formula and len(molecular_formula) <= 24:
        queries.append(f'"{scaffold}" "{molecular_formula}" patent')

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


def fetch_surechembl_hits(query: str, count: int = 5, timeout: int = 20) -> list[dict[str, Any]]:
    raise NotImplementedError("SureChEMBL retrieval adapter is not configured yet.")


def fetch_patcid_hits(query: str, count: int = 5, timeout: int = 20) -> list[dict[str, Any]]:
    raise NotImplementedError("PatCID retrieval adapter is not configured yet.")


def retrieve_patent_evidence_for_candidate(candidate: dict[str, Any], count: int = 5, timeout: int = 20) -> dict[str, Any]:
    queries = build_patent_queries(candidate)
    surechembl_hits: list[dict[str, Any]] = []
    patcid_hits: list[dict[str, Any]] = []
    errors: list[str] = []

    for query in queries:
        try:
            surechembl_hits.append({"query": query, "hits": fetch_surechembl_hits(query, count=count, timeout=timeout)})
        except Exception as exc:
            errors.append(f"SureChEMBL: {query}: {exc}")
        try:
            patcid_hits.append({"query": query, "hits": fetch_patcid_hits(query, count=count, timeout=timeout)})
        except Exception as exc:
            errors.append(f"PatCID: {query}: {exc}")

    status = "ok" if (surechembl_hits or patcid_hits) else "unavailable"
    if errors and not (surechembl_hits or patcid_hits):
        status = "adapter_unavailable"

    return {
        "queries": queries,
        "surechembl": surechembl_hits,
        "patcid": patcid_hits,
        "errors": errors,
        "status": status,
    }
