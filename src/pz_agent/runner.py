from __future__ import annotations

from pathlib import Path

from pz_agent.config import load_config
from pz_agent.io import ensure_dir, write_json
from pz_agent.state import RunState
from pz_agent.agents.library_designer import LibraryDesignerAgent
from pz_agent.agents.standardizer import StandardizerAgent
from pz_agent.agents.surrogate_screen import SurrogateScreenAgent
from pz_agent.agents.benchmark import BenchmarkAgent
from pz_agent.agents.knowledge_graph import KnowledgeGraphAgent
from pz_agent.agents.ranker import RankerAgent
from pz_agent.agents.critique import CritiqueAgent
from pz_agent.agents.critique_reranker import CritiqueRerankerAgent
from pz_agent.agents.reporter import ReporterAgent
from pz_agent.agents.dft_handoff import DFTHandoffAgent


STAGE_MAP = {
    "library_designer": LibraryDesignerAgent,
    "standardizer": StandardizerAgent,
    "surrogate_screen": SurrogateScreenAgent,
    "benchmark": BenchmarkAgent,
    "knowledge_graph": KnowledgeGraphAgent,
    "ranker": RankerAgent,
    "critique": CritiqueAgent,
    "critique_reranker": CritiqueRerankerAgent,
    "reporter": ReporterAgent,
    "dft_handoff": DFTHandoffAgent,
}


def run_pipeline(config_path: str | Path, run_dir: str | Path = "artifacts/run") -> RunState:
    config = load_config(config_path)
    run_dir = Path(run_dir)
    ensure_dir(run_dir)

    state = RunState(config=config, run_dir=run_dir)
    state.log("Initialized run state")

    for stage_name in config.get("pipeline", {}).get("stages", []):
        agent_cls = STAGE_MAP[stage_name]
        agent = agent_cls(config=config)
        state.log(f"Running stage: {stage_name}")
        state = agent.run(state)
        write_json(run_dir / "state_snapshot.json", {
            "logs": state.logs,
            "knowledge_graph_path": str(state.knowledge_graph_path) if state.knowledge_graph_path else None,
            "ranked_count": len(state.ranked or []),
            "shortlist_count": len(state.shortlist or []),
        })

    return state
