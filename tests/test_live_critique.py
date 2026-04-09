from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique import CritiqueAgent, _classify_match_type, _summarize_live_signals
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


def test_classify_match_type_detects_exact_and_analog() -> None:
    note = {
        "candidate_id": "cand_1",
        "identity": {
            "name": "cand_1",
            "scaffold": "phenothiazine",
            "decoration_tokens": ["O", "N"],
        },
    }

    assert _classify_match_type(note, "cand_1 phenothiazine result", None, None) == "exact"
    assert _classify_match_type(note, "phenothiazine derivative study", None, None) == "analog"
    assert _classify_match_type(note, "unrelated benzene result", None, None) == "unknown"


def test_summarize_live_signals_detects_property_support_and_warnings() -> None:
    note = {"signals": {"support_score": 0.0, "contradiction_score": 0.0}}
    evidence = [
        {
            "title": "Phenothiazine solubility and synthesis route study",
            "snippet": "This soluble analog was prepared through a short synthesis.",
            "match_type": "analog",
        },
        {
            "title": "Phenothiazine instability report",
            "snippet": "The compound shows decomposition under air.",
            "match_type": "exact",
        },
    ]

    signals = _summarize_live_signals(note, evidence)

    assert signals["supports_solubility"] is True
    assert signals["supports_synthesizability"] is True
    assert signals["warns_instability"] is True
    assert signals["exact_match_hits"] >= 1
    assert signals["analog_match_hits"] >= 1
