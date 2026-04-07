# ENRICHED_FLOW_NOTES.md

## Current enriched flow

We now support a concrete two-phase workflow:

1. **Base pipeline run**
   - writes `critique_notes.json`
   - writes `knowledge_graph.json`
   - writes `report.json`

2. **Live search enrichment**
   - writes `critique_notes.enriched.json`
   - can rebuild:
     - `knowledge_graph.enriched.json`
     - `report.enriched.json`

## Important note

The enriched graph/report rebuild is currently a lightweight overlay approach.
It preserves the original base artifacts and adds enriched critique evidence on top.

That is the right short-term move because it:
- preserves provenance
- keeps the base run reproducible
- makes the enrichment step explicit

## Future improvement

A future version should rebuild the graph more semantically by turning each live search hit into:
- canonical LiteraturePaper nodes
- LiteratureClaim support/contradiction edges
- media references when present

instead of embedding the enriched critique bundle wholesale.
