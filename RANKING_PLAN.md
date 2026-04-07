# RANKING_PLAN.md

## Current ranking behavior

The ranker now computes a simple weighted priority score:
- synthesizability weight: 0.55
- solubility weight: 0.45

This is still a placeholder ranking model, but it is better than pass-through ordering.

## Outputs added to ranked candidates
- `predicted_priority`
- `ranking_rationale`

## Why this is useful now

Even before real production models exist, this makes the pipeline behavior more realistic:
- predictions affect ordering
- shortlist size is configurable
- rationale is explicit in the artifacts

## Future improvement
- replace weighted score with real Pareto / non-dominated sorting
- add hard thresholds and uncertainty penalties
- include literature evidence as a reranking factor
