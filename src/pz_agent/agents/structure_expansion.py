from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.retrieval.pubchem import expand_structure_with_pubchem
from pz_agent.state import RunState


class StructureExpansionAgent(BaseAgent):
    name = "structure_expansion"

    def run(self, state: RunState) -> RunState:
        cfg = state.config.get("structure_expansion", {}) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            state.log("Structure expansion skipped (disabled)")
            return state

        candidates = state.library_clean or []
        expansions: list[dict] = []
        similarity_threshold = int(cfg.get("similarity_threshold", 90))
        similarity_max_records = int(cfg.get("similarity_max_records", 5))
        substructure_max_records = int(cfg.get("substructure_max_records", 5))
        timeout = int(cfg.get("timeout", 20))

        for candidate in candidates:
            expanded = dict(candidate)
            expanded["structure_expansion"] = expand_structure_with_pubchem(
                candidate,
                similarity_threshold=similarity_threshold,
                similarity_max_records=similarity_max_records,
                substructure_max_records=substructure_max_records,
                timeout=timeout,
            )
            expansions.append(expanded)

        state.library_clean = expansions
        state.structure_expansion = [
            {
                "candidate_id": item.get("id"),
                **(item.get("structure_expansion") or {}),
            }
            for item in expansions
        ]
        out_path = state.run_dir / "structure_expansion.json"
        write_json(out_path, state.structure_expansion)
        state.log(f"Structure expansion completed for {len(expansions)} candidates")
        return state
