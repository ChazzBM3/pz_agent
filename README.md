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

## Fresh laptop quick start

On a new machine, use the repo virtualenv and the CLI entrypoint rather than calling modules directly:

```bash
git clone git@github.com:ChazzBM3/pz_agent.git
cd pz_agent
git checkout charles/local-state-2026-04-23-clean
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m pz_agent.cli run configs/phenothiazine_genmol_auto_loop_dry.yaml --run-dir artifacts/smoke_dry
```

Current handoff baseline:
- branch: `charles/local-state-2026-04-23-clean`
- head commit: `6d2976d57f8c42bda5bfeba601a661db06770ec6`
- latest meaningful repo step: document current GenMol loop state and the next remote-orchestration gap

If you want a quick regression check before a real remote launch:

```bash
source .venv/bin/activate
pytest tests/test_genmol_import.py tests/test_htvs_backend.py -q
```

For a dry-loop helper script:

```bash
./scripts/smoke_genmol_dry.sh
```

## Continuation notes for another OpenClaw

If another OpenClaw instance is picking this up, start with these files in this order:
- `README.md`
- `TRANSITION.md`
- `PROJECT_SUMMARY.md`
- `PLAN.md`

Then orient around this concrete state:
- the live remote-execution direction is the HTVS-backed Supercloud path, not the older direct ORCA-over-Slurm scaffolding
- a Grimm-backed remote GenMol smoke test succeeded for one completed round
- the current next implementation target is making multi-round remote GenMol loops resumable when the next round is still `submitted` or `running`
- large local artifacts are not fully versioned, especially under `artifacts/`

Important local-only data on this machine:
- `artifacts/kg_prod_2026_04_22/` contains about 1.0G of D3TaLES KG snapshots and audit outputs
- if the other laptop needs those exact files, transfer them separately rather than expecting git to provide them

## D3TaLES KG audit workflow

To build and audit the baseline D3TaLES production KG, including exclusion of zero-information rows, run:

```bash
./.venv/bin/python scripts/d3tales_kg_audit.py --csv data/d3tales.csv --outdir artifacts/kg_prod_2026_04_22 --limit 50000
```

This writes:
- `d3tales_kg.json` (raw graph)
- `d3tales_kg.filtered.json` (recommended production baseline)
- `d3tales_kg_audit.json` (removed-row list and before/after counts)

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

Current priority: validate and harden the simulation-first execution path around the HTVS-backed Supercloud flow, keep failed calculations logged cleanly for operator follow-up, then tighten scoring, evidence semantics, downstream result ingestion, and KG-guided prioritization.

Recent April 27 status:
- Grimm-backed GenMol remote smoke testing succeeded for a single completed round
- the GenMol loop stop rule is currently exploration-biased and stops only when both solubility and synthesizability worsen beyond tolerance
- in-flight multi-round remote GenMol work is now reported as `awaiting_remote_outputs` instead of terminal `no_completed_outputs`; config-level resume is available via `generation.loop.resume_iteration_run_dir`, and the next real gap is a first-class resume command/operator wrapper

## Current simulation defaults

Unless overridden in config, simulation handoff currently packages candidate jobs with these defaults:
- engine: `orca`
- simulation type: `geometry_optimization`
- optimization type: `min`
- functional: `PBE`
- basis set: `def2-SVP`
- dispersion correction: `D3`
- implicit solvent model: `CPCM`
- solvent: `water`
- requested outputs:
  - `optimized_structure`
  - `final_energy`
  - `status`

These defaults live in `src/pz_agent/agents/simulation_handoff.py` and are intended as the current remote-execution packaging contract, not as a claim that the repo already runs ORCA locally.

See `artifacts/htvs_adapter_demo/demo_htvs_adapter.yaml` plus the HTVS backend under `src/pz_agent/simulation/backends/htvs.py` for the current primary remote execution path. Failed calculations are logged in `simulation_failures.json`; completed results flow through validation with explicit usable / partial / failed quality assessment. `docs/REMOTE_SIMULATION_PROTOCOL.md` remains useful as legacy design context for the older direct ORCA-over-Slurm path.
