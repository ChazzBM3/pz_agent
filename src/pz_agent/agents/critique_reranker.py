from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.analysis.diversity import diversify_placeholder
from pz_agent.analysis.pareto import apply_literature_adjustment, compute_decoration_adjustment
from pz_agent.state import RunState


class CritiqueRerankerAgent(BaseAgent):
    name = "critique_reranker"

    def run(self, state: RunState) -> RunState:
        note_map = {note["candidate_id"]: note for note in (state.critique_notes or [])}
        reranked = []
        for row in state.ranked or []:
            item = dict(row)
            decoration_bonus, decoration_rationale = compute_decoration_adjustment(item)
            item["decoration_adjustment_second_pass"] = decoration_bonus
            item.setdefault("ranking_rationale", {})
            item["ranking_rationale"]["decoration_adjustment_second_pass"] = decoration_rationale
            reranked.append(apply_literature_adjustment(item, note_map.get(row["id"])))
        reranked.sort(
            key=lambda x: (
                -1.0 if x.get("predicted_priority_literature_adjusted") is None else -float(x["predicted_priority_literature_adjusted"]),
                x.get("id", ""),
            )
        )
        reranked = diversify_placeholder(reranked)
        state.ranked = reranked
        shortlist_size = int(self.config.get("screening", {}).get("shortlist_size", 3))
        state.shortlist = list((state.ranked or [])[: min(shortlist_size, len(state.ranked or []))])
        state.log("Critique reranker adjusted priorities using literature and decoration evidence")
        return state
