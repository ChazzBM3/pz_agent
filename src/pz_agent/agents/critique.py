from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.kg.retrieval import attach_critique_placeholders, synthesize_evidence_from_queries
from pz_agent.state import RunState


class CritiqueAgent(BaseAgent):
    name = "critique"

    def run(self, state: RunState) -> RunState:
        search_fields = list(self.config.get("critique", {}).get("search_fields", []))
        critique_notes = attach_critique_placeholders(
            shortlist=state.shortlist or [],
            enable_web_search=bool(self.config.get("critique", {}).get("enable_web_search", True)),
            max_candidates=int(self.config.get("critique", {}).get("max_candidates", 10)),
            search_fields=search_fields,
            graph_path=state.knowledge_graph_path,
        )
        critique_notes = synthesize_evidence_from_queries(critique_notes)
        state.critique_notes = critique_notes
        write_json(state.run_dir / "critique_notes.json", critique_notes)
        state.log("Critique agent prepared candidate evidence bundles with KG-derived context, targeted queries, and text/image placeholders")
        return state
