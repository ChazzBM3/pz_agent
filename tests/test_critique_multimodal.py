from __future__ import annotations

from pz_agent.agents.critique import _apply_multimodal_judgments
from pz_agent.analysis.pareto import apply_literature_adjustment



def test_apply_multimodal_judgments_updates_signals() -> None:
    note = {
        "candidate_id": "cand_1",
        "signals": {"exact_match_hits": 0, "analog_match_hits": 0, "property_aligned_hits": 0, "support_score": 0.0, "contradiction_score": 0.0},
        "multimodal_rerank": {
            "bundles": [
                {"retrieval_score": 0.95, "gemma_judgment": {"match_label": "exact", "property_relevance": "redox", "confidence": "high", "needs_human_review": False}},
                {"retrieval_score": 0.60, "gemma_judgment": {"match_label": "analog", "property_relevance": "solubility", "confidence": "medium", "needs_human_review": True}},
            ]
        },
    }
    updated = _apply_multimodal_judgments(note)
    signals = updated["signals"]
    assert signals["exact_match_hits"] == 1
    assert signals["analog_match_hits"] == 1
    assert signals["property_aligned_hits"] == 2
    assert signals["support_score"] > 0
    assert signals["multimodal_support_score"] > 0
    assert signals["multimodal_mean_retrieval_score"] > 0.7
    assert signals["multimodal_review_flags"] == 1



def test_apply_literature_adjustment_uses_multimodal_signal_calibration() -> None:
    row = {"id": "cand_1", "predicted_priority": 1.0, "ranking_rationale": {}}
    critique_note = {
        "evidence_tier": "analog",
        "signals": {
            "support_score": 0.2,
            "contradiction_score": 0.0,
            "multimodal_support_score": 1.2,
            "multimodal_contradiction_score": 0.1,
            "multimodal_mean_retrieval_score": 0.8,
        },
    }
    updated = apply_literature_adjustment(row, critique_note)
    assert updated["predicted_priority_literature_adjusted"] > 1.0
    rationale = updated["ranking_rationale"]["literature_adjustment"]
    assert any("multimodal_support_bonus" in item for item in rationale)
    assert any("multimodal_retrieval_bonus" in item for item in rationale)
