from __future__ import annotations

from pathlib import Path

from pz_agent.analysis.media import create_placeholder_plot
from pz_agent.io import read_json, write_json
from pz_agent.kg.metrics import summarize_graph_metrics
from pz_agent.state import RunState


def write_evidence_report(state: RunState) -> Path:
    plots_dir = state.run_dir / "plots"
    synth_plot = create_placeholder_plot(
        plots_dir / "synthesizability_ranking.txt",
        "Synthesizability ranking",
        state.ranked or [],
    )
    sol_plot = create_placeholder_plot(
        plots_dir / "solubility_ranking.txt",
        "Solubility ranking",
        state.ranked or [],
    )
    pareto_plot = create_placeholder_plot(
        plots_dir / "pareto_shortlist.txt",
        "Pareto shortlist",
        state.shortlist or [],
    )

    path = state.run_dir / "evidence_report.json"
    graph_metrics = {}
    if state.knowledge_graph_path and state.knowledge_graph_path.exists():
        graph_metrics = summarize_graph_metrics(read_json(state.knowledge_graph_path))

    payload = {
        "summary": "Evidence-aware report scaffold with text evidence and plot artifact references.",
        "shortlist": state.shortlist or [],
        "critique_notes": state.critique_notes or [],
        "knowledge_graph_path": str(state.knowledge_graph_path) if state.knowledge_graph_path else None,
        "graph_metrics": graph_metrics,
        "plots": [str(synth_plot), str(sol_plot), str(pareto_plot)],
    }
    write_json(path, payload)
    return path
