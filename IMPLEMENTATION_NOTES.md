# IMPLEMENTATION_NOTES.md

## Current status

The codebase now supports:
- GenMol-oriented generation framing
- synthesizability / solubility-first screening framing
- critique bundles with text evidence stubs
- multimodal KG nodes for image/plot/media artifacts
- evidence-aware report generation with placeholder plot artifacts

## Next coding step

The next step should be live tool integration for critique ingestion:
- call `web_search` for candidate queries
- normalize hits into exact-match vs analog-match evidence
- attach URLs/titles/snippets to evidence nodes
- generate actual plots with matplotlib or plotly
- store those plots in `artifacts/plots/`
- attach plot paths as `MediaArtifact` nodes

## Why it is not fully live yet

The agent package itself is plain Python code and does not have direct access to OpenClaw tools from inside those modules. So the current scaffold prepares the right data model and artifact flow, but actual tool-mediated search still needs to be orchestrated at the session/agent layer or via a dedicated wrapper.
