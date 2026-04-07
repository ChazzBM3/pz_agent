# NORMALIZED_KG_PLAN.md

## Goal

Move from an overlay-style enriched KG to a more normalized graph where live search results become first-class graph nodes and edges.

## New normalized entities
- `LiteraturePaper`
- `EvidenceHit`
- enriched `LiteratureClaim` nodes

## New relations
- `HAS_EVIDENCE_HIT`
- `ANALOG_OF`
- `EXACT_MATCH_OF`

## Normalized enriched flow

For each candidate:
1. create an enriched claim node
2. create a query-bundle node
3. create one paper node per search hit
4. create one evidence-hit node per search hit
5. connect evidence-hit to candidate as exact or analog
6. connect evidence-hit to paper and claim

## Why this is better
- search hits are now explicit graph objects
- papers can later be deduplicated across candidates
- exact vs analog is graph-visible
- downstream graph analytics become more natural

## Still to improve later
- canonical paper deduplication by URL/title fingerprint
- claim-level support/contradiction extraction
- media/figure extraction from papers
- chemistry-aware exact matching via SMILES/InChI/name normalization
