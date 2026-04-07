from __future__ import annotations

from pathlib import Path

from pz_agent.io import write_json
from pz_agent.state import RunState


def write_evidence_report(state: RunState) -> Path:
    path = state.run_dir / "evidence_report.json"
    payload = {
        "shortlist": state.shortlist or [],
        "critique_notes": state.critique_notes or [],
        "knowledge_graph_path": str(state.knowledge_graph_path) if state.knowledge_graph_path else None,
    }
    write_json(path, payload)
    return path
