from __future__ import annotations

import json
import subprocess
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
        "contract_version": item.get("contract_version") or response.get("contract_version") or tracking.get("contract_version") or "orca_slurm.request_response.v1",
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


def _artifact_path(queue_item: dict, artifact_name: str) -> Path | None:
    job_package = dict(queue_item.get("job_package") or {})
    job_dir = job_package.get("job_dir")
    if not job_dir:
        return None
    return Path(job_dir) / artifact_name


def _run_remote_cat(command: str) -> dict:
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "ok": result.returncode == 0,
    }


def _artifact_payloads(state: RunState, extract_cfg: dict) -> tuple[list[dict], Path | None]:
    payload: list[dict] = []
    remote_fetches: list[dict] = []
    seen_keys: set[tuple[str | None, str | None, str | None]] = set()
    transport = str(extract_cfg.get("transport", "")).strip().lower()
    remote_host_override = extract_cfg.get("remote_host")

    for queue_item in list(state.simulation_queue or []):
        result_path = _artifact_path(queue_item, "result.json")
        failure_path = _artifact_path(queue_item, "failure.json")
        if result_path and result_path.exists():
            item = read_json(result_path)
            if isinstance(item, dict):
                key = (item.get("candidate_id"), item.get("submission_id"), item.get("job_id"))
                if key not in seen_keys:
                    seen_keys.add(key)
                    payload.append(item)
            continue
        if failure_path and failure_path.exists():
            item = read_json(failure_path)
            if isinstance(item, dict):
                key = (item.get("candidate_id"), item.get("submission_id"), item.get("job_id"))
                if key not in seen_keys:
                    seen_keys.add(key)
                    payload.append(item)
            continue

        submission = dict(queue_item.get("submission") or {})
        staging = dict(submission.get("staging") or {})
        remote_job_dir = staging.get("remote_job_dir")
        remote_host = remote_host_override or staging.get("remote_host")
        remote_transport = transport or str(staging.get("transport") or "").strip().lower()
        if remote_transport != "ssh" or not remote_job_dir or not remote_host:
            continue

        for artifact_name in ("result.json", "failure.json"):
            command = f"ssh {remote_host} 'cat {remote_job_dir.rstrip('/')}/{artifact_name}'"
            fetched = _run_remote_cat(command)
            if not fetched.get("ok") or not str(fetched.get("stdout") or "").strip():
                remote_fetches.append({"artifact": artifact_name, **fetched})
                continue
            try:
                item = json.loads(fetched.get("stdout") or "{}")
            except Exception:
                remote_fetches.append({"artifact": artifact_name, **fetched, "ok": False, "stderr": "invalid json from remote artifact fetch"})
                continue
            if isinstance(item, dict):
                key = (item.get("candidate_id"), item.get("submission_id"), item.get("job_id"))
                remote_fetches.append({"artifact": artifact_name, **fetched})
                if key not in seen_keys:
                    seen_keys.add(key)
                    payload.append(item)
                break

    if payload:
        results_path = state.run_dir / "simulation_artifact_results.json"
        write_json(results_path, payload)
        write_json(state.run_dir / "simulation_remote_fetch_log.json", remote_fetches)
        return payload, results_path
    if remote_fetches:
        write_json(state.run_dir / "simulation_remote_fetch_log.json", remote_fetches)
    return [], None


class SimulationExtractAgent(BaseAgent):
    name = "simulation_extract"

    def run(self, state: RunState) -> RunState:
        extract_cfg = dict((state.config.get("simulation_extract", {}) or {}))
        payload, results_path = _artifact_payloads(state, extract_cfg)

        if not payload:
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
            normalized = _normalize_result_envelope(item, queue_item, results_path or (state.run_dir / "simulation_artifact_results.json"))
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
                    "deferred_rerun_plan": {
                        "policy": "deferred_manual_or_scheduled_rerun",
                        "orca_adjustments": {
                            "special_option": "",
                            "soscf_enabled": True,
                        },
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
        state.log(f"Simulation extract normalized {len(extractions)} completed result envelopes and logged {len(rerun_candidates)} deferred rerun candidates")
        return state
