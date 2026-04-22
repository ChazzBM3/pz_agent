from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.chemistry.geometry import GeometryGenerationError, load_xyz_file, normalize_xyz_text, smiles_to_xyz
from pz_agent.io import ensure_dir, write_json
from pz_agent.state import RunState


CONTRACT_VERSION = "htvs.request_response.v1"


def _scheduler_settings(simulation_cfg: dict, candidate_id: str) -> dict:
    scheduler_cfg = dict(simulation_cfg.get("scheduler") or {})
    return {
        "system": scheduler_cfg.get("system", "slurm"),
        "partition": scheduler_cfg.get("partition", "xeon-p8"),
        "nodes": int(scheduler_cfg.get("nodes", 1) or 1),
        "time": str(scheduler_cfg.get("time", "00:10:00")),
        "mem_per_cpu": str(scheduler_cfg.get("mem_per_cpu", "2000")),
        "no_requeue": bool(scheduler_cfg.get("no_requeue", True)),
        "job_name": str(scheduler_cfg.get("job_name_prefix", "orca") ) + f"_{candidate_id}",
        "mpi_module": scheduler_cfg.get("mpi_module", "mpi/openmpi-4.1.8"),
        "orca_dir": scheduler_cfg.get("orca_dir", "/home/gridsan/groups/rgb_shared/software/orca/orca_6_0_0_linux_x86-64_shared_openmpi416"),
    }


def _remote_simulation_spec(item: dict, simulation_cfg: dict) -> dict:
    identity = dict(item.get("identity") or {})
    candidate_id = str(item.get("id") or item.get("candidate_id") or "job")
    return {
        "backend": simulation_cfg.get("backend", "htvs_supercloud"),
        "engine": simulation_cfg.get("engine", "orca"),
        "execution_mode": simulation_cfg.get("execution_mode", "remote"),
        "job_driver": simulation_cfg.get("job_driver", "direct_orca") ,
        "simulation_type": simulation_cfg.get("simulation_type", "geometry_optimization"),
        "opt_type": simulation_cfg.get("opt_type", "min"),
        "charge": int(simulation_cfg.get("charge", identity.get("charge", 0)) or 0),
        "spin_multiplicity": int(simulation_cfg.get("spin_multiplicity", 1) or 1),
        "functional": simulation_cfg.get("functional", "PBE"),
        "basis_set": simulation_cfg.get("basis_set", "def2-SVP"),
        "dispersion": simulation_cfg.get("dispersion", "D3"),
        "solvation": simulation_cfg.get("solvation", "CPCM"),
        "solvent": simulation_cfg.get("solvent", "water"),
        "special_option": simulation_cfg.get("special_option", "NOSOSCF"),
        "nprocs": int(simulation_cfg.get("nprocs", 1) or 1),
        "convergence_max_iterations": int(simulation_cfg.get("convergence_max_iterations", 200) or 200),
        "calculate_final_hessian": bool(simulation_cfg.get("calculate_final_hessian", False)),
        "calculator_settings": simulation_cfg.get("calculator_settings"),
        "optimizer_settings": simulation_cfg.get("optimizer_settings"),
        "remote_target": simulation_cfg.get("remote_target"),
        "scheduler": _scheduler_settings(simulation_cfg, candidate_id),
    }


def _requested_outputs(simulation_cfg: dict) -> list[str]:
    outputs = simulation_cfg.get("requested_outputs")
    if isinstance(outputs, list) and outputs:
        return [str(item) for item in outputs]
    return [
        "optimized_structure",
        "final_energy",
        "groundState.solvation_energy",
        "groundState.homo",
        "groundState.lumo",
        "groundState.homo_lumo_gap",
        "groundState.dipole_moment",
        "status",
    ]


def _tracking(record: dict, simulation: dict, state: RunState) -> dict:
    parameters = dict(simulation.get("parameters") or {})
    candidate_id = record.get("candidate_id") or record.get("id") or "unknown_candidate"
    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": f"simreq::{state.run_dir.name}::{candidate_id}",
        "job_id": None,
        "submission_id": None,
        "check_only": False,
        "status": "prepared",
        "execution_mode": simulation.get("execution_mode", "remote"),
        "remote_target": parameters.get("remote_target"),
        "poll": {
            "strategy": "submission_id_or_job_id",
            "status_values": ["prepared", "submitted", "running", "completed", "failed"],
        },
    }


def _resolve_geometry(record: dict) -> tuple[object, str]:
    geometry_block = dict(record.get("geometry") or {})
    xyz_text = geometry_block.get("xyz_text") or record.get("xyz_text")
    xyz_path = geometry_block.get("xyz_path") or record.get("xyz_path")
    if xyz_text:
        return normalize_xyz_text(str(xyz_text)), "provided_xyz_text"
    if xyz_path:
        return load_xyz_file(str(xyz_path)), "provided_xyz_path"

    smiles = str(record.get("canonical_smiles") or record.get("smiles") or "").strip()
    if not smiles:
        candidate_id = record.get("candidate_id") or "unknown_candidate"
        raise ValueError(f"Simulation handoff requires SMILES or XYZ geometry for candidate {candidate_id}")
    return smiles_to_xyz(smiles), "smiles_to_xyz"


def _write_orca_job_package(state: RunState, record: dict) -> dict:
    candidate_id = record.get("candidate_id") or "unknown_candidate"
    job_dir = state.run_dir / "orca_jobs" / candidate_id
    ensure_dir(job_dir)

    try:
        geometry, geometry_source = _resolve_geometry(record)
    except GeometryGenerationError as exc:
        raise ValueError(f"Failed to prepare XYZ for candidate {candidate_id}: {exc}") from exc

    structure_filename = "input_structure.xyz"
    structure_path = job_dir / structure_filename
    structure_path.write_text(geometry.xyz_text, encoding="utf-8")

    simulation = dict(record.get("simulation") or {})
    parameters = dict(simulation.get("parameters") or {})
    tracking = dict(record.get("tracking") or {})
    job_spec = {
        "contract_version": CONTRACT_VERSION,
        "request_type": "submit_simulation",
        "job_type": simulation.get("simulation_type"),
        "simulation_type": simulation.get("simulation_type"),
        "candidate_id": candidate_id,
        "run_id": state.run_dir.name,
        "structure_file": structure_filename,
        "job_driver": simulation.get("job_driver", "direct_orca"),
        "backend": simulation.get("backend", "htvs_supercloud"),
        "engine": simulation.get("engine", "orca"),
        "execution_mode": simulation.get("execution_mode", "remote"),
        "requested_outputs": simulation.get("requested_outputs") or [],
        "parameters": parameters,
        "scheduler": dict(simulation.get("scheduler") or {}),
        "operation": {
            "execution_mode": simulation.get("execution_mode", "remote"),
            "check_only": False,
            "job_id": tracking.get("job_id"),
            "submission_id": tracking.get("submission_id"),
            "remote_settings": {
                "target": parameters.get("remote_target"),
            },
        },
        "provenance": {
            "stable_identity_key": record.get("stable_identity_key"),
            "smiles": record.get("smiles"),
            "canonical_smiles": geometry.canonical_smiles,
            "selection_basis": record.get("selection_basis", {}),
            "remote_backend": simulation.get("backend"),
            "engine": simulation.get("engine"),
            "execution_mode": simulation.get("execution_mode"),
            "remote_target": parameters.get("remote_target"),
            "request_id": tracking.get("request_id"),
            "geometry_embed_method": geometry.embed_method,
            "geometry_source": geometry_source,
        },
    }
    write_json(job_dir / "orca_job.json", job_spec)
    return {
        "job_dir": str(job_dir),
        "structure_path": str(structure_path),
        "job_spec_path": str(job_dir / "orca_job.json"),
        "geometry_source": geometry_source,
        "geometry_embed_method": geometry.embed_method,
        "canonical_smiles": geometry.canonical_smiles,
        "atom_count": geometry.atom_count,
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

        remote_spec = _remote_simulation_spec(selected[0] if selected else {}, simulation_cfg)
        parameters = {
            key: value
            for key, value in remote_spec.items()
            if key not in {"backend", "engine", "execution_mode", "skill", "simulation_type", "scheduler"}
        }
        requested_outputs = _requested_outputs(simulation_cfg)

        queue_records: list[dict] = []
        for rank, item in enumerate(selected, start=1):
            identity = dict(item.get("identity") or {})
            ranking_rationale = dict(item.get("ranking_rationale") or {})
            per_item_spec = _remote_simulation_spec(item, simulation_cfg)
            per_item_parameters = {
                key: value
                for key, value in per_item_spec.items()
                if key not in {"backend", "engine", "execution_mode", "skill", "simulation_type", "scheduler"}
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
                "tracking": {},
                "simulation": {
                    "simulation_type": per_item_spec.get("simulation_type", "geometry_optimization"),
                    "compute_tier": simulation_cfg.get("compute_tier", "screening"),
                    "budget_tag": simulation_cfg.get("budget_tag", "default"),
                    "backend": per_item_spec.get("backend", "htvs_supercloud"),
                    "engine": per_item_spec.get("engine", "orca"),
                    "job_driver": per_item_spec.get("job_driver", "direct_orca"),
                    "execution_mode": per_item_spec.get("execution_mode", "remote"),
                    "parameters": per_item_parameters,
                    "requested_outputs": requested_outputs,
                    "scheduler": per_item_spec.get("scheduler", {}),
                },
                "dft": {
                    "job_type": per_item_spec.get("simulation_type", "geometry_optimization"),
                    "compute_tier": simulation_cfg.get("compute_tier", "screening"),
                    "budget_tag": simulation_cfg.get("budget_tag", "default"),
                    "orca": {
                        "backend": per_item_spec.get("backend", "htvs_supercloud"),
                        "execution_mode": per_item_spec.get("execution_mode", "remote"),
                        "job_driver": per_item_spec.get("job_driver", "direct_orca"),
                        **per_item_parameters,
                    },
                },
            }
            record["tracking"] = _tracking(record, record["simulation"], state)
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
            "contract_version": CONTRACT_VERSION,
            "simulation_defaults": {
                "simulation_type": remote_spec.get("simulation_type", "geometry_optimization"),
                "compute_tier": simulation_cfg.get("compute_tier", "screening"),
                "budget_tag": simulation_cfg.get("budget_tag", "default"),
                "backend": remote_spec.get("backend", "htvs_supercloud"),
                "engine": remote_spec.get("engine", "orca"),
                "job_driver": remote_spec.get("job_driver", "direct_orca"),
                "execution_mode": remote_spec.get("execution_mode", "remote"),
                "parameters": parameters,
                "requested_outputs": requested_outputs,
                "orca": {
                    "backend": remote_spec.get("backend", "htvs_supercloud"),
                    "execution_mode": remote_spec.get("execution_mode", "remote"),
                    "job_driver": remote_spec.get("job_driver", "direct_orca"),
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
