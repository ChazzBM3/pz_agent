# ENRICHED_RERANKING_PLAN.md

## Goal

Allow reranking to operate from enriched critique artifacts, not just the base pipeline critique stage.

## New capability

`pz-agent rerank-enriched --run-dir artifacts/run`

This reads:
- `report.json`
- `critique_notes.enriched.json`

and writes:
- `report.literature_reranked.json`

## Why this matters

This bridges the current architecture gap:
- live literature enrichment often happens after the base run
- reranking should be able to consume that richer evidence directly

## Current behavior
- uses enriched critique signals
- adjusts `predicted_priority_literature_adjusted`
- rewrites ranked list and shortlist in a separate output artifact

## Future improvement
- rerank directly from normalized enriched KG instead of critique artifact
- use confidence-weighted and contradiction-aware adjustments
