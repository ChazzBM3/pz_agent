from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.analysis.diversity import diversify_placeholder
from pz_agent.analysis.pareto import compute_placeholder_pareto
from pz_agent.state import RunState


class RankerAgent(BaseAgent):
    name = "ranker"

    def run(self, state: RunState) -> RunState:
        ranked = compute_placeholder_pareto(list(state.predictions or []))
        ranked = diversify_placeholder(ranked)
        state.ranked = ranked
        state.shortlist = list((state.ranked or [])[: min(3, len(state.ranked or []))])
        state.log("Ranker produced placeholder shortlist emphasizing synthesizability and solubility")
        return state
