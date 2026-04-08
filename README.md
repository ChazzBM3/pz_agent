# pz_agent

Phenothiazine screening project plan using a modular multi-agent workflow without LangGraph.

This repo captures:
- the intended UROP project scope
- a practical agent architecture
- an implementation roadmap
- candidate deliverables and evaluation criteria

See `PLAN.md` for the full plan.
See `PROJECT_SUMMARY.md` for a concise project + repo status summary.

## Development

Create or activate the repo virtualenv, then install editable with dev extras:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

## Current scaffold

The repo now includes a Python package scaffold for:
- staged pipeline execution
- external GenMol import
- chemistry normalization with RDKit support
- synthesizeability / solubility scoring scaffolds
- weighted and literature-aware reranking
- a knowledge-graph builder
- enriched critique / literature workflows

Next step: replace heuristics and placeholders with stronger chemistry-aware matching and real production scoring.
