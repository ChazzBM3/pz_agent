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
- paper nodes per live search hit
- evidence-hit nodes per live search hit
- explicit `ANALOG_OF` / `EXACT_MATCH_OF` edges

## Next coding step

The next step should be improving semantic quality:
- deduplicate papers across candidates
- classify evidence into support vs contradiction
- attach local/generated plot paths as media nodes in enriched graph
- generate actual plots with matplotlib or plotly
- replace placeholder molecules with real GenMol outputs

## Why it is not fully live yet

The agent package itself is plain Python code and does not have direct access to OpenClaw tools from inside those modules. So the current scaffold prepares the right data model and artifact flow, but actual tool-mediated search still needs to be orchestrated at the session/agent layer or via a dedicated wrapper.
