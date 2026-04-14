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
        report = {
            "summary": "Placeholder report with evidence-aware artifacts",
            "ranked": state.ranked or [],
            "shortlist": state.shortlist or [],
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
            "queued_evidence_query_count": sum(1 for item in (state.action_queue or []) if item.get("action_type") == "evidence_query"),
            "expansion_proposals": state.expansion_registry or [],
            "action_queue": state.action_queue or [],
            "expansion_proposals_accepted_path": str(state.run_dir / "expansion_proposals.accepted.json"),
            "expansion_proposals_rejected_path": str(state.run_dir / "expansion_proposals.rejected.json"),
            "action_queue_path": str(state.run_dir / "action_queue.json"),
            "evidence_report": str(evidence_report_path),
        }
        write_json(state.run_dir / "report.json", report)
        state.log("Reporter wrote placeholder report and evidence-aware artifact bundle")
        return state
