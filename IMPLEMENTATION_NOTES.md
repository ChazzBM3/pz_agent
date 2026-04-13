# IMPLEMENTATION_NOTES.md

## Current status

The codebase now supports:
- GenMol-oriented generation framing
- synthesizability / solubility-first screening framing
- critique bundles with text evidence stubs
- multimodal KG nodes for image/plot/media artifacts
- evidence-aware report generation with placeholder plot artifacts
- live web-search enrichment artifacts
- normalized enriched KG rebuild with first-class literature/evidence nodes
- paper deduplication by URL/title fingerprint
- attachment of generated plot artifacts into enriched KG as media nodes

## Current KG layers

### Base KG
- run
- molecule
- prediction
- stub critique claim
- stub query nodes
- stub media nodes

### Enriched KG
- enriched claim nodes
- query-bundle nodes
- deduplicated paper nodes
- evidence-hit nodes per live search hit
- explicit `ANALOG_OF` / `EXACT_MATCH_OF` edges
- generated plot media nodes attached to enriched claim nodes

## Next coding step

The next step should be improving semantic quality, but with a clearer structure-first retrieval direction:
- build `structure_expansion` via PubChem exact/similarity/substructure lookup
- build patent-first retrieval via SureChEMBL + PatCID
- refine OpenAlex retrieval to consume structure-expansion outputs
- update critique/KG integration to use exact/analog/patent support tiers before generic text heuristics
- only after that, add page-corpus assembly, ColPali page-image retrieval, and Gemma multimodal reranking

See `IMAGE_RETRIEVAL_ROADMAP.md` for the concrete staged plan.

## Why it is not fully live yet

The agent package itself is plain Python code and does not have direct access to OpenClaw tools from inside those modules. So the current scaffold prepares the right data model and artifact flow, but actual tool-mediated search still needs to be orchestrated at the session/agent layer or via a dedicated wrapper.
