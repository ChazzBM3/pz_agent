from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique import CritiqueAgent
from pz_agent.state import RunState


def test_critique_agent_uses_live_search_backend(tmp_path: Path) -> None:
    state = RunState(
        config={
            "critique": {
                "enable_web_search": True,
                "max_candidates": 1,
                "search_fields": ["phenothiazine", "solubility"],
            },
            "search": {
                "backend": "stub",
                "count": 2,
            },
            "screening": {"shortlist_size": 1},
        },
        run_dir=tmp_path,
    )
    state.shortlist = [
        {
            "id": "cand_1",
            "identity": {"name": "cand_1", "scaffold": "phenothiazine"},
        }
    ]

    agent = CritiqueAgent(config=state.config)
    updated = agent.run(state)

    assert updated.critique_notes is not None
    note = updated.critique_notes[0]
    assert note["status"] in {"ready_for_live_web_ingestion", "disabled"}


def test_critique_agent_falls_back_to_placeholder_for_stub_backend(tmp_path: Path) -> None:
    state = RunState(
        config={
            "critique": {
                "enable_web_search": True,
                "max_candidates": 1,
                "search_fields": ["phenothiazine"],
            },
            "search": {
                "backend": "stub",
                "count": 2,
            },
            "screening": {"shortlist_size": 1},
        },
        run_dir=tmp_path,
    )
    state.shortlist = [{"id": "cand_2", "identity": {}}]

    agent = CritiqueAgent(config=state.config)
    updated = agent.run(state)

    note = updated.critique_notes[0]
    assert note["evidence"]
    assert note["evidence"][0]["kind"] == "web_result_stub"
