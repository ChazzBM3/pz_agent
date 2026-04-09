from __future__ import annotations

import json
from urllib.parse import quote_plus, urlparse
from urllib.request import urlopen

from pz_agent.search.base import SearchBackend, SearchHit

DDGS_IMPORT_SOURCE = None

try:
    from ddgs import DDGS
    DDGS_IMPORT_SOURCE = "ddgs"
    DDGS_AVAILABLE = True
except Exception:
    try:
        from duckduckgo_search import DDGS
        DDGS_IMPORT_SOURCE = "duckduckgo_search"
        DDGS_AVAILABLE = True
    except Exception:
        DDGS = None
        DDGS_AVAILABLE = False


class StubSearchBackend:
    name = "stub"

    def search(self, query: str, count: int = 5) -> list[SearchHit]:
        return [
            SearchHit(
                title=f"Stub result {idx + 1} for {query}",
                url=None,
                snippet="Replace with live search results from OpenClaw orchestration or a production scholarly API.",
                source=self.name,
                confidence=None,
                match_type="unknown",
            )
            for idx in range(count)
        ]


class DuckDuckGoSearchBackend:
    name = "duckduckgo"

    def search(self, query: str, count: int = 5) -> list[SearchHit]:
        if not DDGS_AVAILABLE:
            raise RuntimeError("Neither ddgs nor duckduckgo_search is installed")
        hits: list[SearchHit] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=count):
                hits.append(
                    SearchHit(
                        title=item.get("title"),
                        url=item.get("href"),
                        snippet=item.get("body"),
                        source=self.name,
                        confidence=None,
                        match_type="unknown",
                    )
                )
        return hits


class OpenAlexSearchBackend:
    name = "openalex"

    def search(self, query: str, count: int = 5) -> list[SearchHit]:
        per_page = max(1, min(max(int(count) * 3, 10), 50))
        url = (
            "https://api.openalex.org/works?search="
            f"{quote_plus(query)}&per-page={per_page}&select=display_name,doi,id,primary_location,abstract_inverted_index,publication_year"
        )
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        ranked_hits: list[tuple[float, SearchHit]] = []
        for item in payload.get("results", []):
            title = item.get("display_name")
            doi = item.get("doi")
            primary_location = item.get("primary_location") or {}
            landing_page = primary_location.get("landing_page_url") or item.get("id") or doi
            abstract_index = item.get("abstract_inverted_index") or {}
            snippet = _openalex_abstract_to_text(abstract_index)
            if not snippet:
                year = item.get("publication_year")
                snippet = f"OpenAlex scholarly record{f' ({year})' if year else ''}."
            hit = SearchHit(
                title=title,
                url=landing_page,
                snippet=snippet,
                source=self.name,
                confidence=None,
                match_type="unknown",
            )
            ranked_hits.append((_score_openalex_hit(query, hit), hit))

        ranked_hits.sort(key=lambda pair: pair[0], reverse=True)
        return [hit for _, hit in ranked_hits[:count]]


class PlannedScholarlySearchBackend:
    name = "planned_scholarly_api"

    def search(self, query: str, count: int = 5) -> list[SearchHit]:
        raise NotImplementedError("Production scholarly search backend is planned but not configured yet.")


def _score_openalex_hit(query: str, hit: SearchHit) -> float:
    query_text = query.lower()
    hit_text = " ".join(part for part in [hit.title or "", hit.snippet or "", hit.url or ""] if part).lower()
    score = 0.0
    for token in ["solubility", "soluble", "synthesis", "synthetic", "redox", "oxidation", "reduction", "electrochemical", "phenothiazine"]:
        if token in query_text and token in hit_text:
            score += 1.0
    for token in ["cl", "br", "f", "i", "c#n", "c(=o)"]:
        if token in query_text and token in hit_text:
            score += 1.5
    if any(token in hit_text for token in ["review", "perspective", "overview", "platform", "editor"]):
        score -= 1.0
    host = (urlparse(hit.url).netloc or "").lower() if hit.url else ""
    if any(domain in host for domain in ["acs", "wiley", "sciencedirect", "nature", "pubmed", "doi.org"]):
        score += 0.3
    return score


def _openalex_abstract_to_text(abstract_index: dict) -> str | None:
    if not abstract_index:
        return None
    positions: dict[int, str] = {}
    for word, indexes in abstract_index.items():
        for idx in indexes or []:
            positions[int(idx)] = word
    if not positions:
        return None
    return " ".join(token for _, token in sorted(positions.items()))


def get_search_backend(name: str) -> SearchBackend:
    if name == "duckduckgo":
        return DuckDuckGoSearchBackend()
    if name == "openalex":
        return OpenAlexSearchBackend()
    if name == "planned_scholarly_api":
        return PlannedScholarlySearchBackend()
    return StubSearchBackend()
