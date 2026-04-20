from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.reports.evidence_report import write_evidence_report
from pz_agent.state import RunState


class ReporterAgent(BaseAgent):
    name = "reporter"

    def run(self, state: RunState) -> RunState:
        evidence_report_path = write_evidence_report(state)
        evidence_report = __import__('json').loads(evidence_report_path.read_text()) if evidence_report_path.exists() else {}

        ranked = state.ranked or []
        shortlist = state.shortlist or []
        critique_by_candidate = {note.get("candidate_id"): note for note in (state.critique_notes or []) if note.get("candidate_id")}
        prediction_by_candidate = {pred.get("id"): pred for pred in (state.predictions or []) if pred.get("id")}

        candidate_decisions = []
        for item in shortlist:
            candidate_id = item.get("id")
            critique_note = critique_by_candidate.get(candidate_id, {})
            prediction = prediction_by_candidate.get(candidate_id, {})
            rationale = dict(item.get("ranking_rationale") or {})
            signals = dict(critique_note.get("signals") or {})
            candidate_decisions.append(
                {
                    "candidate_id": candidate_id,
                    "queue_status": next((entry.get("status") for entry in (state.simulation_queue or []) if entry.get("candidate_id") == candidate_id), None),
                    "submission_id": next((entry.get("submission", {}).get("submission_id") for entry in (state.simulation_queue or []) if entry.get("candidate_id") == candidate_id), None),
                    "predicted_priority": item.get("predicted_priority"),
                    "predicted_priority_literature_adjusted": item.get("predicted_priority_literature_adjusted", item.get("predicted_priority")),
                    "literature_adjustment": item.get("literature_adjustment", 0.0),
                    "predicted_properties": {
                        "synthesizability": prediction.get("predicted_synthesizability"),
                        "solubility": prediction.get("predicted_solubility"),
                    },
                    "measured_support": {
                        "measurement_summary": rationale.get("measurement_summary"),
                        "measurement_values": rationale.get("measurement_values"),
                    },
                    "evidence_summary": {
                        "evidence_tier": critique_note.get("evidence_tier"),
                        "exact_match_hits": signals.get("exact_match_hits", 0),
                        "analog_match_hits": signals.get("analog_match_hits", 0),
                        "patent_hit_count": signals.get("patent_hit_count", 0),
                        "scholarly_hit_count": signals.get("scholarly_hit_count", 0),
                        "contradiction_score": signals.get("contradiction_score", 0.0),
                    },
                    "selection_rationale": rationale.get("literature_adjustment", []),
                    "stable_identity_key": item.get("stable_identity_key") or (item.get("identity") or {}).get("stable_identity_key"),
                }
            )

        top_candidate_id = ranked[0].get("id") if ranked else None
        validation_results = state.validation or []
        report = {
            "summary": {
                "status": "pseudo_production_readying",
                "top_candidate_id": top_candidate_id,
                "ranked_count": len(ranked),
                "shortlist_count": len(shortlist),
                "simulation_queue_count": len(state.simulation_queue or []),
                "simulation_submission_count": len(state.simulation_submissions or []),
                "simulation_check_count": len(state.simulation_checks or []),
                "simulation_failure_count": len(state.simulation_failures or []),
                "validation_count": len(validation_results),
                "usable_validation_count": sum(1 for item in validation_results if (item.get("quality_assessment") or {}).get("quality") == "usable"),
                "partial_validation_count": sum(1 for item in validation_results if (item.get("quality_assessment") or {}).get("quality") == "partial"),
                "failed_validation_count": sum(1 for item in validation_results if (item.get("quality_assessment") or {}).get("quality") == "failed"),
                "queued_evidence_query_count": sum(1 for item in (state.action_queue or []) if item.get("action_type") == "evidence_query"),
                "has_identity_aware_graph": bool(state.knowledge_graph_path),
            },
            "decision_summary": candidate_decisions,
            "ranked": ranked,
            "shortlist": shortlist,
            "predictions": state.predictions or [],
            "graph_metrics": evidence_report.get("graph_metrics", {}),
            "prediction_provenance_summary": [
                {
                    "id": pred["id"],
                    "prediction_provenance": pred.get("prediction_provenance", {}),
                }
                for pred in (state.predictions or [])
            ],
            "critique_notes": state.critique_notes or [],
            "expansion_proposals": state.expansion_registry or [],
            "action_queue": state.action_queue or [],
            "action_outcomes": state.action_outcomes or [],
            "outcome_stats": state.outcome_stats or {},
            "simulation_queue": state.simulation_queue or [],
            "simulation_manifest": state.simulation_manifest or {},
            "simulation_submissions": state.simulation_submissions or [],
            "simulation_checks": state.simulation_checks or [],
            "simulation_failures": state.simulation_failures or [],
            "validation_results": validation_results,
            "artifacts": {
                "expansion_proposals_accepted_path": str(state.run_dir / "expansion_proposals.accepted.json"),
                "expansion_proposals_rejected_path": str(state.run_dir / "expansion_proposals.rejected.json"),
                "action_queue_path": str(state.run_dir / "action_queue.json"),
                "action_outcomes_path": str(state.run_dir / "action_outcomes.json"),
                "outcome_stats_path": str(state.run_dir / "outcome_stats.json"),
                "evidence_report": str(evidence_report_path),
                "simulation_queue_path": str(state.run_dir / "simulation_queue.json"),
                "simulation_manifest_path": str(state.run_dir / "simulation_manifest.json"),
                "simulation_submissions_path": str(state.run_dir / "simulation_submissions.json"),
                "simulation_checks_path": str(state.run_dir / "simulation_checks.json"),
                "simulation_failures_path": str(state.run_dir / "simulation_failures.json"),
                "validation_results_path": str(state.run_dir / "validation_results.json"),
            },
        }
        write_json(state.run_dir / "report.json", report)
        state.log("Reporter wrote operator-facing run summary with simulation handoff, submission, and validation artifacts and candidate decisions")
        return state
