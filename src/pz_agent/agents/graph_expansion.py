from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.io import read_json, write_json
from pz_agent.state import RunState


def _priority_with_outcome_bias(proposal: dict, outcome_stats: dict | None) -> tuple[float, dict[str, float]]:
    base_priority = float(proposal.get("priority", 0.0) or 0.0)
    if not outcome_stats:
        return base_priority, {"base": base_priority, "type_bias": 0.0, "reason_bias": 0.0, "final": base_priority}

    proposal_type = str(proposal.get("proposal_type") or "")
    reason = str(proposal.get("reason") or "")
    type_stats = (outcome_stats.get("by_action_type") or {}).get(proposal_type, {})
    reason_stats = (outcome_stats.get("by_reason") or {}).get(reason, {})

    def _bias(stats: dict) -> float:
        success = float(stats.get("success", 0.0) or 0.0)
        failure = float(stats.get("failure", 0.0) or 0.0)
        total = success + failure
        if total <= 0:
            return 0.0
        return max(-0.08, min(0.08, ((success - failure) / total) * 0.08))

    type_bias = _bias(type_stats)
    reason_bias = _bias(reason_stats)
    final_priority = max(0.0, min(1.0, base_priority + type_bias + reason_bias))
    return final_priority, {"base": round(base_priority, 3), "type_bias": round(type_bias, 3), "reason_bias": round(reason_bias, 3), "final": round(final_priority, 3)}


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
            "critic_reason": proposal.get("critic_reason"),
        }
        if proposal_type == "simulation_request_candidate":
            queue.append({**base, "action_type": "simulation_request", "payload": proposal.get("payload", {})})
        elif proposal_type == "evidence_query_candidate":
            queue.append({**base, "action_type": "evidence_query", "payload": proposal.get("payload", {})})
        elif proposal_type == "bridge_case_candidate":
            queue.append({**base, "action_type": "bridge_expansion", "payload": proposal.get("payload", {})})
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

            frontier.sort(key=lambda item: (-float(item.get("priority", 0.0) or 0.0), item["node"].get("id", "")))
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
