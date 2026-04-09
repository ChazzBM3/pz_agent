from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.kg.retrieval import attach_critique_placeholders, synthesize_evidence_from_queries
from pz_agent.search.backends import get_search_backend
from pz_agent.state import RunState


def _live_search_note(note: dict, backend_name: str, count: int) -> dict:
    backend = get_search_backend(backend_name)
    evidence = []
    media_evidence = []
    for idx, query in enumerate(note.get("queries", [])):
        try:
            hits = backend.search(query, count=count)
        except Exception:
            hits = []
        for hit_idx, hit in enumerate(hits):
            evidence.append(
                {
                    "id": f"evidence::{note['candidate_id']}::{idx}::{hit_idx}",
                    "kind": "web_result",
                    "query": query,
                    "title": hit.title,
                    "url": hit.url,
                    "snippet": hit.snippet,
                    "match_type": hit.match_type,
                    "provenance": {
                        "source_type": backend.name,
                        "query": query,
                        "confidence": hit.confidence,
                        "evidence_level": "web_search",
                    },
                }
            )
        media_evidence.append(
            {
                "id": f"media::{note['candidate_id']}::{idx}",
                "kind": "query_trace",
                "query": query,
                "caption": f"Search trace for {query}",
                "source_url": None,
                "image_path": None,
                "media_type": "search_trace",
                "provenance": {
                    "source_type": backend.name,
                    "query": query,
                    "confidence": None,
                },
            }
        )
    note["evidence"] = evidence
    note["media_evidence"] = media_evidence
    note["status"] = "live_web_results" if evidence else "live_web_no_results"
    note["summary"] = f"Live web critique collected {len(evidence)} evidence hits via {backend.name}."
    return note


class CritiqueAgent(BaseAgent):
    name = "critique"

    def run(self, state: RunState) -> RunState:
        search_fields = list(self.config.get("critique", {}).get("search_fields", []))
        enable_web_search = bool(self.config.get("critique", {}).get("enable_web_search", True))
        critique_notes = attach_critique_placeholders(
            shortlist=state.shortlist or [],
            enable_web_search=enable_web_search,
            max_candidates=int(self.config.get("critique", {}).get("max_candidates", 10)),
            search_fields=search_fields,
            graph_path=state.knowledge_graph_path,
        )

        backend_name = str(self.config.get("search", {}).get("backend", "stub"))
        count = int(self.config.get("search", {}).get("count", 5))
        if enable_web_search and backend_name != "stub":
            critique_notes = [_live_search_note(note, backend_name=backend_name, count=count) for note in critique_notes]
            state.log(f"Critique agent collected live web evidence using {backend_name}")
        else:
            critique_notes = synthesize_evidence_from_queries(critique_notes)
            state.log("Critique agent prepared candidate evidence bundles with KG-derived context, targeted queries, and text/image placeholders")

        state.critique_notes = critique_notes
        write_json(state.run_dir / "critique_notes.json", critique_notes)
        return state
