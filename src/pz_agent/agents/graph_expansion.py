from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import read_json, write_json
from pz_agent.kg.rag import summarize_generation_iteration_candidate
from pz_agent.state import RunState


def _priority_with_outcome_bias(proposal: dict, outcome_stats: dict | None) -> tuple[float, dict[str, float]]:
    base_priority = float(proposal.get("priority", 0.0) or 0.0)
    if not outcome_stats:
        return base_priority, {"base": base_priority, "type_bias": 0.0, "reason_bias": 0.0, "type_support": 0.0, "reason_support": 0.0, "final": base_priority}

    proposal_type = str(proposal.get("proposal_type") or "")
    reason = str(proposal.get("reason") or "")
    type_stats = (outcome_stats.get("by_proposal_type") or {}).get(proposal_type, {})
    reason_stats = (outcome_stats.get("by_proposal_reason") or {}).get(reason, {})

    def _bias(stats: dict) -> tuple[float, float]:
        success = float(stats.get("success", 0.0) or 0.0)
        failure = float(stats.get("failure", 0.0) or 0.0)
        total = success + failure
        if total <= 0:
            return 0.0, 0.0
        raw_bias = max(-0.08, min(0.08, ((success - failure) / total) * 0.08))
        support_factor = min(1.0, total / 3.0)
        return raw_bias * support_factor, support_factor

    type_bias, type_support = _bias(type_stats)
    reason_bias, reason_support = _bias(reason_stats)
    final_priority = max(0.0, min(1.0, base_priority + type_bias + reason_bias))
    return final_priority, {"base": round(base_priority, 3), "type_bias": round(type_bias, 3), "reason_bias": round(reason_bias, 3), "type_support": round(type_support, 3), "reason_support": round(reason_support, 3), "final": round(final_priority, 3)}


def _frontier_priority(item: dict, outcome_stats: dict | None) -> float:
    kind = str(item.get("kind") or "")
    base_priority = float(item.get("priority", 0.0) or 0.0)
    synthetic_proposal = {
        "proposal_type": {
            "belief": "evidence_query_candidate",
            "failure": "simulation_request_candidate",
            "bridge": "bridge_case_candidate",
            "generation": "generation_iteration_candidate",
        }.get(kind, ""),
        "reason": {
            "belief": "low_confidence_belief_expand",
            "failure": "failed_transfer_needs_validation",
            "bridge": "medium_transferability_bridge_expand",
            "generation": "promising_genmol_iteration_seed",
        }.get(kind, ""),
        "priority": base_priority,
    }
    biased, _ = _priority_with_outcome_bias(synthetic_proposal, outcome_stats)
    return biased


def _build_action_queue(accepted: list[dict]) -> list[dict]:
    queue: list[dict] = []
    for proposal in accepted:
        proposal_type = str(proposal.get("proposal_type") or "")
        candidate_id = proposal.get("candidate_id")
        base = {
            "candidate_id": candidate_id,
            "priority": proposal.get("priority"),
            "source": "graph_expansion",
            "proposal_type": proposal_type,
            "proposal_reason": proposal.get("reason"),
            "critic_reason": proposal.get("critic_reason"),
        }
        if proposal_type == "simulation_request_candidate":
            queue.append({**base, "action_type": "simulation_request", "payload": proposal.get("payload", {})})
        elif proposal_type == "evidence_query_candidate":
            queue.append({**base, "action_type": "evidence_query", "payload": proposal.get("payload", {})})
        elif proposal_type == "bridge_case_candidate":
            queue.append({**base, "action_type": "bridge_expansion", "payload": proposal.get("payload", {})})
        elif proposal_type == "generation_iteration_candidate":
            queue.append({**base, "action_type": "generation_iteration", "payload": proposal.get("payload", {})})
    queue.sort(key=lambda item: (-float(item.get("priority", 0.0) or 0.0), str(item.get("candidate_id") or ""), str(item.get("action_type") or "")))
    return queue


def _critique_proposals(proposals: list[dict], outcome_stats: dict | None = None) -> tuple[list[dict], list[dict]]:
    accepted: list[dict] = []
    rejected: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for proposal in sorted(proposals, key=lambda item: (-float(item.get("priority", 0.0) or 0.0), item.get("candidate_id", ""), item.get("proposal_type", ""))):
        key = (str(proposal.get("candidate_id") or ""), str(proposal.get("proposal_type") or ""))
        if key in seen:
            rejected.append({**proposal, "critic_decision": "reject", "critic_reason": "duplicate_candidate_and_type"})
            continue
        seen.add(key)

        priority, bias_meta = _priority_with_outcome_bias(proposal, outcome_stats)
        merge_tag = str(proposal.get("merge_tag") or "")
        proposal_type = str(proposal.get("proposal_type") or "")
        enriched = {**proposal, "priority": priority, "priority_bias": bias_meta}

        if proposal_type == "simulation_request_candidate" and priority >= 0.5:
            accepted.append({**enriched, "critic_decision": "accept", "critic_reason": "high_priority_failure_validation"})
        elif proposal_type == "bridge_case_candidate" and priority >= 0.35 and merge_tag == "inferred":
            accepted.append({**enriched, "critic_decision": "accept", "critic_reason": "medium_transfer_bridge_followup"})
        elif proposal_type == "generation_iteration_candidate" and priority >= 0.55 and merge_tag in {"supported", "inferred"}:
            accepted.append({**enriched, "critic_decision": "accept", "critic_reason": "high_transfer_genmol_iteration_seed"})
        elif proposal_type == "evidence_query_candidate" and priority >= 0.45 and merge_tag == "speculative":
            accepted.append({**enriched, "critic_decision": "accept", "critic_reason": "high_uncertainty_belief_followup"})
        else:
            rejected.append({**enriched, "critic_decision": "reject", "critic_reason": "below_supervision_threshold"})

    return accepted, rejected


class GraphExpansionAgent(BaseAgent):
    name = "graph_expansion"

    def run(self, state: RunState) -> RunState:
        proposals: list[dict] = []
        if state.knowledge_graph_path and state.knowledge_graph_path.exists():
            graph = read_json(state.knowledge_graph_path)
            beliefs = [n for n in graph.get("nodes", []) if n.get("type") == "BeliefState"]
            failures = [n for n in graph.get("nodes", []) if n.get("type") == "FailureModeClass"]
            bridge_cases = [n for n in graph.get("nodes", []) if n.get("type") == "BridgeCase"]

            frontier = []
            for node in beliefs:
                attrs = node.get("attrs", {})
                status = str(attrs.get("status") or "")
                confidence = float(attrs.get("confidence", 0.0) or 0.0)
                if status in {"proposed", "contradicted"} or confidence < 0.6:
                    frontier.append({"kind": "belief", "node": node, "priority": 1.0 - confidence})
            for node in failures:
                frontier.append({"kind": "failure", "node": node, "priority": 1.0})
            for node in bridge_cases:
                attrs = node.get("attrs", {})
                score = float(attrs.get("transferability_score", 0.0) or 0.0)
                if 0.25 <= score < 0.75:
                    frontier.append({"kind": "bridge", "node": node, "priority": score})
                elif score >= 0.75 and str(attrs.get("next_action") or "") == "generation_prior":
                    frontier.append({"kind": "generation", "node": node, "priority": score})

            frontier.sort(key=lambda item: (-_frontier_priority(item, state.outcome_stats), item["node"].get("id", "")))
            for item in frontier[:5]:
                node = item["node"]
                attrs = node.get("attrs", {})
                candidate_id = attrs.get("candidate_id") or attrs.get("target_candidate_id") or attrs.get("belief_id", "unknown").replace("belief_state::", "")
                if item["kind"] == "failure":
                    proposals.append(
                        {
                            "merge_tag": "inferred",
                            "proposal_type": "simulation_request_candidate",
                            "candidate_id": candidate_id,
                            "reason": "failed_transfer_needs_validation",
                            "priority": item["priority"],
                            "payload": {
                                "next_action": "simulation_request",
                                "failure_mode": attrs.get("kind"),
                            },
                        }
                    )
                elif item["kind"] == "bridge":
                    proposals.append(
                        {
                            "merge_tag": "inferred",
                            "proposal_type": "bridge_case_candidate",
                            "candidate_id": candidate_id,
                            "reason": "medium_transferability_bridge_expand",
                            "priority": item["priority"],
                            "payload": {
                                "bridge_principles": attrs.get("bridge_principle_refs", []),
                                "transferability_score": attrs.get("transferability_score"),
                            },
                        }
                    )
                elif item["kind"] == "generation":
                    iteration_summary = summarize_generation_iteration_candidate(state.knowledge_graph_path, str(candidate_id))
                    if iteration_summary.get("eligible"):
                        proposals.append(
                            {
                                "merge_tag": "supported",
                                "proposal_type": "generation_iteration_candidate",
                                "candidate_id": candidate_id,
                                "reason": "promising_genmol_iteration_seed",
                                "priority": max(item["priority"], float(iteration_summary.get("priority", 0.0) or 0.0)),
                                "payload": {
                                    "next_action": "generation_iteration",
                                    "protocol": iteration_summary.get("protocol", {}),
                                    "candidate": iteration_summary.get("candidate", {}),
                                    "bridge_case_id": iteration_summary.get("bridge_case_id"),
                                    "bridge_principles": iteration_summary.get("bridge_principles", []),
                                    "generation_batch_ids": iteration_summary.get("generation_batch_ids", []),
                                    "history": iteration_summary.get("history", {}),
                                    "selection_basis": {
                                        "transferability_score": iteration_summary.get("transferability_score"),
                                        "support_score": iteration_summary.get("support_score"),
                                        "contradiction_score": iteration_summary.get("contradiction_score"),
                                        "measurement_summary": iteration_summary.get("measurement_summary", {}),
                                        "measurement_values": iteration_summary.get("measurement_values", {}),
                                    },
                                },
                            }
                        )
                else:
                    proposals.append(
                        {
                            "merge_tag": "speculative",
                            "proposal_type": "evidence_query_candidate",
                            "candidate_id": candidate_id,
                            "reason": "low_confidence_belief_expand",
                            "priority": item["priority"],
                            "payload": {
                                "belief_status": attrs.get("status"),
                                "confidence": attrs.get("confidence"),
                            },
                        }
                    )

        accepted, rejected = _critique_proposals(proposals, outcome_stats=state.outcome_stats)
        action_queue = _build_action_queue(accepted)
        state.expansion_registry = accepted
        state.action_queue = action_queue
        write_json(state.run_dir / "expansion_proposals.json", proposals)
        write_json(state.run_dir / "expansion_proposals.accepted.json", accepted)
        write_json(state.run_dir / "expansion_proposals.rejected.json", rejected)
        write_json(state.run_dir / "action_queue.json", action_queue)
        state.log(f"Graph expansion agent proposed {len(proposals)} actions, accepted {len(accepted)}, rejected {len(rejected)}, queued {len(action_queue)}")
        return state
