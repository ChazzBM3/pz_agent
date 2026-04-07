from __future__ import annotations

from pz_agent.search.base import SearchBackend, SearchHit


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


class PlannedScholarlySearchBackend:
    name = "planned_scholarly_api"

    def search(self, query: str, count: int = 5) -> list[SearchHit]:
        raise NotImplementedError("Production scholarly search backend is planned but not configured yet.")


def get_search_backend(name: str) -> SearchBackend:
    if name == "planned_scholarly_api":
        return PlannedScholarlySearchBackend()
    return StubSearchBackend()
