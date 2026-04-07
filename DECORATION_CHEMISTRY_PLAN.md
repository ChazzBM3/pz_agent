# DECORATION_CHEMISTRY_PLAN.md

## Assumption

All molecules already contain the phenothiazine core.
So chemistry reasoning should focus on decorations / functional groups rather than core detection.

## Current additions
- `core_assumption = phenothiazine`
- `decoration_summary`
- `substituent_count`
- `decoration_tokens`

## Why this matters
This makes the system more aligned with the actual project:
- literature queries can focus on substituent patterns
- KG memory can accumulate decoration-level trends
- analog reasoning can be centered on functionalization, not scaffold existence

## Current implementation
The decoration summary is currently a lightweight token-based heuristic over canonical SMILES.
That is enough for scaffolding, but not yet a chemically rigorous substituent decomposition.

## Future improvement
- derive attachment-aware substituent fragments with RDKit
- classify electron-donating vs electron-withdrawing groups
- use decoration-level features in ranking and reranking
