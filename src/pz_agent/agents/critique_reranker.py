from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.analysis.diversity import diversify_placeholder
from pz_agent.analysis.pareto import apply_literature_adjustment, compute_decoration_adjustment
from pz_agent.kg.rag import (
    summarize_candidate_property_values,
    summarize_property_coverage,
    summarize_support_contradiction,
)
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

            note = dict(note_map.get(row["id"], {})) if note_map.get(row["id"]) else None
            if note is not None:
                note.setdefault("signals", {})
                kg_summary = summarize_support_contradiction(state.knowledge_graph_path, row["id"])
                measurement_summary = summarize_property_coverage(state.knowledge_graph_path, row["id"])
                measurement_values = summarize_candidate_property_values(
                    state.knowledge_graph_path,
                    row["id"],
                    [
                        "oxidation_potential",
                        "reduction_potential",
                        "groundState.solvation_energy",
                        "hole_reorganization_energy",
                        "electron_reorganization_energy",
                    ],
                )
                note["signals"]["exact_match_hits"] = max(
                    int(note["signals"].get("exact_match_hits", 0) or 0),
                    int(kg_summary.get("exact_match_hits", 0) or 0),
                )
                note["signals"]["analog_match_hits"] = max(
                    int(note["signals"].get("analog_match_hits", 0) or 0),
                    int(kg_summary.get("analog_match_hits", 0) or 0),
                )
                note["signals"]["support_score"] = max(
                    float(note["signals"].get("support_score", 0.0) or 0.0),
                    float(kg_summary.get("support_score", 0.0) or 0.0),
                )
                note["signals"]["contradiction_score"] = max(
                    float(note["signals"].get("contradiction_score", 0.0) or 0.0),
                    float(kg_summary.get("contradiction_score", 0.0) or 0.0),
                )
                note["signals"]["patent_hit_count"] = max(
                    int(note["signals"].get("patent_hit_count", 0) or 0),
                    int(kg_summary.get("patent_hit_count", 0) or 0),
                )
                note["signals"]["scholarly_hit_count"] = max(
                    int(note["signals"].get("scholarly_hit_count", 0) or 0),
                    int(kg_summary.get("scholarly_hit_count", 0) or 0),
                )
                note["signals"]["measurement_count"] = max(
                    int(note["signals"].get("measurement_count", 0) or 0),
                    int(measurement_summary.get("measurement_count", 0) or 0),
                )
                note["signals"]["property_count"] = max(
                    int(note["signals"].get("property_count", 0) or 0),
                    int(measurement_summary.get("property_count", 0) or 0),
                )
                item.setdefault("ranking_rationale", {})
                item["ranking_rationale"]["kg_summary"] = kg_summary
                item["ranking_rationale"]["measurement_summary"] = measurement_summary
                item["ranking_rationale"]["measurement_values"] = measurement_values
                support_mix = dict(note.get("support_mix") or {})
                simulation_support = float(support_mix.get("simulation_support", 0.0) or 0.0)
                item["ranking_rationale"]["support_mix"] = support_mix
                belief_state = {
                    "support_score": float(note["signals"].get("support_score", 0.0) or 0.0),
                    "contradiction_score": float(note["signals"].get("contradiction_score", 0.0) or 0.0),
                    "transferability_score": float((note.get("support_mix") or {}).get("transferability_score", 0.0) or 0.0),
                    "simulation_support": simulation_support,
                }
                item["ranking_rationale"]["belief_state"] = belief_state
                note["ranking_rationale"] = {**item.get("ranking_rationale", {}), "belief_state": belief_state}
                note["measurement_context"] = measurement_summary
                note["measurement_values"] = measurement_values
            reranked.append(apply_literature_adjustment(item, note))
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
        state.log("Critique reranker adjusted priorities using literature, KG support/contradiction summaries, and decoration evidence")
        return state
