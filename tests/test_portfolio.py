from __future__ import annotations

from pz_agent.analysis.portfolio import assign_portfolio_buckets, normalize_budget_map



def test_normalize_budget_map_normalizes_values() -> None:
    normalized = normalize_budget_map({"exploit": 2, "explore": 1, "bridge": 1, "falsify": 0})
    assert round(sum(normalized.values()), 6) == 1.0
    assert normalized["exploit"] > normalized["explore"]



def test_assign_portfolio_buckets_emits_bridge_bucket_when_signal_exists() -> None:
    assignments = assign_portfolio_buckets(
        [
            {"id": "cand_1", "identity": {"decoration_tokens": ["OMe"]}, "ranked_row": {"predicted_priority": 0.9}},
            {"id": "cand_2", "identity": {}, "ranked_row": {"predicted_priority": 0.8}},
            {"id": "cand_3", "identity": {}, "ranked_row": {"predicted_priority": 0.7}},
            {"id": "cand_4", "identity": {}, "ranked_row": {"predicted_priority": 0.6}},
        ]
    )
    by_id = {item["candidate_id"]: item for item in assignments}
    assert by_id["cand_1"]["proposal_bucket"] in {"exploit", "bridge"}
    assert any(item["proposal_bucket"] == "bridge" for item in assignments)
