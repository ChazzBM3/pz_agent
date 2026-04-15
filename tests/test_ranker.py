from __future__ import annotations

from pz_agent.agents.ranker import RankerAgent
from pz_agent.state import RunState


class _DummyRunDir:
    name = "test-run"


def _state() -> RunState:
    return RunState(config={"screening": {"shortlist_size": 2}}, run_dir=_DummyRunDir())


def test_ranker_applies_critique_adjustments_to_ordering() -> None:
    state = _state()
    state.predictions = [
        {"id": "cand_a", "predicted_synthesizability": 0.60, "predicted_solubility": 0.60},
        {"id": "cand_b", "predicted_synthesizability": 0.62, "predicted_solubility": 0.62},
    ]
    state.critique_notes = [
        {
            "candidate_id": "cand_a",
            "evidence_tier": "candidate",
            "signals": {
                "exact_match_hits": 2,
                "analog_match_hits": 1,
                "property_aligned_hits": 3,
                "support_score": 4.0,
                "contradiction_score": 0.0,
                "patent_hit_count": 2,
                "scholarly_hit_count": 1,
                "supports_solubility": True,
            },
            "support_mix": {"transferability_score": 0.7, "simulation_support": 0.2},
            "evidence": [
                {"match_type": "exact", "title": "Phenothiazine solubility", "snippet": "solubility oxidation electrolyte", "query": "cand_a solubility"}
            ],
        }
    ]

    ranked_state = RankerAgent(config=state.config).run(state)

    assert ranked_state.ranked is not None
    assert ranked_state.ranked[0]["id"] == "cand_a"
    assert ranked_state.ranked[0]["predicted_priority_literature_adjusted"] > ranked_state.ranked[1]["predicted_priority_literature_adjusted"]
    assert ranked_state.ranked[0]["ranking_rationale"]["evidence_sources"]["has_critique_note"] is True


def test_ranker_preserves_base_priority_without_critique() -> None:
    state = _state()
    state.predictions = [
        {"id": "cand_a", "predicted_synthesizability": 0.55, "predicted_solubility": 0.55},
        {"id": "cand_b", "predicted_synthesizability": 0.50, "predicted_solubility": 0.50},
    ]
    state.critique_notes = []

    ranked_state = RankerAgent(config=state.config).run(state)

    assert ranked_state.ranked is not None
    assert ranked_state.ranked[0]["id"] == "cand_a"
    assert ranked_state.ranked[0]["predicted_priority_literature_adjusted"] == ranked_state.ranked[0]["predicted_priority"]
    assert ranked_state.ranked[0]["ranking_rationale"]["evidence_sources"]["has_critique_note"] is False
