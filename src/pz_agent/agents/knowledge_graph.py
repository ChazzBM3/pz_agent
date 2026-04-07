from __future__ import annotations

from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.kg.builder import build_graph_snapshot
from pz_agent.state import RunState


class KnowledgeGraphAgent(BaseAgent):
    name = "knowledge_graph"

    def run(self, state: RunState) -> RunState:
        kg_relpath = self.config.get("kg", {}).get("path", "artifacts/knowledge_graph.json")
        kg_path = state.run_dir / Path(kg_relpath).name
        graph = build_graph_snapshot(state)
        write_json(kg_path, graph)
        state.knowledge_graph_path = kg_path
        media_registry = []
        for note in state.critique_notes or []:
            media_registry.extend(note.get("media_evidence", []))
        state.media_registry = media_registry
        state.log(f"Knowledge graph updated at {kg_path}")
        return state
