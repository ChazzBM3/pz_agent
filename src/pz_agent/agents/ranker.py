from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.analysis.diversity import diversify_placeholder
from pz_agent.analysis.pareto import apply_literature_adjustment, compute_placeholder_pareto
from pz_agent.io import write_json
from pz_agent.kg.scaffold_features import write_scaffold_features
from pz_agent.state import RunState


class RankerAgent(BaseAgent):
    name = "ranker"

    def run(self, state: RunState) -> RunState:
        ranked = compute_placeholder_pareto(list(state.predictions or []))
        critique_by_candidate = {note.get("candidate_id"): note for note in (state.critique_notes or []) if note.get("candidate_id")}
        scaffold_features = write_scaffold_features(
            state.knowledge_graph_path,
            state.run_dir / "scaffold_features.json",
        )

        evidence_aware_ranked = []
        for item in ranked:
            candidate_id = item.get("id")
            critique_note = critique_by_candidate.get(candidate_id)
            pre_enriched = dict(item)
            ranking_rationale = dict(pre_enriched.get("ranking_rationale") or {})
            ranking_rationale["evidence_sources"] = {
                "has_critique_note": critique_note is not None,
                "uses_identity_level_evidence": bool(critique_note and ((critique_note.get("signals") or {}).get("exact_match_hits") or (critique_note.get("signals") or {}).get("analog_match_hits"))),
                "measurement_context_present": bool((critique_note or {}).get("measurement_context") or ranking_rationale.get("measurement_summary")),
            }
            scaffold_context = scaffold_features.get(candidate_id)
            if scaffold_context:
                ranking_rationale["scaffold_context"] = scaffold_context
                ranking_rationale["evidence_sources"]["scaffold_context_present"] = True
            else:
                ranking_rationale["evidence_sources"]["scaffold_context_present"] = False
            pre_enriched["ranking_rationale"] = ranking_rationale
            enriched = apply_literature_adjustment(pre_enriched, critique_note)
            evidence_aware_ranked.append(enriched)

        evidence_aware_ranked.sort(
            key=lambda x: (
                -1.0 if x.get("predicted_priority_literature_adjusted") is None else -float(x["predicted_priority_literature_adjusted"]),
                -1.0 if x.get("predicted_priority") is None else -float(x["predicted_priority"]),
                x.get("id", ""),
            )
        )

        novelty_ranked = sorted(
            evidence_aware_ranked,
            key=lambda x: (
                -1.0 if x.get("predicted_priority_novelty_adjusted") is None else -float(x["predicted_priority_novelty_adjusted"]),
                -1.0 if x.get("predicted_priority") is None else -float(x["predicted_priority"]),
                x.get("id", ""),
            ),
        )

        ranked = diversify_placeholder(evidence_aware_ranked)
        state.ranked = ranked
        state.novelty_ranked = diversify_placeholder(novelty_ranked)
        shortlist_size = int(self.config.get("screening", {}).get("shortlist_size", 3))
        state.shortlist = list((state.ranked or [])[: min(shortlist_size, len(state.ranked or []))])
        state.novelty_shortlist = list((state.novelty_ranked or [])[: min(shortlist_size, len(state.novelty_ranked or []))])
        ranker_views = {
            "ranked": state.ranked,
            "shortlist": state.shortlist,
            "novelty_ranked": state.novelty_ranked,
            "novelty_shortlist": state.novelty_shortlist,
        }
        write_json(state.run_dir / "ranker_views.json", ranker_views)

        support_ids = [row.get("id") for row in (state.shortlist or []) if row.get("id")]
        novelty_ids = [row.get("id") for row in (state.novelty_shortlist or []) if row.get("id")]
        support_only_ids = [item for item in support_ids if item not in set(novelty_ids)]
        novelty_only_ids = [item for item in novelty_ids if item not in set(support_ids)]
        ranked_by_id = {row.get("id"): row for row in (state.ranked or []) if row.get("id")}
        novelty_by_id = {row.get("id"): row for row in (state.novelty_ranked or []) if row.get("id")}
        write_json(
            state.run_dir / "ranker_views_summary.json",
            {
                "support_top_ids": support_ids,
                "novelty_top_ids": novelty_ids,
                "overlap_ids": sorted(set(support_ids) & set(novelty_ids)),
                "support_only_ids": support_only_ids,
                "novelty_only_ids": novelty_only_ids,
                "support_only_details": [
                    {
                        "id": item,
                        "literature_adjustment": ranked_by_id.get(item, {}).get("literature_adjustment"),
                        "novelty_adjustment": ranked_by_id.get(item, {}).get("novelty_adjustment"),
                        "predicted_priority_literature_adjusted": ranked_by_id.get(item, {}).get("predicted_priority_literature_adjusted"),
                        "predicted_priority_novelty_adjusted": ranked_by_id.get(item, {}).get("predicted_priority_novelty_adjusted"),
                    }
                    for item in support_only_ids
                ],
                "novelty_only_details": [
                    {
                        "id": item,
                        "literature_adjustment": novelty_by_id.get(item, {}).get("literature_adjustment"),
                        "novelty_adjustment": novelty_by_id.get(item, {}).get("novelty_adjustment"),
                        "predicted_priority_literature_adjusted": novelty_by_id.get(item, {}).get("predicted_priority_literature_adjusted"),
                        "predicted_priority_novelty_adjusted": novelty_by_id.get(item, {}).get("predicted_priority_novelty_adjusted"),
                    }
                    for item in novelty_only_ids
                ],
            },
        )
        state.log("Ranker produced support-aware and novelty-aware shortlists using predicted properties, measured support, KG critique signals, and scaffold context")
        return state
