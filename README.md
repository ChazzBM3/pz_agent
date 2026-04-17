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

## RDKit environment note

This project expects RDKit to be available inside the repo virtualenv.
Use the venv interpreter for repo scripts and pipeline runs:

```bash
.venv/bin/python -m pz_agent.cli run configs/d3tales_demo.yaml --run-dir artifacts/run
```

If you use the system `python3` instead, RDKit may appear missing even when it is installed in `.venv`.

Quick check:

```bash
.venv/bin/python - <<'PY'
from pz_agent.chemistry.normalize import RDKIT_AVAILABLE
print(RDKIT_AVAILABLE)
PY
```

If RDKit is not installed in the venv, reinstall project dependencies from the activated venv:

```bash
source .venv/bin/activate
pip install -e '.[dev]'
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
- supervised graph expansion into action queues
- simulation handoff packaging and submission scaffolding

Current priority: validate and harden the simulation-first execution path, then tighten scoring, evidence semantics, and downstream result ingestion.
