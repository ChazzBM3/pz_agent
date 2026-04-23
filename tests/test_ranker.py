from __future__ import annotations

import json
from pathlib import Path

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


def test_ranker_dedupes_duplicate_evidence_credit() -> None:
    state = _state()
    state.predictions = [
        {"id": "cand_a", "predicted_synthesizability": 0.60, "predicted_solubility": 0.60},
        {"id": "cand_b", "predicted_synthesizability": 0.60, "predicted_solubility": 0.60},
    ]
    duplicate_evidence = {
        "match_type": "exact",
        "title": "Phenothiazine solubility",
        "snippet": "solubility oxidation electrolyte",
        "query": "cand_a solubility",
        "url": "https://example.org/paper-a",
    }
    state.critique_notes = [
        {
            "candidate_id": "cand_a",
            "evidence_tier": "candidate",
            "signals": {
                "exact_match_hits": 3,
                "analog_match_hits": 2,
                "property_aligned_hits": 4,
                "support_score": 4.0,
                "contradiction_score": 0.0,
            },
            "evidence": [duplicate_evidence, dict(duplicate_evidence)],
        }
    ]

    ranked_state = RankerAgent(config=state.config).run(state)

    assert ranked_state.ranked is not None
    top = next(item for item in ranked_state.ranked if item["id"] == "cand_a")
    assert "deduped_evidence_items=1" in top["ranking_rationale"]["literature_adjustment"]


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


def test_ranker_prefers_support_view_while_novelty_view_can_diverge(tmp_path: Path) -> None:
    graph = {
        "nodes": [
            {"id": "cand_supported", "type": "Molecule", "attrs": {}},
            {"id": "cand_novel", "type": "Molecule", "attrs": {}},
            {"id": "scaffold::dense", "type": "Scaffold", "attrs": {"smiles": "c1ccccc1"}},
            {"id": "scaffold::sparse", "type": "Scaffold", "attrs": {"smiles": "c1ccncc1"}},
        ],
        "edges": [
            {"source": "cand_supported", "target": "scaffold::dense", "type": "HAS_SCAFFOLD"},
            {"source": "cand_novel", "target": "scaffold::sparse", "type": "HAS_SCAFFOLD"},
            *[
                {"source": f"dense_family_{i}", "target": "scaffold::dense", "type": "HAS_SCAFFOLD"}
                for i in range(140)
            ],
            *[
                {"source": f"dense_measurement_{i}", "target": "cand_supported", "type": "MEASURED_FOR"}
                for i in range(18)
            ],
            *[
                {"source": f"sparse_family_{i}", "target": "scaffold::sparse", "type": "HAS_SCAFFOLD"}
                for i in range(2)
            ],
        ],
    }
    graph_path = tmp_path / "kg.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")

    state = RunState(
        config={"screening": {"shortlist_size": 1}},
        run_dir=tmp_path,
        knowledge_graph_path=graph_path,
        predictions=[
            {"id": "cand_supported", "predicted_synthesizability": 0.72, "predicted_solubility": 0.72},
            {"id": "cand_novel", "predicted_synthesizability": 0.69, "predicted_solubility": 0.69},
        ],
        critique_notes=[
            {
                "candidate_id": "cand_supported",
                "signals": {
                    "exact_match_hits": 4,
                    "property_aligned_hits": 3,
                    "measurement_count": 18,
                    "property_count": 5,
                    "support_score": 7.0,
                    "contradiction_score": 0.0,
                    "supports_solubility": True,
                },
                "support_mix": {"transferability_score": 0.3, "simulation_support": 0.2},
                "evidence": [
                    {
                        "match_type": "exact",
                        "title": "Phenothiazine electrolyte solubility",
                        "snippet": "solubility oxidation electrolyte",
                        "query": "cand_supported solubility",
                        "url": "https://example.org/support-paper",
                    }
                ],
            },
            {
                "candidate_id": "cand_novel",
                "signals": {
                    "exact_match_hits": 0,
                    "analog_match_hits": 1,
                    "property_aligned_hits": 1,
                    "support_score": 1.0,
                    "contradiction_score": 0.0,
                },
                "support_mix": {"adjacent_scaffold_support": 0.8, "transferability_score": 0.5},
                "evidence": [
                    {
                        "match_type": "analog",
                        "title": "Adjacent scaffold redox behavior",
                        "snippet": "redox electrolyte scaffold analog",
                        "query": "cand_novel analog redox",
                        "url": "https://example.org/analog-paper",
                    }
                ],
            },
        ],
    )

    ranked_state = RankerAgent(config=state.config).run(state)

    assert ranked_state.shortlist is not None
    assert ranked_state.novelty_shortlist is not None
    assert ranked_state.shortlist[0]["id"] == "cand_supported"
    assert ranked_state.novelty_shortlist[0]["id"] == "cand_novel"



def test_ranker_contradiction_signal_penalizes_candidate_ordering() -> None:
    state = _state()
    state.predictions = [
        {"id": "cand_clean", "predicted_synthesizability": 0.60, "predicted_solubility": 0.60},
        {"id": "cand_warned", "predicted_synthesizability": 0.62, "predicted_solubility": 0.62},
    ]
    state.critique_notes = [
        {
            "candidate_id": "cand_warned",
            "evidence_tier": "candidate",
            "signals": {
                "exact_match_hits": 1,
                "property_aligned_hits": 1,
                "support_score": 1.0,
                "contradiction_score": 6.0,
                "warns_instability": True,
            },
            "support_mix": {},
            "evidence": [
                {
                    "match_type": "exact",
                    "title": "Phenothiazine instability warning",
                    "snippet": "unstable decomposition electrolyte",
                    "query": "cand_warned instability",
                    "url": "https://example.org/instability-paper",
                }
            ],
        }
    ]

    ranked_state = RankerAgent(config=state.config).run(state)

    assert ranked_state.ranked is not None
    assert ranked_state.ranked[0]["id"] == "cand_clean"
    warned = next(item for item in ranked_state.ranked if item["id"] == "cand_warned")
    assert warned["predicted_priority_literature_adjusted"] < warned["predicted_priority"]
    assert any("instability_warning_penalty" in item for item in warned["ranking_rationale"]["literature_adjustment"])
