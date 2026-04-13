from __future__ import annotations

from pathlib import Path

from pz_agent.agents.patent_retrieval import PatentRetrievalAgent
from pz_agent.state import RunState



def test_patent_retrieval_agent_writes_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.patent_retrieval.retrieve_patent_evidence_for_candidate",
        lambda candidate, count=5, timeout=20: {
            "queries": ["foo patent"],
            "surechembl": [],
            "patcid": [],
            "errors": [],
            "status": "adapter_unavailable",
        },
    )

    state = RunState(
        config={"patent_retrieval": {"enabled": True}},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "smiles": "CC", "structure_expansion": {}}],
    )
    agent = PatentRetrievalAgent(config=state.config)
    updated = agent.run(state)

    assert updated.patent_registry is not None
    assert updated.patent_registry[0]["candidate_id"] == "cand_1"
    assert updated.library_clean[0]["patent_retrieval"]["queries"] == ["foo patent"]
    assert (tmp_path / "patent_retrieval.json").exists()
