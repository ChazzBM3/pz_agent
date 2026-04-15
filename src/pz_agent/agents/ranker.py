from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.analysis.diversity import diversify_placeholder
from pz_agent.analysis.pareto import apply_literature_adjustment, compute_placeholder_pareto
from pz_agent.state import RunState


class RankerAgent(BaseAgent):
    name = "ranker"

    def run(self, state: RunState) -> RunState:
        ranked = compute_placeholder_pareto(list(state.predictions or []))
        critique_by_candidate = {note.get("candidate_id"): note for note in (state.critique_notes or []) if note.get("candidate_id")}

        evidence_aware_ranked = []
        for item in ranked:
            candidate_id = item.get("id")
            critique_note = critique_by_candidate.get(candidate_id)
            enriched = apply_literature_adjustment(item, critique_note)
            ranking_rationale = dict(enriched.get("ranking_rationale") or {})
            ranking_rationale["evidence_sources"] = {
                "has_critique_note": critique_note is not None,
                "uses_identity_level_evidence": bool(critique_note and ((critique_note.get("signals") or {}).get("exact_match_hits") or (critique_note.get("signals") or {}).get("analog_match_hits"))),
                "measurement_context_present": bool((critique_note or {}).get("measurement_context") or ranking_rationale.get("measurement_summary")),
            }
            enriched["ranking_rationale"] = ranking_rationale
            evidence_aware_ranked.append(enriched)

        evidence_aware_ranked.sort(
            key=lambda x: (
                -1.0 if x.get("predicted_priority_literature_adjusted") is None else -float(x["predicted_priority_literature_adjusted"]),
                -1.0 if x.get("predicted_priority") is None else -float(x["predicted_priority"]),
                x.get("id", ""),
            )
        )

        ranked = diversify_placeholder(evidence_aware_ranked)
        state.ranked = ranked
        shortlist_size = int(self.config.get("screening", {}).get("shortlist_size", 3))
        state.shortlist = list((state.ranked or [])[: min(shortlist_size, len(state.ranked or []))])
        state.log("Ranker produced evidence-aware shortlist using predicted properties, measured support, and KG critique signals")
        return state
