from __future__ import annotations

import shlex
from pathlib import Path

from pz_agent.agents.base import BaseAgent
from pz_agent.io import ensure_dir, write_json
from pz_agent.state import RunState


DEFAULT_GENMOL_SCRIPT = ".agents/skills/ml-generative-genmol/scripts/generate_functionalized_lowest_conformers.py"


def _submit_config(config: dict) -> dict:
    generation_cfg = dict(config.get("generation", {}) or {})
    submit_cfg = dict(generation_cfg.get("submit", {}) or {})
    return {
        "atomistic_root": str(submit_cfg.get("atomistic_root", "~/AtomisticSkills")),
        "conda_init": str(submit_cfg.get("conda_init", "~/miniconda3/etc/profile.d/conda.sh")),
        "conda_env": str(submit_cfg.get("conda_env", "genmol-agent")),
        "script_path": str(submit_cfg.get("script_path", DEFAULT_GENMOL_SCRIPT)),
        "runs_root": str(submit_cfg.get("runs_root", "research/genmol_iteration_runs")),
        "launcher_mode": str(submit_cfg.get("launcher_mode", "serial_manifest")),
        "python_bin": str(submit_cfg.get("python_bin", "python")),
        "extra_env": dict(submit_cfg.get("extra_env") or {}),
    }


def _shell_prefix(cfg: dict) -> str:
    parts = [
        f"source {shlex.quote(cfg['conda_init'])}",
        f"conda activate {shlex.quote(cfg['conda_env'])}",
        f"cd {shlex.quote(cfg['atomistic_root'])}",
    ]
    env_parts = [f"{key}={shlex.quote(str(value))}" for key, value in sorted((cfg.get("extra_env") or {}).items())]
    if env_parts:
        parts.append("export " + " ".join(env_parts))
    return " && ".join(parts)


class GenerationIterationSubmitAgent(BaseAgent):
    name = "generation_iteration_submit"

    def run(self, state: RunState) -> RunState:
        manifest = dict(state.generation_iteration_manifest or {})
        queue = list(state.generation_iteration_queue or manifest.get("queue") or [])
        cfg = _submit_config(state.config)
        run_root = Path(state.run_dir) / cfg["runs_root"]
        ensure_dir(run_root)

        shell_prefix = _shell_prefix(cfg)
        submissions: list[dict] = []
        script_lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]

        for idx, record in enumerate(queue, start=1):
            candidate_id = str(record.get("candidate_id") or f"candidate_{idx:03d}")
            smiles = str(record.get("smiles") or "").strip()
            if not smiles:
                continue
            request = dict(record.get("generation_request") or {})
            output_dir = run_root / f"{idx:02d}_{candidate_id}"
            log_path = output_dir.with_suffix(".log")
            command = (
                f"mkdir -p {shlex.quote(str(output_dir))} && "
                f"{shell_prefix} && "
                f"{shlex.quote(cfg['python_bin'])} {shlex.quote(cfg['script_path'])} "
                f"--smiles {shlex.quote(smiles)} "
                f"--num-generations {int(request.get('num_generations', 100) or 100)} "
                f"--num-conformers {int(request.get('num_conformers', 100) or 100)} "
                f"--output-dir {shlex.quote(str(output_dir))}"
            )
            submission = {
                "candidate_id": candidate_id,
                "smiles": smiles,
                "priority": record.get("priority"),
                "output_dir": str(output_dir),
                "log_path": str(log_path),
                "launcher_mode": cfg["launcher_mode"],
                "status": "prepared",
                "command": command,
                "generation_request": request,
                "selection_basis": record.get("selection_basis", {}),
            }
            submissions.append(submission)
            script_lines.append(f"echo START {shlex.quote(candidate_id)}")
            script_lines.append(f"{command} > {shlex.quote(str(log_path))} 2>&1")
            script_lines.append(f"echo DONE {shlex.quote(candidate_id)}")
            script_lines.append("")

        launch_manifest = {
            "contract_version": "genmol.iteration_launch.v1",
            "run_id": state.run_dir.name,
            "launcher_mode": cfg["launcher_mode"],
            "runs_root": str(run_root),
            "atomistic_root": cfg["atomistic_root"],
            "script_path": cfg["script_path"],
            "submission_count": len(submissions),
            "submissions": submissions,
        }

        launcher_script_path = state.run_dir / "launch_genmol_iteration.sh"
        launcher_script_path.write_text("\n".join(script_lines) + "\n", encoding="utf-8")
        state.generation_iteration_submissions = submissions
        write_json(state.run_dir / "generation_iteration_launch_manifest.json", launch_manifest)
        write_json(state.run_dir / "generation_iteration_submissions.json", submissions)
        state.log("Generation iteration submit prepared Grimm/GenMol launch manifest and shell script for queued iteration requests")
        return state
