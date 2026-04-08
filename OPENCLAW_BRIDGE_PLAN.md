# OPENCLAW_BRIDGE_PLAN.md

## Purpose

Provide the immediate bridge between:
- the Python package orchestration layer
- the OpenClaw runtime `web_search` tool

## Recommended live flow

1. Run the base pipeline
2. Read `artifacts/run/critique_notes.json`
3. For each candidate query, call OpenClaw `web_search`
4. Normalize results into:
   - title
   - url
   - snippet
   - provenance
   - match_type (later exact vs analog)
5. Merge results into `critique_notes.enriched.json`
6. Rebuild KG and reports from enriched critique state

## Why separate this from the package

The package code should remain portable and not assume direct access to OpenClaw tools.
The bridge can be thin and runtime-specific.

## Production path

Later, replace or supplement the OpenClaw bridge with:
- dedicated scholarly API backend
- browser fallback for blocked sources
- figure/media extraction pipeline
