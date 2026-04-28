from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from typing import Any

from pz_agent.agents.base import BaseAgent
from pz_agent.agents.generation_iteration_execute import GenerationIterationExecuteAgent
from pz_agent.agents.generation_iteration_handoff import GenerationIterationHandoffAgent
from pz_agent.agents.generation_iteration_monitor import GenerationIterationMonitorAgent
from pz_agent.agents.generation_iteration_recycle import GenerationIterationRecycleAgent
from pz_agent.agents.generation_iteration_submit import GenerationIterationSubmitAgent
from pz_agent.agents.graph_expansion import GraphExpansionAgent
from pz_agent.agents.knowledge_graph import KnowledgeGraphAgent
from pz_agent.agents.library_designer import LibraryDesignerAgent
from pz_agent.agents.ranker import RankerAgent
from pz_agent.agents.standardizer import StandardizerAgent
from pz_agent.agents.surrogate_screen import SurrogateScreenAgent
from pz_agent.generation_loop_controls import build_loop_controls
from pz_agent.io import ensure_dir, read_json, write_json
from pz_agent.state import RunState


AGENT_MAP = {
    "library_designer": LibraryDesignerAgent,
    "standardizer": StandardizerAgent,
    "surrogate_screen": SurrogateScreenAgent,
    "knowledge_graph": KnowledgeGraphAgent,
    "ranker": RankerAgent,
    "graph_expansion": GraphExpansionAgent,
    "generation_iteration_handoff": GenerationIterationHandoffAgent,
    "generation_iteration_submit": GenerationIterationSubmitAgent,
    "generation_iteration_execute": GenerationIterationExecuteAgent,
    "generation_iteration_monitor": GenerationIterationMonitorAgent,
    "generation_iteration_recycle": GenerationIterationRecycleAgent,
}


class GenerationIterationLoopAgent(BaseAgent):
    name = "generation_iteration_loop"

    @classmethod
    def _resolve_loop_controls(cls, config: dict[str, Any], action_queue: list[dict[str, Any]] | None) -> dict[str, Any]:
        controls = {"source": "user_config", **build_loop_controls(config=config)}

        generation_actions = [
            item for item in (action_queue or [])
            if item.get("action_type") == "generation_iteration"
        ]
        if not generation_actions:
            return controls

        ranked_actions = sorted(
            generation_actions,
            key=lambda item: (-float(item.get("priority", 0.0) or 0.0), str(item.get("candidate_id") or "")),
        )
        for action in ranked_actions:
            payload = dict(action.get("payload") or {})
            raw_controls = dict(payload.get("loop_controls") or {})
            if not raw_controls:
                continue
            controls = {
                "source": "agent_payload",
                "candidate_id": action.get("candidate_id"),
                **build_loop_controls(
                    config=config,
                    primary_objectives=raw_controls.get("primary_objectives"),
                    convergence_tolerance=raw_controls.get("convergence_tolerance"),
                    taper_min_improvement=raw_controls.get("taper_min_improvement"),
                ),
            }
            break
        return controls

    def run(self, state: RunState) -> RunState:
        loop_cfg = dict((state.config.get("generation", {}) or {}).get("loop", {}) or {})
        max_rounds = int(loop_cfg.get("max_rounds", 3) or 3)
        analysis_stages = list(
            loop_cfg.get(
                "analysis_stages",
                [
                    "library_designer",
                    "standardizer",
                    "surrogate_screen",
                    "knowledge_graph",
                    "ranker",
                    "graph_expansion",
                ],
            )
        )
        iteration_stages = list(
            loop_cfg.get(
                "iteration_stages",
                [
                    "generation_iteration_handoff",
                    "generation_iteration_submit",
                    "generation_iteration_execute",
                    "generation_iteration_monitor",
                    "generation_iteration_recycle",
                ],
            )
        )
        loop_root = state.run_dir / "generation_iteration_loop"
        ensure_dir(loop_root)
        resume_iteration_run_dir = loop_cfg.get("resume_iteration_run_dir")
        resume_iteration_stages = list(
            loop_cfg.get(
                "resume_iteration_stages",
                [
                    "generation_iteration_monitor",
                    "generation_iteration_recycle",
                ],
            )
        )
        previous_top = self._top_metrics(state)
        current_action_queue = list(state.action_queue or [])
        loop_controls = self._resolve_loop_controls(state.config, current_action_queue)
        primary_objectives = list(loop_controls["primary_objectives"])
        convergence_tol = dict(loop_controls["convergence_tolerance"])
        taper_tol = dict(loop_controls["taper_min_improvement"])
        summary: dict[str, Any] = {
            "max_rounds": max_rounds,
            "analysis_stages": analysis_stages,
            "iteration_stages": iteration_stages,
            "resume_iteration_run_dir": str(resume_iteration_run_dir) if resume_iteration_run_dir else None,
            "resume_iteration_stages": resume_iteration_stages if resume_iteration_run_dir else None,
            "loop_controls": loop_controls,
            "baseline_top": previous_top,
            "rounds": [],
            "stop_reason": None,
            "completed_rounds": 0,
        }

        has_bootstrap_seed = bool(state.ranked)
        summary["bootstrap_seed_available"] = has_bootstrap_seed

        if not current_action_queue and not has_bootstrap_seed and not resume_iteration_run_dir:
            summary["stop_reason"] = "missing_action_queue"
            state.generation_iteration_loop_summary = summary
            write_json(state.run_dir / "generation_iteration_loop_summary.json", summary)
            state.log("Generation iteration loop skipped because there was no action queue and no ranked candidate was available to bootstrap the first iteration")
            return state

        last_analysis_state: RunState | None = None
        last_iteration_state: RunState | None = None

        for round_index in range(1, max_rounds + 1):
            resume_mode = bool(resume_iteration_run_dir) and round_index == 1
            iteration_run_dir = Path(resume_iteration_run_dir) if resume_mode else loop_root / f"round_{round_index:02d}_iteration"
            iteration_state = RunState(
                config=deepcopy(state.config),
                run_dir=iteration_run_dir,
                action_queue=deepcopy(current_action_queue),
                ranked=deepcopy(last_analysis_state.ranked if last_analysis_state else state.ranked),
            )
            ensure_dir(iteration_state.run_dir)
            if resume_mode:
                self._load_resume_iteration_state(iteration_state)
            iteration_state.log(f"Starting generation iteration loop round {round_index}")
            stages_to_run = resume_iteration_stages if resume_mode else iteration_stages
            for stage_name in stages_to_run:
                agent_cls = AGENT_MAP[stage_name]
                iteration_state = agent_cls(config=iteration_state.config).run(iteration_state)

            last_iteration_state = iteration_state
            reingest_manifest = dict(iteration_state.generation_iteration_reingest_manifest or {})
            aggregate_candidates_path = reingest_manifest.get("aggregate_candidates_path")
            completed_submission_count = int(reingest_manifest.get("completed_submission_count", 0) or 0)
            waiting_submission_count = int(reingest_manifest.get("waiting_submission_count", 0) or 0)
            monitor_statuses = sorted({str(item.get("status") or "unknown") for item in (iteration_state.generation_iteration_monitor or [])})

            round_summary: dict[str, Any] = {
                "round_index": round_index,
                "iteration_run_dir": str(iteration_state.run_dir),
                "resume_mode": resume_mode,
                "completed_submission_count": completed_submission_count,
                "waiting_submission_count": waiting_submission_count,
                "monitor_statuses": monitor_statuses,
                "status_counts": reingest_manifest.get("status_counts", {}),
                "aggregate_candidates_path": aggregate_candidates_path,
                "analysis_run_dir": None,
                "top_candidate": None,
                "delta": None,
                "stop_reason": None,
            }

            if not aggregate_candidates_path or completed_submission_count <= 0:
                awaiting_remote_outputs = waiting_submission_count > 0 or bool(reingest_manifest.get("awaiting_remote_outputs"))
                stop_reason = "awaiting_remote_outputs" if awaiting_remote_outputs else "no_completed_outputs"
                round_summary["stop_reason"] = stop_reason
                round_summary["resume_iteration_run_dir"] = str(iteration_state.run_dir) if awaiting_remote_outputs else None
                round_summary["resume_hint"] = (
                    "Re-run this loop after remote GenMol outputs finish; monitor -> recycle -> analysis can resume from the recorded iteration run directory."
                    if awaiting_remote_outputs
                    else None
                )
                summary["rounds"].append(round_summary)
                summary["stop_reason"] = stop_reason
                if awaiting_remote_outputs:
                    summary["awaiting_remote_outputs"] = True
                    summary["waiting_round_index"] = round_index
                    summary["resume_iteration_run_dir"] = str(iteration_state.run_dir)
                    summary["waiting_submission_count"] = waiting_submission_count
                    summary["waiting_statuses"] = monitor_statuses
                break

            analysis_state = RunState(
                config=deepcopy(state.config),
                run_dir=loop_root / f"round_{round_index:02d}_analysis",
            )
            ensure_dir(analysis_state.run_dir)
            generation_cfg = dict(analysis_state.config.get("generation", {}) or {})
            generation_cfg["external_genmol_path"] = aggregate_candidates_path
            analysis_state.config["generation"] = generation_cfg
            for stage_name in analysis_stages:
                agent_cls = AGENT_MAP[stage_name]
                analysis_state = agent_cls(config=analysis_state.config).run(analysis_state)

            last_analysis_state = analysis_state
            current_action_queue = list(analysis_state.action_queue or [])
            loop_controls = self._resolve_loop_controls(state.config, current_action_queue)
            primary_objectives = list(loop_controls["primary_objectives"])
            convergence_tol = dict(loop_controls["convergence_tolerance"])
            taper_tol = dict(loop_controls["taper_min_improvement"])
            current_top = self._top_metrics(analysis_state)
            round_summary["analysis_run_dir"] = str(analysis_state.run_dir)
            round_summary["top_candidate"] = current_top
            round_summary["next_action_queue_count"] = len(current_action_queue)
            round_summary["loop_controls"] = loop_controls

            stop_reason = None
            delta = self._metric_delta(previous_top, current_top)
            if delta is not None:
                round_summary["delta"] = delta
                if self._all_primary_metrics_worsened(delta, taper_tol, primary_objectives):
                    stop_reason = (
                        "both_metrics_worsened"
                        if set(primary_objectives) == {"solubility", "synthesizability"} and len(primary_objectives) == 2
                        else "primary_objectives_worsened"
                    )
                elif self._is_converged(delta, convergence_tol, primary_objectives):
                    stop_reason = "converged"

            round_summary["stop_reason"] = stop_reason
            summary["rounds"].append(round_summary)
            summary["completed_rounds"] = round_index
            previous_top = current_top

            if stop_reason is not None:
                summary["stop_reason"] = stop_reason
                break
        else:
            summary["completed_rounds"] = max_rounds
            summary["stop_reason"] = "max_rounds_reached"

        if summary["stop_reason"] is None:
            summary["stop_reason"] = "max_rounds_reached"

        child_state = last_analysis_state or last_iteration_state
        if child_state is not None:
            self._merge_child_state(state, child_state)
        state.generation_iteration_loop_summary = summary
        write_json(state.run_dir / "generation_iteration_loop_summary.json", summary)
        state.log(
            f"Generation iteration loop completed {summary['completed_rounds']} rounds and stopped because {summary['stop_reason']}"
        )
        return state

    @staticmethod
    def _metric_delta(previous_top: dict[str, Any] | None, current_top: dict[str, Any] | None) -> dict[str, Any] | None:
        if not previous_top or not current_top:
            return None
        previous_sol = previous_top.get("predicted_solubility")
        current_sol = current_top.get("predicted_solubility")
        previous_syn = previous_top.get("predicted_synthesizability")
        current_syn = current_top.get("predicted_synthesizability")
        if previous_sol is None or current_sol is None or previous_syn is None or current_syn is None:
            return None
        return {
            "solubility": float(current_sol) - float(previous_sol),
            "synthesizability": float(current_syn) - float(previous_syn),
        }

    @staticmethod
    def _primary_objectives(config: dict[str, Any]) -> list[str]:
        objectives = [
            str(item)
            for item in ((config.get("screening", {}) or {}).get("primary_objectives", []) or [])
            if str(item) in {"solubility", "synthesizability"}
        ]
        return objectives or ["solubility", "synthesizability"]

    @staticmethod
    def _is_converged(delta: dict[str, Any], tolerance: dict[str, float], primary_objectives: list[str]) -> bool:
        return all(
            abs(float(delta.get(metric, 0.0))) <= tolerance[metric]
            for metric in primary_objectives
        )

    @staticmethod
    def _all_primary_metrics_worsened(delta: dict[str, Any], tolerance: dict[str, float], primary_objectives: list[str]) -> bool:
        return all(
            float(delta.get(metric, 0.0)) < -abs(float(tolerance[metric]))
            for metric in primary_objectives
        )

    @staticmethod
    def _top_metrics(state: RunState) -> dict[str, Any] | None:
        if not state.ranked:
            return None
        top = dict(state.ranked[0] or {})
        return {
            "candidate_id": top.get("id"),
            "smiles": top.get("smiles"),
            "predicted_priority": top.get("predicted_priority_literature_adjusted", top.get("predicted_priority")),
            "predicted_solubility": top.get("predicted_solubility"),
            "predicted_synthesizability": top.get("predicted_synthesizability"),
        }

    @staticmethod
    def _load_resume_iteration_state(state: RunState) -> None:
        submissions_path = state.run_dir / "generation_iteration_submissions.json"
        if submissions_path.exists():
            state.generation_iteration_submissions = list(read_json(submissions_path) or [])
        manifest_path = state.run_dir / "generation_iteration_manifest.json"
        if manifest_path.exists():
            state.generation_iteration_manifest = dict(read_json(manifest_path) or {})
            if state.generation_iteration_queue is None:
                state.generation_iteration_queue = list(state.generation_iteration_manifest.get("queue") or [])
        queue_path = state.run_dir / "generation_iteration_queue.json"
        if queue_path.exists():
            state.generation_iteration_queue = list(read_json(queue_path) or [])
        execution_path = state.run_dir / "generation_iteration_execution.json"
        if execution_path.exists():
            state.generation_iteration_execution = list(read_json(execution_path) or [])
        state.log(f"Loaded resumable generation iteration state from {state.run_dir}")

    @staticmethod
    def _merge_child_state(parent: RunState, child: RunState) -> None:
        for field in fields(RunState):
            if field.name in {"config", "run_dir", "logs", "generation_iteration_loop_summary"}:
                continue
            setattr(parent, field.name, getattr(child, field.name))
        parent.logs.extend(child.logs)
