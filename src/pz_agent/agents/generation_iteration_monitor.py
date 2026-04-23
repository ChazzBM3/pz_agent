from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.chemistry.genmol_import import load_external_genmol_candidates
from pz_agent.io import write_json
from pz_agent.state import RunState


def _ssh_exists(remote_host: str, path: str) -> bool:
    inner = f"test -e {shlex.quote(path)} && echo yes || echo no"
    result = subprocess.run(
        f"ssh {shlex.quote(remote_host)} {shlex.quote(inner)}",
        shell=True,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0 and result.stdout.strip().endswith("yes")


def _ssh_read(remote_host: str, path: str) -> str:
    inner = f"cat {shlex.quote(path)}"
    result = subprocess.run(
        f"ssh {shlex.quote(remote_host)} {shlex.quote(inner)}",
        shell=True,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or f"failed to read remote path: {path}")
    return result.stdout


class GenerationIterationMonitorAgent(BaseAgent):
    name = "generation_iteration_monitor"

    def run(self, state: RunState) -> RunState:
        submissions = list(state.generation_iteration_submissions or [])
        monitor_records: list[dict] = []
        aggregate_candidates: list[dict] = []
        completed_outputs: list[str] = []

        remote_cache_dir = state.run_dir / "generation_iteration_remote_cache"
        remote_cache_dir.mkdir(parents=True, exist_ok=True)

        for submission in submissions:
            remote_host = str(submission.get("remote_host") or "").strip() or None
            output_dir_value = str(submission.get("output_dir") or "")
            log_path_value = str(submission.get("log_path") or "")
            output_dir = Path(output_dir_value)
            log_path = Path(log_path_value)
            payload_path_value = f"{output_dir_value.rstrip('/')}/lowest_energy_conformers.json"
            ranked_path_value = f"{output_dir_value.rstrip('/')}/sa_scores_ranked.json"
            payload_path = Path(payload_path_value)
            ranked_path = Path(ranked_path_value)
            record = {
                "candidate_id": submission.get("candidate_id"),
                "output_dir": output_dir_value,
                "log_path": log_path_value,
                "remote_host": remote_host,
                "status": "missing",
                "generated_count": 0,
                "error_summary": None,
                "payload_path": payload_path_value,
            }

            payload_exists = _ssh_exists(remote_host, payload_path_value) if remote_host else payload_path.exists()
            ranked_exists = _ssh_exists(remote_host, ranked_path_value) if remote_host else ranked_path.exists()
            log_exists = _ssh_exists(remote_host, log_path_value) if remote_host else log_path.exists()

            if payload_exists or ranked_exists:
                record["status"] = "finished"
                completed_outputs.append(output_dir_value)
                if payload_exists:
                    import_path = output_dir
                    if remote_host:
                        cached_payload = remote_cache_dir / f"{submission.get('candidate_id')}_lowest_energy_conformers.json"
                        cached_payload.write_text(_ssh_read(remote_host, payload_path_value), encoding="utf-8")
                        import_path = cached_payload
                    imported = load_external_genmol_candidates(import_path)
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
                elif ranked_exists:
                    data = json.loads(_ssh_read(remote_host, ranked_path_value) if remote_host else ranked_path.read_text())
                    if isinstance(data, list):
                        record["generated_count"] = len(data)
            elif log_exists:
                text = _ssh_read(remote_host, log_path_value) if remote_host else log_path.read_text(errors="ignore")
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
