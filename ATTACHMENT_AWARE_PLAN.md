# ATTACHMENT_AWARE_PLAN.md

## Goal

Move beyond decoration token counting toward attachment-aware substituent characterization for phenothiazine derivatives.

## Current scaffold
The current implementation adds:
- `substituent_fragments`
- `attachment_summary`
- `electronic_bias`

These are still heuristics, but they prepare the data model for more chemically meaningful reasoning.

## Why this matters
For this project, all candidates share the phenothiazine core. The useful chemical variation is therefore:
- what decorations exist
- how many there are
- whether they skew electron-donating or electron-withdrawing
- how that decoration pattern relates to solubility, synthesizability, and literature support

## Current limitation
Attachment summaries are not yet true site-resolved substituent assignments. They are placeholders for that future capability.

## Future upgrade path
- site-aware substituent extraction from RDKit graphs
- donor/acceptor and electronic effect classification at substituent level
- decoration-aware analog reasoning in KG and reranking
