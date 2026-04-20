from __future__ import annotations

from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.io import read_json, write_json
from pz_agent.state import RunState


def _normalize_result_envelope(item: dict, queue_item: dict, results_path: Path) -> dict:
    response = dict(item.get("response") or {}) if isinstance(item.get("response"), dict) else {}
    outputs = dict(item.get("outputs") or response.get("outputs") or {})
    tracking = dict(queue_item.get("tracking") or {})
    submission = dict(queue_item.get("submission") or {})
    simulation = dict(queue_item.get("simulation") or {})
    candidate_id = item.get("candidate_id") or response.get("candidate_id") or queue_item.get("candidate_id")
    return {
        "contract_version": item.get("contract_version") or response.get("contract_version") or tracking.get("contract_version") or "atomisticskills.request_response.v1",
        "request_type": item.get("request_type") or response.get("request_type") or "extract_simulation_result",
        "response_type": "result_envelope",
        "candidate_id": candidate_id,
        "submission_id": item.get("submission_id") or response.get("submission_id") or submission.get("submission_id") or tracking.get("submission_id"),
        "job_id": item.get("job_id") or response.get("job_id") or submission.get("job_id") or tracking.get("job_id"),
        "status": item.get("status") or response.get("status"),
        "backend": item.get("backend") or response.get("backend") or simulation.get("backend"),
        "engine": item.get("engine") or response.get("engine") or simulation.get("engine"),
        "simulation_type": item.get("simulation_type") or response.get("simulation_type") or simulation.get("simulation_type"),
        "remote_target": item.get("remote_target") or response.get("remote_target") or simulation.get("parameters", {}).get("remote_target"),
        "outputs": outputs,
        "raw_result": item,
        "provenance": {
            "results_path": str(results_path),
            "job_spec_path": (queue_item.get("job_package") or {}).get("job_spec_path"),
            "request_id": tracking.get("request_id"),
        },
    }


class SimulationExtractAgent(BaseAgent):
    name = "simulation_extract"

    def run(self, state: RunState) -> RunState:
        extract_cfg = dict((state.config.get("simulation_extract", {}) or {}))
        results_relpath = extract_cfg.get("results_path") or (state.config.get("validation_ingest", {}) or {}).get("results_path")
        if not results_relpath:
            state.simulation_extractions = []
            write_json(state.run_dir / "simulation_extractions.json", state.simulation_extractions)
            state.log("Simulation extract found no configured results path and emitted empty extraction results")
            return state

        results_path = Path(results_relpath)
        if not results_path.is_absolute():
            results_path = state.run_dir / results_path
        if not results_path.exists():
            raise FileNotFoundError(f"Simulation extract results file not found: {results_path}")

        payload = read_json(results_path)
        if not isinstance(payload, list):
            raise ValueError("Simulation extract expects a JSON list of result records")

        queue_by_candidate = {item.get("candidate_id"): item for item in (state.simulation_queue or []) if item.get("candidate_id")}
        checks_by_candidate = {item.get("candidate_id"): item for item in (state.simulation_checks or []) if item.get("candidate_id")}

        extractions: list[dict] = []
        failures: list[dict] = list(state.simulation_failures or [])
        rerun_candidates: list[dict] = []

        for item in payload:
            if not isinstance(item, dict):
                continue
            candidate_id = item.get("candidate_id") or (item.get("response") or {}).get("candidate_id")
            if not candidate_id:
                continue
            queue_item = dict(queue_by_candidate.get(candidate_id) or {})
            check_record = dict(checks_by_candidate.get(candidate_id) or {})
            normalized = _normalize_result_envelope(item, queue_item, results_path)
            normalized_status = str(normalized.get("status") or "").strip().lower()
            check_status = str(check_record.get("status") or "").strip().lower()
            check_authoritative = bool(check_record.get("authoritative"))

            if normalized_status == "failed" or check_status == "failed":
                failure = {
                    **normalized,
                    "response_type": "failure_envelope",
                    "failure_source": "simulation_extract",
                    "rerun_ready": True,
                    "rerun_bundle": {
                        "candidate_id": candidate_id,
                        "submission_id": normalized.get("submission_id"),
                        "job_spec_path": (queue_item.get("job_package") or {}).get("job_spec_path"),
                        "simulation": queue_item.get("simulation"),
                    },
                }
                failures.append(failure)
                rerun_candidates.append(failure)
                continue

            if check_authoritative and check_status not in {"completed", ""}:
                continue
            if normalized_status != "completed":
                continue
            extractions.append(normalized)

        state.simulation_extractions = extractions
        state.simulation_failures = failures
        write_json(state.run_dir / "simulation_extractions.json", extractions)
        write_json(state.run_dir / "simulation_failures.json", failures)
        write_json(state.run_dir / "simulation_rerun_candidates.json", rerun_candidates)
        state.log(f"Simulation extract normalized {len(extractions)} completed result envelopes and preserved {len(rerun_candidates)} rerun-ready failures")
        return state
