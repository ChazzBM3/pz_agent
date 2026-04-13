from __future__ import annotations

from pz_agent.agents.critique import _apply_multimodal_judgments



def test_apply_multimodal_judgments_updates_signals() -> None:
    note = {
        "candidate_id": "cand_1",
        "signals": {"exact_match_hits": 0, "analog_match_hits": 0, "property_aligned_hits": 0, "support_score": 0.0, "contradiction_score": 0.0},
        "multimodal_rerank": {
            "bundles": [
                {"gemma_judgment": {"match_label": "exact", "property_relevance": "redox", "confidence": "high", "needs_human_review": False}},
                {"gemma_judgment": {"match_label": "analog", "property_relevance": "solubility", "confidence": "medium", "needs_human_review": True}},
            ]
        },
    }
    updated = _apply_multimodal_judgments(note)
    signals = updated["signals"]
    assert signals["exact_match_hits"] == 1
    assert signals["analog_match_hits"] == 1
    assert signals["property_aligned_hits"] == 2
    assert signals["support_score"] > 0
    assert signals["multimodal_review_flags"] == 1
