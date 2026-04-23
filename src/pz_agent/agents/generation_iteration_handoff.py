from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.state import RunState


CONTRACT_VERSION = "genmol.iteration_request.v1"


def _generation_defaults(config: dict) -> dict:
    generation_cfg = dict(config.get("generation", {}) or {})
    prompts = dict(generation_cfg.get("prompts", {}) or {})
    return {
        "engine": generation_cfg.get("engine", "genmol_external"),
        "strategy": generation_cfg.get("strategy", "genmol_conformer_generation"),
        "objective": prompts.get("objective"),
        "num_generations": int(generation_cfg.get("num_generations", 100) or 100),
        "num_conformers": int(generation_cfg.get("num_conformers", 100) or 100),
        "selection_top_k": int(generation_cfg.get("iteration_top_k", 5) or 5),
    }


class GenerationIterationHandoffAgent(BaseAgent):
    name = "generation_iteration_handoff"

    def run(self, state: RunState) -> RunState:
        defaults = _generation_defaults(state.config)
        iteration_actions = [
            item for item in (state.action_queue or [])
            if item.get("action_type") == "generation_iteration"
        ]

        deduped: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for action in sorted(
            iteration_actions,
            key=lambda item: (
                -float(item.get("priority", 0.0) or 0.0),
                str(item.get("candidate_id") or ""),
            ),
        ):
            payload = dict(action.get("payload") or {})
            candidate = dict(payload.get("candidate") or {})
            protocol = dict(payload.get("protocol") or {})
            stable_identity_key = str(candidate.get("stable_identity_key") or "")
            key = (stable_identity_key or str(action.get("candidate_id") or ""), str(protocol.get("source_path") or ""))
            if key in seen:
                continue
            seen.add(key)

            protocol_metadata = dict(protocol.get("metadata") or {})
            record = {
                "candidate_id": action.get("candidate_id"),
                "seed_candidate_id": action.get("candidate_id"),
                "smiles": candidate.get("smiles"),
                "stable_identity_key": candidate.get("stable_identity_key"),
                "priority": action.get("priority"),
                "source": action.get("source"),
                "proposal_type": action.get("proposal_type"),
                "proposal_reason": action.get("proposal_reason"),
                "critic_reason": action.get("critic_reason"),
                "generation_request": {
                    "contract_version": CONTRACT_VERSION,
                    "engine": protocol.get("engine") or defaults["engine"],
                    "strategy": protocol_metadata.get("mode") or defaults["strategy"],
                    "objective": protocol_metadata.get("objective") or defaults["objective"],
                    "num_generations": int(protocol_metadata.get("num_generations_requested") or defaults["num_generations"]),
                    "num_conformers": int(protocol_metadata.get("num_conformers_per_molecule") or defaults["num_conformers"]),
                    "source_path": protocol.get("source_path"),
                    "seed_batch_count": protocol.get("count"),
                    "bridge_dimensions": list(protocol_metadata.get("bridge_dimensions", []) or payload.get("bridge_principles", []) or []),
                    "generation_priors": dict(protocol_metadata.get("generation_priors") or {}),
                },
                "selection_basis": dict(payload.get("selection_basis") or {}),
                "history": dict(payload.get("history") or {}),
                "bridge_case_id": payload.get("bridge_case_id"),
                "generation_batch_ids": list(payload.get("generation_batch_ids", []) or []),
                "status": "queued",
            }
            deduped.append(record)

        top_k = defaults["selection_top_k"]
        queue_records = deduped[:top_k]
        input_records = [
            {
                "id": record["candidate_id"],
                "smiles": record["smiles"],
                "priority": record["priority"],
                "bridge_dimensions": record["generation_request"].get("bridge_dimensions", []),
                "selection_basis": record.get("selection_basis", {}),
            }
            for record in queue_records
            if record.get("smiles")
        ]

        manifest = {
            "contract_version": CONTRACT_VERSION,
            "run_id": state.run_dir.name,
            "queue_size": len(queue_records),
            "selection_policy": {
                "source_action_type": "generation_iteration",
                "sort_keys": ["priority", "candidate_id"],
                "max_candidates": top_k,
            },
            "generation_defaults": defaults,
            "queue": queue_records,
            "input_records": input_records,
        }

        state.generation_iteration_queue = queue_records
        state.generation_iteration_manifest = manifest
        write_json(state.run_dir / "generation_iteration_queue.json", queue_records)
        write_json(state.run_dir / "generation_iteration_manifest.json", manifest)
        write_json(state.run_dir / "genmol_iteration_input.json", input_records)
        state.log("Generation iteration handoff packaged KG-selected candidates into a GenMol iteration queue and manifest")
        return state
