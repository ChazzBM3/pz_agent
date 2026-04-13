from __future__ import annotations

from typing import Any

from pz_agent.search.backends import OpenAlexSearchBackend


VALID_MODES = {"broad", "balanced", "strict"}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def build_openalex_queries(
    candidate: dict[str, Any],
    max_queries: int = 6,
    mode: str = "balanced",
    exact_query_budget: int | None = None,
    analog_query_budget: int | None = None,
    exploratory_query_budget: int | None = None,
) -> list[str]:
    selected_mode = mode if mode in VALID_MODES else "balanced"
    identity = candidate.get("identity", {}) or {}
    expansion = candidate.get("structure_expansion", {}) or {}
    patent_bundle = candidate.get("patent_retrieval", {}) or {}

    iupac_name = _clean_text(identity.get("iupac_name"))
    scaffold = _clean_text(identity.get("core_assumption") or identity.get("scaffold") or "phenothiazine")
    substitution_pattern = _clean_text(identity.get("substitution_pattern")).replace("_", " ")
    synonyms = [_clean_text(item) for item in (expansion.get("synonyms") or []) if _clean_text(item)]
    patent_queries = [_clean_text(item) for item in (patent_bundle.get("queries") or []) if _clean_text(item)]

    exact_budget = exact_query_budget if exact_query_budget is not None else {"broad": 1, "balanced": 2, "strict": 3}[selected_mode]
    analog_budget = analog_query_budget if analog_query_budget is not None else {"broad": 3, "balanced": 2, "strict": 1}[selected_mode]
    exploratory_budget = exploratory_query_budget if exploratory_query_budget is not None else {"broad": 2, "balanced": 2, "strict": 1}[selected_mode]

    exact_queries: list[str] = []
    analog_queries: list[str] = []
    exploratory_queries: list[str] = []

    if iupac_name:
        exact_queries.append(f'"{iupac_name}" redox solubility synthesis')
    for synonym in synonyms[:3]:
        exact_queries.append(f'"{synonym}" phenothiazine redox')

    if scaffold:
        analog_queries.append(f'"{scaffold}" {substitution_pattern} redox solubility')
        analog_queries.append(f'"{scaffold}" derivative electrochemistry')
        analog_queries.append(f'"{scaffold}" analog redox literature')

    for patent_query in patent_queries[:3]:
        exploratory_queries.append(patent_query.replace(" patent", " chemistry"))
    exploratory_queries.append(f'"{scaffold}" redox flow battery chemistry')
    exploratory_queries.append(f'"{scaffold}" solubility oxidation reduction')

    queries = exact_queries[:exact_budget] + analog_queries[:analog_budget] + exploratory_queries[:exploratory_budget]

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


def retrieve_openalex_evidence_for_candidate(
    candidate: dict[str, Any],
    count: int = 5,
    mode: str = "balanced",
    max_queries: int = 6,
    exact_query_budget: int | None = None,
    analog_query_budget: int | None = None,
    exploratory_query_budget: int | None = None,
) -> dict[str, Any]:
    backend = OpenAlexSearchBackend()
    queries = build_openalex_queries(
        candidate,
        max_queries=max_queries,
        mode=mode,
        exact_query_budget=exact_query_budget,
        analog_query_budget=analog_query_budget,
        exploratory_query_budget=exploratory_query_budget,
    )
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
        "mode": mode,
        "queries": queries,
        "openalex": bundles,
        "errors": errors,
        "status": status,
    }
