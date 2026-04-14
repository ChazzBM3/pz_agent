from __future__ import annotations

from typing import Any


def summarize_graph_metrics(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    node_types = [node.get("type") for node in nodes]

    claim_count = sum(1 for t in node_types if t in {"Claim", "LiteratureClaim"})
    belief_count = sum(1 for t in node_types if t == "BeliefState")
    bridge_count = sum(1 for t in node_types if t == "BridgeCase")
    transform_rule_count = sum(1 for t in node_types if t == "TransformRule")
    failure_mode_count = sum(1 for t in node_types if t == "FailureModeClass")

    unsupported_beliefs = 0
    contradiction_rate_num = 0
    metadata_dominant = 0
    for node in nodes:
        if node.get("type") != "BeliefState":
            continue
        attrs = node.get("attrs", {})
        status = str(attrs.get("status") or "")
        confidence = float(attrs.get("confidence", 0.0) or 0.0)
        support_mix = dict(attrs.get("support_mix") or {})
        if status == "proposed" and confidence < 0.6:
            unsupported_beliefs += 1
        if float(attrs.get("contradiction_score", 0.0) or 0.0) > 0:
            contradiction_rate_num += 1
        metadata_support = float(support_mix.get("metadata_support", 0.0) or 0.0)
        total_support = sum(float(v or 0.0) for k, v in support_mix.items() if k.endswith("support"))
        if total_support > 0 and metadata_support / total_support > 0.5:
            metadata_dominant += 1

    unsupported_belief_ratio = unsupported_beliefs / belief_count if belief_count else 0.0
    contradiction_rate = contradiction_rate_num / belief_count if belief_count else 0.0
    weak_support_dominance = metadata_dominant / belief_count if belief_count else 0.0
    fact_to_belief_ratio = claim_count / belief_count if belief_count else float(claim_count)

    warnings = []
    if unsupported_belief_ratio > 0.35:
        warnings.append("unsupported_belief_ratio_high")
    if contradiction_rate > 0.30:
        warnings.append("contradiction_rate_high")
    if weak_support_dominance > 0.50:
        warnings.append("weak_support_dominance_high")

    return {
        "node_growth": len(nodes),
        "edge_growth": len(edges),
        "fact_to_belief_ratio": round(fact_to_belief_ratio, 3),
        "unsupported_belief_ratio": round(unsupported_belief_ratio, 3),
        "bridge_node_count": bridge_count,
        "transform_rule_count": transform_rule_count,
        "failure_mode_count": failure_mode_count,
        "contradiction_rate": round(contradiction_rate, 3),
        "weak_support_dominance": round(weak_support_dominance, 3),
        "warnings": warnings,
    }
