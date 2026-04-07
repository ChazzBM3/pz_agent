from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.state import RunState


class ReporterAgent(BaseAgent):
    name = "reporter"

    def run(self, state: RunState) -> RunState:
        report = {
            "summary": "Placeholder report",
            "ranked": state.ranked or [],
            "shortlist": state.shortlist or [],
        }
        write_json(state.run_dir / "report.json", report)
        state.log("Reporter wrote placeholder report")
        return state
