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

On a new machine or in a fresh OpenClaw workspace, use the repo virtualenv and the CLI entrypoint rather than calling modules directly:

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
- head commit: run `git log --oneline -1` after pulling; this branch is the continuation target
- latest meaningful repo step: objective-aware GenMol controls plus ORCA-xTB/HTVS continuation docs

If you want a quick regression check before a real remote launch:

```bash
source .venv/bin/activate
pytest tests/test_genmol_import.py tests/test_htvs_backend.py -q
```

For a dry-loop helper script:

```bash
./scripts/smoke_genmol_dry.sh
```

## April 28 OpenClaw continuation notes

This branch contains the current phenothiazine / Grimm GenMol / HTVS handoff state. If another OpenClaw instance is picking this up, start with these files in this order:

1. `README.md`
2. `TRANSITION.md`
3. `PROJECT_SUMMARY.md`
4. `docs/GENMOL_LOOP_CONTROL_SCHEMA.md`
5. `PLAN.md`

Then orient around this concrete state:

- the live remote-execution direction is the HTVS-backed Supercloud path, not the older direct ORCA-over-Slurm scaffolding
- a Grimm-backed remote GenMol smoke test succeeded for one completed round, and in-flight multi-round work is now represented as `awaiting_remote_outputs`
- large local artifacts are intentionally not fully versioned, especially under `artifacts/`
- `artifacts/kg_prod_2026_04_22/` on the original machine contains about 1.0G of D3TaLES KG snapshots and audit outputs; transfer it separately if exact files are needed

For reproducing the current solubility-only ranking run:

```bash
python -m pz_agent.cli run configs/genmol_grimm_compare_solubility_only_20260428.yaml \
  --run-dir artifacts/genmol_grimm_compare_solubility_only_20260428
```

For the live remote simulation path, use HTVS on Supercloud. The active Supercloud checkout used during testing was `/home/gridsan/cmusgrave/htvs`.

Important operational details from the latest run:

- `supercloud` was a local shell alias for `ssh cmusgrave@txe1-login.mit.edu`; do not assume it is resolvable from other hosts.
- The intended xTB workflow is HTVS job config `xtb_opt_orca`, i.e. ORCA-mediated GFN2-xTB, not standalone native xTB.
- The fixed Supercloud `xtb_opt_orca` path uses ORCA 6.0.0 with ALPB water (`%xtb doalpb true; alpbsolvent "water"`).
- Solvation energy should be extracted as a derived paired single-point delta on the optimized geometry: `E_ALPB_water - E_gas`, because the tested ORCA-xTB optimization output did not expose a clean separate ALPB `dGsolv` field.
- `genmol_0005` remained blocked by HTVS `addxyz` formula / stoichiometry validation and should not block progress on the other candidates.


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

Recent April 28 status:
- objective-aware ranking now honors `screening.primary_objectives`, including solubility-only prioritization while still logging synthesizability
- GenMol iteration actions now carry normalized `payload.loop_controls`, and the loop uses those controls for convergence / worsening checks
- the active simulation handoff set came from the solubility-only Grimm GenMol comparison; recommended top candidates were `genmol_0001`, `genmol_0006`, `genmol_0004`, `genmol_0005`, `genmol_0011`, `genmol_0012`, and `genmol_0013`
- six candidates submitted successfully through HTVS/Supercloud; `genmol_0005` remains the known pre-ORCA HTVS `addxyz` blocker
- the intended ORCA-mediated xTB path (`xtb_opt_orca`) was repaired on the Supercloud HTVS checkout and smoke-tested on `genmol_0011`
- next highest-leverage step: rerun the six usable candidates through `xtb_opt_orca`, extract optimized structure, final solvated energy, derived solvation energy, gradients/status, and refresh the KG reintegration table

Earlier April 27 status:
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
