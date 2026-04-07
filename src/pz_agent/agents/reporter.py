from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.reports.evidence_report import write_evidence_report
from pz_agent.state import RunState


class ReporterAgent(BaseAgent):
    name = "reporter"

    def run(self, state: RunState) -> RunState:
        evidence_report_path = write_evidence_report(state)
        report = {
            "summary": "Placeholder report with evidence-aware artifacts",
            "ranked": state.ranked or [],
            "shortlist": state.shortlist or [],
            "predictions": state.predictions or [],
            "prediction_provenance_summary": [
                {
                    "id": pred["id"],
                    "prediction_provenance": pred.get("prediction_provenance", {}),
                }
                for pred in (state.predictions or [])
            ],
            "critique_notes": state.critique_notes or [],
            "evidence_report": str(evidence_report_path),
        }
        write_json(state.run_dir / "report.json", report)
        state.log("Reporter wrote placeholder report and evidence-aware artifact bundle")
        return state
