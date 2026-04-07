from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState


class RankerAgent(BaseAgent):
    name = "ranker"

    def run(self, state: RunState) -> RunState:
        state.ranked = list(state.predictions or [])
        state.shortlist = list((state.ranked or [])[: min(3, len(state.ranked or []))])
        state.log("Ranker produced placeholder ranked list and shortlist")
        return state
