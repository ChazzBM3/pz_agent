from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.state import RunState


class DFTHandoffAgent(BaseAgent):
    name = "dft_handoff"

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

        budget = dict((state.config.get("dft", {}) or {}))
        max_candidates = int(budget.get("max_candidates", len(shortlist) or 0)) if shortlist else 0
        selected = shortlist[:max_candidates] if max_candidates > 0 else shortlist

        queue_records: list[dict] = []
        for rank, item in enumerate(selected, start=1):
            identity = dict(item.get("identity") or {})
            ranking_rationale = dict(item.get("ranking_rationale") or {})
            record = {
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
                "dft": {
                    "job_type": budget.get("job_type", "single_point_or_geometry_opt"),
                    "compute_tier": budget.get("compute_tier", "screening"),
                    "budget_tag": budget.get("budget_tag", "default"),
                },
            }
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
            "dft_defaults": {
                "job_type": budget.get("job_type", "single_point_or_geometry_opt"),
                "compute_tier": budget.get("compute_tier", "screening"),
                "budget_tag": budget.get("budget_tag", "default"),
            },
            "queue": queue_records,
        }

        state.dft_queue = queue_records
        state.dft_manifest = manifest
        write_json(state.run_dir / "dft_queue.json", queue_records)
        write_json(state.run_dir / "dft_manifest.json", manifest)
        state.log("DFT handoff packaged ranked candidates into queue and manifest artifacts")
        return state
