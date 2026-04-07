# DECORATION_RANKING_PLAN.md

## Goal

Start using decoration-aware chemistry features in ranking and reranking rather than keeping them as metadata only.

## Current adjustments

### Base ranking
- moderate substituent count -> small bonus
- very high substituent count -> small penalty
- electronic bias -> small bonus depending on category

### Literature-aware reranking
- preserves the literature bonus/penalty system
- also records decoration-aware rationale fields

## Why this is useful

This begins to align candidate prioritization with the actual chemistry framing of the project:
- all molecules share the phenothiazine core
- the important variation is in decorations and their effects

## Caveat
These adjustments are still heuristic and intentionally weak. They are not yet chemically validated scoring rules.

## Future upgrade path
- learn decoration-value patterns from known phenothiazines
- connect decoration patterns directly to literature support
- use site-aware substituent features instead of simple counts/tokens
