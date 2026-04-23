from __future__ import annotations

from pathlib import Path

import yaml

from pz_agent.agents.base import BaseAgent
from pz_agent.state import RunState


class GenerationIterationRecycleAgent(BaseAgent):
    name = "generation_iteration_recycle"

    def run(self, state: RunState) -> RunState:
        manifest = dict(state.generation_iteration_reingest_manifest or {})
        aggregate_path = manifest.get("aggregate_candidates_path")
        if not aggregate_path:
            state.log("Generation iteration recycle skipped because no aggregate candidates path was available")
            return state

        recycle_cfg = dict((state.config.get("generation", {}) or {}).get("recycle", {}) or {})
        next_stages = list(
            recycle_cfg.get(
                "next_stages",
                [
                    "library_designer",
                    "standardizer",
                    "surrogate_screen",
                    "knowledge_graph",
                    "ranker",
                ],
            )
        )
        next_run_dir = recycle_cfg.get("next_run_dir", f"{state.run_dir}/recycled_run")
        next_config = {
            "project": {
                "name": recycle_cfg.get("project_name", f"{state.run_dir.name}-recycled"),
            },
            "generation": {
                **dict(state.config.get("generation", {}) or {}),
                "external_genmol_path": aggregate_path,
            },
            "screening": dict(state.config.get("screening", {}) or {}),
            "pipeline": {
                **dict(state.config.get("pipeline", {}) or {}),
                "stages": next_stages,
            },
        }
        if state.config.get("critique") is not None:
            next_config["critique"] = dict(state.config.get("critique") or {})
        if state.config.get("search") is not None:
            next_config["search"] = dict(state.config.get("search") or {})
        if state.config.get("kg") is not None:
            next_config["kg"] = dict(state.config.get("kg") or {})

        recycle_manifest = {
            "run_id": state.run_dir.name,
            "aggregate_candidates_path": aggregate_path,
            "next_config_path": str(state.run_dir / "generation_iteration_next_run.yaml"),
            "next_run_dir": str(next_run_dir),
            "next_stages": next_stages,
            "completed_submission_count": manifest.get("completed_submission_count", 0),
        }

        (state.run_dir / "generation_iteration_next_run.yaml").write_text(
            yaml.safe_dump(next_config, sort_keys=False),
            encoding="utf-8",
        )
        (state.run_dir / "generation_iteration_recycle_manifest.json").write_text(
            __import__("json").dumps(recycle_manifest, indent=2),
            encoding="utf-8",
        )
        state.log("Generation iteration recycle wrote a next-run config bootstrapped from completed GenMol iteration outputs")
        return state
