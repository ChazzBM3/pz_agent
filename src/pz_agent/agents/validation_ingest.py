from __future__ import annotations

from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.io import read_json, write_json
from pz_agent.state import RunState


VALIDATION_STATUS_MAP = {
    "converged": "completed",
    "completed": "completed",
    "ok": "completed",
    "failed": "failed",
    "error": "failed",
}


def _normalize_status(item_status: object, output_status: object) -> str:
    for raw in (output_status, item_status):
        text = str(raw or "").strip().lower()
        if text:
            return VALIDATION_STATUS_MAP.get(text, text)
    return "completed"


def _normalize_outputs(outputs: dict) -> dict:
    final_energy = outputs.get("final_energy")
    optimized_structure = outputs.get("optimized_structure")
    status = outputs.get("status")
    return {
        "final_energy": final_energy if isinstance(final_energy, (int, float)) else None,
        "optimized_structure": optimized_structure,
        "raw_status": status,
        "has_final_energy": isinstance(final_energy, (int, float)),
        "has_optimized_structure": bool(optimized_structure),
    }


def _build_quality_assessment(status: str, requested_outputs: list[str], normalized_outputs: dict) -> dict:
    available_outputs = {
        "final_energy": bool(normalized_outputs.get("has_final_energy")),
        "optimized_structure": bool(normalized_outputs.get("has_optimized_structure")),
        "status": bool(normalized_outputs.get("raw_status")),
    }
    missing_outputs = [name for name in requested_outputs if not available_outputs.get(name, False)]
    if status == "completed" and not missing_outputs:
        quality = "usable"
    elif status == "completed":
        quality = "partial"
    else:
        quality = "failed"
    return {
        "quality": quality,
        "requested_outputs_complete": not missing_outputs,
        "missing_requested_outputs": missing_outputs,
        "available_outputs": available_outputs,
    }


class ValidationIngestAgent(BaseAgent):
    name = "validation_ingest"

    def run(self, state: RunState) -> RunState:
        ingest_cfg = dict((state.config.get("validation_ingest", {}) or {}))
        results_relpath = ingest_cfg.get("results_path")
        if not results_relpath:
            state.validation = []
            write_json(state.run_dir / "validation_results.json", state.validation)
            state.log("Validation ingest found no configured results path and emitted empty validation results")
            return state

        results_path = Path(results_relpath)
        if not results_path.is_absolute():
            results_path = state.run_dir / results_path
        if not results_path.exists():
            raise FileNotFoundError(f"Validation ingest results file not found: {results_path}")

        payload = read_json(results_path)
        if not isinstance(payload, list):
            raise ValueError("Validation ingest expects a JSON list of result records")

        queue_by_candidate = {item.get("candidate_id"): item for item in (state.simulation_queue or []) if item.get("candidate_id")}
        prediction_by_candidate = {item.get("id"): item for item in (state.predictions or []) if item.get("id")}

        validation_records: list[dict] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            candidate_id = item.get("candidate_id")
            if not candidate_id:
                continue
            queue_item = dict(queue_by_candidate.get(candidate_id) or {})
            prediction = dict(prediction_by_candidate.get(candidate_id) or {})
            outputs = dict(item.get("outputs") or {})
            normalized_outputs = _normalize_outputs(outputs)
            normalized_status = _normalize_status(item.get("status"), outputs.get("status"))
            predicted_priority = prediction.get("predicted_priority")
            predicted_priority_adjusted = prediction.get("predicted_priority_literature_adjusted", predicted_priority)
            final_energy = normalized_outputs.get("final_energy")
            delta_priority = None
            delta_priority_adjusted = None
            if isinstance(final_energy, (int, float)) and isinstance(predicted_priority, (int, float)):
                delta_priority = final_energy - predicted_priority
            if isinstance(final_energy, (int, float)) and isinstance(predicted_priority_adjusted, (int, float)):
                delta_priority_adjusted = final_energy - predicted_priority_adjusted
            requested_outputs = list(queue_item.get("simulation", {}).get("requested_outputs") or [])
            quality_assessment = _build_quality_assessment(normalized_status, requested_outputs, normalized_outputs)
            validation_records.append(
                {
                    "candidate_id": candidate_id,
                    "status": normalized_status,
                    "submission_id": item.get("submission_id"),
                    "backend": item.get("backend") or queue_item.get("simulation", {}).get("backend"),
                    "engine": item.get("engine") or queue_item.get("simulation", {}).get("engine"),
                    "simulation_type": item.get("simulation_type") or queue_item.get("simulation", {}).get("simulation_type"),
                    "stable_identity_key": queue_item.get("stable_identity_key"),
                    "requested_outputs": requested_outputs,
                    "outputs": normalized_outputs,
                    "quality_assessment": quality_assessment,
                    "predicted_reference": {
                        "predicted_priority": predicted_priority,
                        "predicted_priority_literature_adjusted": predicted_priority_adjusted,
                        "predicted_solubility": prediction.get("predicted_solubility"),
                        "predicted_synthesizability": prediction.get("predicted_synthesizability"),
                    },
                    "comparison": {
                        "final_energy_minus_predicted_priority": delta_priority,
                        "final_energy_minus_predicted_priority_literature_adjusted": delta_priority_adjusted,
                        "optimized_structure_available": normalized_outputs.get("has_optimized_structure", False),
                    },
                    "provenance": {
                        "results_path": str(results_path),
                        "job_spec_path": (queue_item.get("job_package") or {}).get("job_spec_path"),
                        "remote_target": item.get("remote_target") or queue_item.get("simulation", {}).get("parameters", {}).get("remote_target"),
                        "raw_status": outputs.get("status"),
                    },
                }
            )

        state.validation = validation_records
        write_json(state.run_dir / "validation_results.json", validation_records)
        state.log(f"Validation ingest recorded {len(validation_records)} completed simulation results")
        return state
