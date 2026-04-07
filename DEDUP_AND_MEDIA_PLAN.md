# DEDUP_AND_MEDIA_PLAN.md

## Goal

Improve the normalized enriched KG by:
- deduplicating literature papers across candidates and queries
- attaching generated plot artifacts as first-class media nodes
- preparing for support/contradiction typing

## Current strategy

### Paper deduplication
Canonicalize papers by:
- URL when available
- otherwise title fingerprint

This is implemented as a stable paper id derived from a SHA1 fingerprint of URL or title.

### Media attachment
Attach generated plot artifacts from `evidence_report.json` into the enriched graph as `MediaArtifact` nodes.

### Evidence typing
Current relation typing:
- `EXACT_MATCH_OF` when match_type is exact
- `ANALOG_OF` otherwise
- `CONTRADICTED_BY` reserved for future cautionary evidence

## Future refinement
- stronger contradiction extraction from snippets
- paper metadata enrichment (journal, year, authors, DOI)
- candidate-specific plot generation rather than shared plot attachment
