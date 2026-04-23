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
from pz_agent.io import ensure_dir, write_json
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
        convergence_cfg = dict(loop_cfg.get("convergence_tolerance") or {})
        taper_cfg = dict(loop_cfg.get("taper_min_improvement") or {})
        convergence_tol = {
            "solubility": float(convergence_cfg.get("solubility", 0.01) or 0.01),
            "synthesizability": float(convergence_cfg.get("synthesizability", 0.01) or 0.01),
        }
        taper_tol = {
            "solubility": float(taper_cfg.get("solubility", 0.0) or 0.0),
            "synthesizability": float(taper_cfg.get("synthesizability", 0.0) or 0.0),
        }

        loop_root = state.run_dir / "generation_iteration_loop"
        ensure_dir(loop_root)
        previous_top = self._top_metrics(state)
        current_action_queue = list(state.action_queue or [])
        summary: dict[str, Any] = {
            "max_rounds": max_rounds,
            "analysis_stages": analysis_stages,
            "iteration_stages": iteration_stages,
            "baseline_top": previous_top,
            "rounds": [],
            "stop_reason": None,
            "completed_rounds": 0,
        }

        if not current_action_queue:
            summary["stop_reason"] = "missing_action_queue"
            state.generation_iteration_loop_summary = summary
            write_json(state.run_dir / "generation_iteration_loop_summary.json", summary)
            state.log("Generation iteration loop skipped because there was no action queue to seed the first iteration")
            return state

        last_analysis_state: RunState | None = None
        last_iteration_state: RunState | None = None

        for round_index in range(1, max_rounds + 1):
            iteration_state = RunState(
                config=deepcopy(state.config),
                run_dir=loop_root / f"round_{round_index:02d}_iteration",
                action_queue=deepcopy(current_action_queue),
                ranked=deepcopy(last_analysis_state.ranked if last_analysis_state else state.ranked),
            )
            ensure_dir(iteration_state.run_dir)
            iteration_state.log(f"Starting generation iteration loop round {round_index}")
            for stage_name in iteration_stages:
                agent_cls = AGENT_MAP[stage_name]
                iteration_state = agent_cls(config=iteration_state.config).run(iteration_state)

            last_iteration_state = iteration_state
            reingest_manifest = dict(iteration_state.generation_iteration_reingest_manifest or {})
            aggregate_candidates_path = reingest_manifest.get("aggregate_candidates_path")
            completed_submission_count = int(reingest_manifest.get("completed_submission_count", 0) or 0)
            monitor_statuses = sorted({str(item.get("status") or "unknown") for item in (iteration_state.generation_iteration_monitor or [])})

            round_summary: dict[str, Any] = {
                "round_index": round_index,
                "iteration_run_dir": str(iteration_state.run_dir),
                "completed_submission_count": completed_submission_count,
                "monitor_statuses": monitor_statuses,
                "aggregate_candidates_path": aggregate_candidates_path,
                "analysis_run_dir": None,
                "top_candidate": None,
                "delta": None,
                "stop_reason": None,
            }

            if not aggregate_candidates_path or completed_submission_count <= 0:
                round_summary["stop_reason"] = "no_completed_outputs"
                summary["rounds"].append(round_summary)
                summary["stop_reason"] = "no_completed_outputs"
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
            current_top = self._top_metrics(analysis_state)
            round_summary["analysis_run_dir"] = str(analysis_state.run_dir)
            round_summary["top_candidate"] = current_top
            round_summary["next_action_queue_count"] = len(current_action_queue)

            stop_reason = None
            delta = self._metric_delta(previous_top, current_top)
            if delta is not None:
                round_summary["delta"] = delta
                if self._is_converged(delta, convergence_tol):
                    stop_reason = "converged"
                elif self._is_tapered(delta, taper_tol):
                    stop_reason = "tapered"
            if not current_action_queue:
                stop_reason = stop_reason or "empty_action_queue"

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
    def _is_converged(delta: dict[str, Any], tolerance: dict[str, float]) -> bool:
        return (
            abs(float(delta.get("solubility", 0.0))) <= tolerance["solubility"]
            and abs(float(delta.get("synthesizability", 0.0))) <= tolerance["synthesizability"]
        )

    @staticmethod
    def _is_tapered(delta: dict[str, Any], tolerance: dict[str, float]) -> bool:
        return (
            float(delta.get("solubility", 0.0)) <= tolerance["solubility"]
            and float(delta.get("synthesizability", 0.0)) <= tolerance["synthesizability"]
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
    def _merge_child_state(parent: RunState, child: RunState) -> None:
        for field in fields(RunState):
            if field.name in {"config", "run_dir", "logs", "generation_iteration_loop_summary"}:
                continue
            setattr(parent, field.name, getattr(child, field.name))
        parent.logs.extend(child.logs)
