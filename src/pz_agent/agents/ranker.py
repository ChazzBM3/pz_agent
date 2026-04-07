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
        shortlist_size = int(self.config.get("screening", {}).get("shortlist_size", 3))
        state.shortlist = list((state.ranked or [])[: min(shortlist_size, len(state.ranked or []))])
        state.log("Ranker produced weighted shortlist using synthesizability and solubility")
        return state
