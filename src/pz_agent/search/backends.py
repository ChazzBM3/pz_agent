from __future__ import annotations

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


class PlannedScholarlySearchBackend:
    name = "planned_scholarly_api"

    def search(self, query: str, count: int = 5) -> list[SearchHit]:
        raise NotImplementedError("Production scholarly search backend is planned but not configured yet.")


def get_search_backend(name: str) -> SearchBackend:
    if name == "duckduckgo":
        return DuckDuckGoSearchBackend()
    if name == "planned_scholarly_api":
        return PlannedScholarlySearchBackend()
    return StubSearchBackend()
