from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique import CritiqueAgent
from pz_agent.agents.generation import GenerationAgent
from pz_agent.state import RunState



def test_generation_agent_assembles_dossiers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("pz_agent.agents.generation.LibraryDesignerAgent.run", lambda self, state: RunState(**{**state.__dict__, "library_raw": [{"id": "cand_1", "smiles": "CC", "sites": ["R1"]}], "generation_registry": [{"engine": "stub"}]}) )
    monkeypatch.setattr("pz_agent.agents.generation.StandardizerAgent.run", lambda self, state: RunState(**{**state.__dict__, "library_clean": [{"id": "cand_1", "smiles": "CC", "identity": {"scaffold": "phenothiazine"}}], "descriptors": []}) )
    monkeypatch.setattr("pz_agent.agents.generation.StructureExpansionAgent.run", lambda self, state: RunState(**{**state.__dict__, "library_clean": [{"id": "cand_1", "smiles": "CC", "identity": {"scaffold": "phenothiazine"}, "structure_expansion": {"query_hints": ["phenothiazine redox"]}}], "structure_expansion": []}) )
    monkeypatch.setattr("pz_agent.agents.generation.SurrogateScreenAgent.run", lambda self, state: RunState(**{**state.__dict__, "predictions": [{"id": "cand_1", "predicted_solubility": 0.7, "predicted_synthesizability": 0.8, "prediction_uncertainty": 0.2}]}) )
    monkeypatch.setattr("pz_agent.agents.generation.RankerAgent.run", lambda self, state: RunState(**{**state.__dict__, "ranked": [{"id": "cand_1", "predicted_priority": 1.0}], "shortlist": [{"id": "cand_1", "predicted_priority": 1.0}]}) )

    state = RunState(config={}, run_dir=tmp_path)
    updated = GenerationAgent(config={}).run(state)
    assert updated.dossier_registry is not None
    assert updated.dossier_registry[0]["candidate_id"] == "cand_1"
    assert updated.portfolio_registry[0]["proposal_bucket"] in {"exploit", "explore", "bridge", "falsify"}



def test_macro_critique_agent_emits_decisions(monkeypatch, tmp_path: Path) -> None:
    for target in [
        "PatentRetrievalAgent.run",
        "ScholarlyRetrievalAgent.run",
        "PageCorpusAgent.run",
        "DocumentFetchAgent.run",
        "FigureCorpusAgent.run",
        "OCRCaptionAgent.run",
        "PageImageRetrievalAgent.run",
        "MultimodalRerankAgent.run",
    ]:
        monkeypatch.setattr(f"pz_agent.agents.critique.{target}", lambda self, state: state)

    monkeypatch.setattr(
        "pz_agent.agents.critique.attach_critique_placeholders",
        lambda shortlist, enable_web_search, max_candidates, search_fields, graph_path: [{"candidate_id": "cand_1", "signals": {}, "queries": []}],
    )
    monkeypatch.setattr(
        "pz_agent.agents.critique.synthesize_evidence_from_queries",
        lambda notes: [{**notes[0], "signals": {"support_score": 0.4, "contradiction_score": 0.0}, "evidence": []}],
    )

    state = RunState(config={"critique": {"enable_web_search": False}}, run_dir=tmp_path, shortlist=[{"id": "cand_1"}], multimodal_registry=[])
    updated = CritiqueAgent(config=state.config).run(state)
    assert updated.critique_notes is not None
    assert updated.critique_notes[0]["decision"] in {"approve", "revise", "reject", "simulate-next"}
    assert updated.belief_registry is not None
