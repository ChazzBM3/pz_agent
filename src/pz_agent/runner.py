from __future__ import annotations

from pathlib import Path

from pz_agent.agents.benchmark import BenchmarkAgent
from pz_agent.agents.critique import CritiqueAgent
from pz_agent.agents.critique_reranker import CritiqueRerankerAgent
from pz_agent.agents.dft_handoff import DFTHandoffAgent
from pz_agent.agents.document_fetch import DocumentFetchAgent
from pz_agent.agents.figure_corpus import FigureCorpusAgent
from pz_agent.agents.knowledge_graph import KnowledgeGraphAgent
from pz_agent.agents.library_designer import LibraryDesignerAgent
from pz_agent.agents.multimodal_rerank import MultimodalRerankAgent
from pz_agent.agents.page_corpus import PageCorpusAgent
from pz_agent.agents.page_image_retrieval import PageImageRetrievalAgent
from pz_agent.agents.patent_retrieval import PatentRetrievalAgent
from pz_agent.agents.ranker import RankerAgent
from pz_agent.agents.reporter import ReporterAgent
from pz_agent.agents.scholarly_retrieval import ScholarlyRetrievalAgent
from pz_agent.agents.standardizer import StandardizerAgent
from pz_agent.agents.structure_expansion import StructureExpansionAgent
from pz_agent.agents.surrogate_screen import SurrogateScreenAgent
from pz_agent.agents.visual_identity import VisualIdentityAgent
from pz_agent.config import load_config
from pz_agent.io import ensure_dir, write_json
from pz_agent.state import RunState


STAGE_MAP = {
    "library_designer": LibraryDesignerAgent,
    "standardizer": StandardizerAgent,
    "structure_expansion": StructureExpansionAgent,
    "patent_retrieval": PatentRetrievalAgent,
    "scholarly_retrieval": ScholarlyRetrievalAgent,
    "page_corpus": PageCorpusAgent,
    "document_fetch": DocumentFetchAgent,
    "figure_corpus": FigureCorpusAgent,
    "page_image_retrieval": PageImageRetrievalAgent,
    "multimodal_rerank": MultimodalRerankAgent,
    "visual_identity": VisualIdentityAgent,
    "surrogate_screen": SurrogateScreenAgent,
    "benchmark": BenchmarkAgent,
    "knowledge_graph": KnowledgeGraphAgent,
    "ranker": RankerAgent,
    "critique": CritiqueAgent,
    "critique_reranker": CritiqueRerankerAgent,
    "reporter": ReporterAgent,
    "dft_handoff": DFTHandoffAgent,
}


def _get_stage_list(config: dict) -> list[str]:
    stages = config.get("pipeline", {}).get("stages", [])
    if not isinstance(stages, list) or not all(isinstance(stage, str) for stage in stages):
        raise ValueError("Config field pipeline.stages must be a list of stage names")
    if not stages:
        raise ValueError("Config field pipeline.stages is empty")
    unknown_stages = [stage for stage in stages if stage not in STAGE_MAP]
    if unknown_stages:
        supported = ", ".join(sorted(STAGE_MAP))
        unknown = ", ".join(unknown_stages)
        raise ValueError(f"Unknown pipeline stage(s): {unknown}. Supported stages: {supported}")
    return stages


def _write_state_snapshot(state: RunState) -> None:
    write_json(
        state.run_dir / "state_snapshot.json",
        {
            "logs": state.logs,
            "knowledge_graph_path": str(state.knowledge_graph_path) if state.knowledge_graph_path else None,
            "ranked_count": len(state.ranked or []),
            "shortlist_count": len(state.shortlist or []),
            "structure_expansion_count": len(state.structure_expansion or []),
            "patent_registry_count": len(state.patent_registry or []),
            "scholarly_registry_count": len(state.scholarly_registry or []),
            "page_registry_count": len(state.page_registry or []),
            "document_registry_count": len(state.document_registry or []),
            "figure_registry_count": len(state.figure_registry or []),
            "page_image_registry_count": len(state.page_image_registry or []),
            "multimodal_registry_count": len(state.multimodal_registry or []),
        },
    )


def run_pipeline(config_path: str | Path, run_dir: str | Path = "artifacts/run") -> RunState:
    config = load_config(config_path)
    stages = _get_stage_list(config)
    run_dir = Path(run_dir)
    ensure_dir(run_dir)

    state = RunState(config=config, run_dir=run_dir)
    state.log("Initialized run state")
    _write_state_snapshot(state)

    for stage_name in stages:
        agent_cls = STAGE_MAP[stage_name]
        agent = agent_cls(config=config)
        state.log(f"Running stage: {stage_name}")
        try:
            state = agent.run(state)
        except Exception as exc:
            state.log(f"Stage failed: {stage_name}: {exc}")
            _write_state_snapshot(state)
            raise RuntimeError(f"Pipeline stage '{stage_name}' failed") from exc
        _write_state_snapshot(state)

    return state
