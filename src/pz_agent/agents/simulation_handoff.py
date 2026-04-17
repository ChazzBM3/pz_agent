from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import ensure_dir, write_json
from pz_agent.state import RunState


def _orca_remote_spec(item: dict, simulation_cfg: dict) -> dict:
    identity = dict(item.get("identity") or {})
    return {
        "backend": simulation_cfg.get("backend", "atomisticskills_orca"),
        "engine": simulation_cfg.get("engine", "orca"),
        "execution_mode": simulation_cfg.get("execution_mode", "remote"),
        "skill": simulation_cfg.get("skill", "chem-dft-orca-optimization"),
        "simulation_type": simulation_cfg.get("simulation_type", "geometry_optimization"),
        "opt_type": simulation_cfg.get("opt_type", "min"),
        "charge": int(simulation_cfg.get("charge", identity.get("charge", 0)) or 0),
        "spin_multiplicity": int(simulation_cfg.get("spin_multiplicity", 1) or 1),
        "functional": simulation_cfg.get("functional", "PBE"),
        "basis_set": simulation_cfg.get("basis_set", "def2-SVP"),
        "dispersion": simulation_cfg.get("dispersion"),
        "solvation": simulation_cfg.get("solvation"),
        "solvent": simulation_cfg.get("solvent"),
        "special_option": simulation_cfg.get("special_option", "NOSOSCF"),
        "nprocs": int(simulation_cfg.get("nprocs", 1) or 1),
        "convergence_max_iterations": int(simulation_cfg.get("convergence_max_iterations", 200) or 200),
        "calculate_final_hessian": bool(simulation_cfg.get("calculate_final_hessian", False)),
        "calculator_settings": simulation_cfg.get("calculator_settings"),
        "optimizer_settings": simulation_cfg.get("optimizer_settings"),
        "remote_target": simulation_cfg.get("remote_target"),
    }


def _requested_outputs(simulation_cfg: dict) -> list[str]:
    outputs = simulation_cfg.get("requested_outputs")
    if isinstance(outputs, list) and outputs:
        return [str(item) for item in outputs]
    return ["optimized_structure", "final_energy", "status"]


def _write_orca_job_package(state: RunState, record: dict) -> dict:
    candidate_id = record.get("candidate_id") or "unknown_candidate"
    job_dir = state.run_dir / "orca_jobs" / candidate_id
    ensure_dir(job_dir)

    structure_filename = "input_structure.xyz"
    structure_path = job_dir / structure_filename
    structure_path.write_text(f"1\n{candidate_id}\nC 0.0 0.0 0.0\n", encoding="utf-8")

    simulation = dict(record.get("simulation") or {})
    parameters = dict(simulation.get("parameters") or {})
    job_spec = {
        "job_type": simulation.get("simulation_type"),
        "simulation_type": simulation.get("simulation_type"),
        "candidate_id": candidate_id,
        "run_id": state.run_dir.name,
        "structure_file": structure_filename,
        "orca_skill": simulation.get("skill", "chem-dft-orca-optimization"),
        "backend": simulation.get("backend", "atomisticskills_orca"),
        "engine": simulation.get("engine", "orca"),
        "execution_mode": simulation.get("execution_mode", "remote"),
        "requested_outputs": simulation.get("requested_outputs") or [],
        "parameters": parameters,
        "provenance": {
            "stable_identity_key": record.get("stable_identity_key"),
            "smiles": record.get("smiles"),
            "selection_basis": record.get("selection_basis", {}),
            "remote_backend": simulation.get("backend"),
            "engine": simulation.get("engine"),
            "execution_mode": simulation.get("execution_mode"),
            "remote_target": parameters.get("remote_target"),
        },
    }
    write_json(job_dir / "orca_job.json", job_spec)
    return {
        "job_dir": str(job_dir),
        "structure_path": str(structure_path),
        "job_spec_path": str(job_dir / "orca_job.json"),
    }


class SimulationHandoffAgent(BaseAgent):
    name = "simulation_handoff"

    def run(self, state: RunState) -> RunState:
        shortlist = list(state.shortlist or [])
        shortlist.sort(
            key=lambda item: (
                -float(item.get("predicted_priority_literature_adjusted", item.get("predicted_priority", 0.0)) or 0.0),
                -float(item.get("ranking_rationale", {}).get("belief_state", {}).get("transferability_score", 0.0) or 0.0),
                -float(item.get("ranking_rationale", {}).get("belief_state", {}).get("simulation_support", 0.0) or 0.0),
                item.get("id", ""),
            )
        )

        simulation_cfg = dict((state.config.get("simulation", {}) or {}))
        max_candidates = int(simulation_cfg.get("max_candidates", len(shortlist) or 0)) if shortlist else 0
        selected = shortlist[:max_candidates] if max_candidates > 0 else shortlist

        remote_spec = _orca_remote_spec(selected[0] if selected else {}, simulation_cfg)
        parameters = {
            key: value
            for key, value in remote_spec.items()
            if key not in {"backend", "engine", "execution_mode", "skill", "simulation_type"}
        }
        requested_outputs = _requested_outputs(simulation_cfg)

        queue_records: list[dict] = []
        for rank, item in enumerate(selected, start=1):
            identity = dict(item.get("identity") or {})
            ranking_rationale = dict(item.get("ranking_rationale") or {})
            per_item_spec = _orca_remote_spec(item, simulation_cfg)
            per_item_parameters = {
                key: value
                for key, value in per_item_spec.items()
                if key not in {"backend", "engine", "execution_mode", "skill", "simulation_type"}
            }
            record = {
                "id": item.get("id"),
                "queue_rank": rank,
                "candidate_id": item.get("id"),
                "smiles": item.get("smiles"),
                "canonical_smiles": identity.get("canonical_smiles") or item.get("canonical_smiles"),
                "inchikey": identity.get("inchikey"),
                "stable_identity_key": item.get("stable_identity_key") or identity.get("stable_identity_key"),
                "predicted_priority": item.get("predicted_priority"),
                "predicted_priority_literature_adjusted": item.get("predicted_priority_literature_adjusted", item.get("predicted_priority")),
                "literature_adjustment": item.get("literature_adjustment", 0.0),
                "selection_basis": {
                    "primary_score": item.get("predicted_priority_literature_adjusted", item.get("predicted_priority")),
                    "measurement_context": ranking_rationale.get("measurement_summary"),
                    "measurement_values": ranking_rationale.get("measurement_values"),
                    "literature_adjustment": ranking_rationale.get("literature_adjustment", []),
                    "evidence_sources": ranking_rationale.get("evidence_sources", {}),
                    "belief_state": ranking_rationale.get("belief_state", {}),
                },
                "status": "queued",
                "simulation": {
                    "simulation_type": per_item_spec.get("simulation_type", "geometry_optimization"),
                    "compute_tier": simulation_cfg.get("compute_tier", "screening"),
                    "budget_tag": simulation_cfg.get("budget_tag", "default"),
                    "backend": per_item_spec.get("backend", "atomisticskills_orca"),
                    "engine": per_item_spec.get("engine", "orca"),
                    "skill": per_item_spec.get("skill", "chem-dft-orca-optimization"),
                    "execution_mode": per_item_spec.get("execution_mode", "remote"),
                    "parameters": per_item_parameters,
                    "requested_outputs": requested_outputs,
                },
                "dft": {
                    "job_type": per_item_spec.get("simulation_type", "geometry_optimization"),
                    "compute_tier": simulation_cfg.get("compute_tier", "screening"),
                    "budget_tag": simulation_cfg.get("budget_tag", "default"),
                    "orca": {
                        "backend": per_item_spec.get("backend", "atomisticskills_orca"),
                        "execution_mode": per_item_spec.get("execution_mode", "remote"),
                        "skill": per_item_spec.get("skill", "chem-dft-orca-optimization"),
                        **per_item_parameters,
                    },
                },
            }
            record["job_package"] = _write_orca_job_package(state, record)
            queue_records.append(record)

        manifest = {
            "run_id": state.run_dir.name,
            "queue_size": len(queue_records),
            "selection_policy": {
                "sort_keys": [
                    "predicted_priority_literature_adjusted",
                    "belief_state.transferability_score",
                    "belief_state.simulation_support",
                    "candidate_id",
                ],
                "max_candidates": max_candidates,
            },
            "simulation_defaults": {
                "simulation_type": remote_spec.get("simulation_type", "geometry_optimization"),
                "compute_tier": simulation_cfg.get("compute_tier", "screening"),
                "budget_tag": simulation_cfg.get("budget_tag", "default"),
                "backend": remote_spec.get("backend", "atomisticskills_orca"),
                "engine": remote_spec.get("engine", "orca"),
                "skill": remote_spec.get("skill", "chem-dft-orca-optimization"),
                "execution_mode": remote_spec.get("execution_mode", "remote"),
                "parameters": parameters,
                "requested_outputs": requested_outputs,
                "orca": {
                    "backend": remote_spec.get("backend", "atomisticskills_orca"),
                    "execution_mode": remote_spec.get("execution_mode", "remote"),
                    "skill": remote_spec.get("skill", "chem-dft-orca-optimization"),
                    **parameters,
                },
            },
            "queue": queue_records,
        }

        state.simulation_queue = queue_records
        state.simulation_manifest = manifest
        write_json(state.run_dir / "simulation_queue.json", queue_records)
        write_json(state.run_dir / "simulation_manifest.json", manifest)
        state.log("Simulation handoff packaged ranked candidates into ORCA-ready remote queue, manifest, and job artifacts")
        return state
