# ORCHESTRATION_PLAN.md

## Goal

Provide a session-level orchestration layer that can:
- run the base pipeline
- enrich critique notes with live search results
- update the KG and reports after evidence enrichment

## Production architecture assumption

The code is explicitly architected around the assumption that we will upgrade to a **high-quality scholarly/web-search API** for production runs.

### Current default
- `search.backend = stub`

### Planned production backend
- `search.backend = planned_scholarly_api`

This should eventually be replaced with a concrete provider such as:
- Exa
- Tavily
- SerpAPI
- Semantic Scholar / Crossref hybrid
- another scholarly web-search API

## Why this architecture

The Python package itself should not assume OpenClaw tools are callable from inside arbitrary modules.
So the right split is:

- **package layer**
  - defines query structure
  - defines evidence schema
  - defines backend interface
  - normalizes evidence into graph-ready objects

- **runtime/orchestration layer**
  - provides actual search implementation
  - can later bind OpenClaw `web_search`, `browser`, or an API client

## Expected production search features

A production search backend should support:
- result ranking quality above generic web search
- scholarly metadata when available
- stable URLs and titles
- retrieval of abstracts/snippets
- figure/plot/media references when possible
- confidence scoring
- exact-match vs analog-match classification

## Near-term next step

Implement an OpenClaw-specific bridge that:
- reads shortlist candidate queries
- calls the current session `web_search`
- writes normalized search hits back to `critique_notes.enriched.json`

That will give us a live bridge now, while preserving the backend abstraction for a stronger provider later.
