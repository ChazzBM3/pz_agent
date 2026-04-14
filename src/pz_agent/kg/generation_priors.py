from __future__ import annotations

from pathlib import Path
from typing import Any

from pz_agent.io import read_json



def derive_generation_priors_from_graph(workspace_root: Path) -> dict[str, Any]:
    artifacts_dir = workspace_root / "artifacts"
    if not artifacts_dir.exists():
        return {
            "generation_priors": {"pt_direct": 0.5, "bridge_driven": 0.3, "simulation_driven": 0.2},
            "bridge_dimensions": ["electronic_push_pull", "solubilizing_handle", "route_modularity"],
            "failure_bias": [],
            "source": "default",
        }

    candidates = sorted(
        [p for p in artifacts_dir.iterdir() if p.is_dir() and (p / "report.json").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {
            "generation_priors": {"pt_direct": 0.5, "bridge_driven": 0.3, "simulation_driven": 0.2},
            "bridge_dimensions": ["electronic_push_pull", "solubilizing_handle", "route_modularity"],
            "failure_bias": [],
            "source": "default",
        }

    report = read_json(candidates[0] / "report.json")
    graph_metrics = dict(report.get("graph_metrics") or {})
    knowledge_graph_path = report.get("knowledge_graph") or report.get("knowledge_graph_path")
    bridge_dimensions = ["electronic_push_pull", "solubilizing_handle", "route_modularity"]
    failure_bias: list[str] = []

    if knowledge_graph_path:
        kg_path = Path(knowledge_graph_path)
        if not kg_path.is_absolute():
            kg_path = candidates[0] / Path(knowledge_graph_path).name
        if kg_path.exists():
            graph = read_json(kg_path)
            for node in graph.get("nodes", []):
                if node.get("type") == "FailureModeClass":
                    failure_bias.append(str(node.get("attrs", {}).get("candidate_id") or node.get("id")))
                if node.get("type") == "BridgeDimension":
                    name = str(node.get("attrs", {}).get("name") or "")
                    if name and name not in bridge_dimensions:
                        bridge_dimensions.append(name)

    unsupported = float(graph_metrics.get("unsupported_belief_ratio", 0.0) or 0.0)
    contradiction = float(graph_metrics.get("contradiction_rate", 0.0) or 0.0)

    pt_direct = max(0.35, min(0.75, 0.55 + unsupported * 0.1 + contradiction * 0.1))
    bridge_driven = max(0.15, min(0.4, 0.3 - contradiction * 0.1))
    simulation_driven = max(0.1, min(0.35, 1.0 - pt_direct - bridge_driven))

    total = pt_direct + bridge_driven + simulation_driven
    priors = {
        "pt_direct": round(pt_direct / total, 3),
        "bridge_driven": round(bridge_driven / total, 3),
        "simulation_driven": round(simulation_driven / total, 3),
    }

    return {
        "generation_priors": priors,
        "bridge_dimensions": bridge_dimensions,
        "failure_bias": failure_bias,
        "source": str(candidates[0].name),
        "graph_metrics": graph_metrics,
    }
