# LITERATURE_RERANKING_PLAN.md

## Goal

Add a second-pass reranking stage that adjusts candidate priority using critique/literature evidence.

## Current adjustment rules
- `supports_solubility` -> +0.05
- `supports_synthesizability` -> +0.05
- analog hit count -> small capped bonus
- `warns_instability` -> penalty

## Why a second pass

This keeps the architecture clean:
- first pass = model-based numeric ranking
- second pass = evidence-aware adjustment

## Current limitation

The critique stage currently produces placeholder evidence in the base pipeline run.
So the real value will show up most strongly once the pipeline is run after live enrichment or when critique signals become richer.

## Future improvement
- use normalized enriched KG directly for reranking
- separate background literature from strong support
- penalize contradictory or low-confidence evidence
