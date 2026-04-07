# SCORING_PLAN.md

## Goal

Prepare `pz_agent` for real screening before final models are available by scaffolding:
- synthesizability scoring
- solubility scoring
- prediction provenance
- external score import support

## Current modes

### 1. Internal heuristic mode
Default.
Returns rough placeholder numeric values with structured provenance for both objectives.
These are deliberately weak heuristics, but they exercise downstream ranking/KG/report paths.

### 2. External score import mode
Enable with:
- `screening.use_external_scores: true`

In this mode, if imported molecules contain fields like:
- `external_synthesizability`
- `external_solubility`
- `external_solubility_units`

then those values flow into predictions with external provenance.

## Why this matters

This lets the project mature in stages:
- external GenMol generation first
- external or heuristic scoring next
- internal production models later

without changing the downstream ranking / KG / reporting architecture.

## Next steps
- add better heuristic baselines
- add units/normalization rules
- propagate prediction provenance more deeply into normalized enriched KG rebuild
