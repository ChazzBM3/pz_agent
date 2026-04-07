from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState


class BenchmarkAgent(BaseAgent):
    name = "benchmark"

    def run(self, state: RunState) -> RunState:
        state.benchmark = {
            "selected_model": "baseline_placeholder",
            "status": "not_yet_implemented",
        }
        state.log("Benchmark stage recorded placeholder calibration output")
        return state
