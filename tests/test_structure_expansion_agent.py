from __future__ import annotations

from pathlib import Path

from pz_agent.agents.structure_expansion import StructureExpansionAgent
from pz_agent.state import RunState



def test_structure_expansion_agent_writes_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.structure_expansion.expand_structure_with_pubchem",
        lambda candidate, similarity_threshold=90, similarity_max_records=5, substructure_max_records=5, timeout=20: {
            "query_smiles": candidate.get("smiles"),
            "synonyms": ["Example"],
            "exact_matches": [{"cid": 1}],
            "similarity_matches": [],
            "substructure_matches": [],
            "status": "ok",
        },
    )

    state = RunState(
        config={"structure_expansion": {"enabled": True}},
        run_dir=tmp_path,
        library_clean=[{"id": "cand_1", "smiles": "CC"}],
    )
    agent = StructureExpansionAgent(config=state.config)
    updated = agent.run(state)

    assert updated.structure_expansion is not None
    assert updated.structure_expansion[0]["candidate_id"] == "cand_1"
    assert (tmp_path / "structure_expansion.json").exists()
    assert updated.library_clean[0]["structure_expansion"]["status"] == "ok"
