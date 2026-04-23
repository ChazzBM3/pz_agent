from __future__ import annotations

import json
from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.chemistry.genmol_import import load_external_genmol_candidates
from pz_agent.io import write_json
from pz_agent.state import RunState


class GenerationIterationMonitorAgent(BaseAgent):
    name = "generation_iteration_monitor"

    def run(self, state: RunState) -> RunState:
        submissions = list(state.generation_iteration_submissions or [])
        monitor_records: list[dict] = []
        aggregate_candidates: list[dict] = []
        completed_outputs: list[str] = []

        for submission in submissions:
            output_dir = Path(str(submission.get("output_dir") or ""))
            log_path = Path(str(submission.get("log_path") or ""))
            payload_path = output_dir / "lowest_energy_conformers.json"
            ranked_path = output_dir / "sa_scores_ranked.json"
            record = {
                "candidate_id": submission.get("candidate_id"),
                "output_dir": str(output_dir),
                "log_path": str(log_path),
                "status": "missing",
                "generated_count": 0,
                "error_summary": None,
                "payload_path": str(payload_path),
            }

            if payload_path.exists() or ranked_path.exists():
                record["status"] = "finished"
                completed_outputs.append(str(output_dir))
                if payload_path.exists():
                    imported = load_external_genmol_candidates(output_dir)
                    record["generated_count"] = len(imported)
                    for idx, item in enumerate(imported, start=1):
                        candidate = dict(item)
                        if not candidate.get("seed"):
                            candidate["seed"] = submission.get("candidate_id")
                        if not candidate.get("generation_round"):
                            candidate["generation_round"] = state.run_dir.name
                        if not candidate.get("notes"):
                            candidate["notes"] = f"iteration_seed:{submission.get('candidate_id')}"
                        if not candidate.get("id"):
                            candidate["id"] = f"{submission.get('candidate_id')}_iter_{idx:04d}"
                        aggregate_candidates.append(candidate)
                elif ranked_path.exists():
                    data = json.loads(ranked_path.read_text())
                    if isinstance(data, list):
                        record["generated_count"] = len(data)
            elif log_path.exists():
                text = log_path.read_text(errors="ignore")
                lines = [line for line in text.splitlines() if line.strip()]
                if "Traceback" in text or "Error" in text or "Exception" in text:
                    record["status"] = "error"
                    record["error_summary"] = lines[-1] if lines else "unknown error"
                else:
                    record["status"] = "running"
            else:
                record["status"] = "submitted"

            monitor_records.append(record)

        aggregate_path = state.run_dir / "generation_iteration_completed_candidates.json"
        write_json(aggregate_path, aggregate_candidates)
        reingest_manifest = {
            "run_id": state.run_dir.name,
            "completed_output_dirs": completed_outputs,
            "completed_submission_count": sum(1 for item in monitor_records if item.get("status") == "finished"),
            "error_submission_count": sum(1 for item in monitor_records if item.get("status") == "error"),
            "aggregate_candidates_path": str(aggregate_path),
            "aggregate_candidate_count": len(aggregate_candidates),
        }

        state.generation_iteration_monitor = monitor_records
        state.generation_iteration_reingest_manifest = reingest_manifest
        write_json(state.run_dir / "generation_iteration_monitor.json", monitor_records)
        write_json(state.run_dir / "generation_iteration_reingest_manifest.json", reingest_manifest)
        state.log(
            f"Generation iteration monitor scanned {len(monitor_records)} submissions and found {reingest_manifest['completed_submission_count']} completed outputs"
        )
        return state
