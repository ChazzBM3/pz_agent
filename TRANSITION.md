# Transition notes

## Use this exact repo state

Primary continuation target:
- branch: `charles/local-state-2026-04-23-clean`
- current head: `6d2976d57f8c42bda5bfeba601a661db06770ec6`

This is the branch the other laptop should use unless Charles explicitly decides to branch again.

## Latest important commits on this branch

- `6d2976d` - Document current loop state and next remote-orchestration step
- `f4a11e9` - Stop GenMol loop only when both metrics worsen
- `608e716` - Base iteration stopping on score improvement only
- `9382ed3` - Add laptop bootstrap and dry smoke-run helper
- `d776959` - Track followup presets outside artifacts
- `a3b87bc` - Prepare repo handoff for laptop transition
- `bb63eee` - previous local continuation point carried in memory

## Clone / continue

```bash
git clone git@github.com:ChazzBM3/pz_agent.git
cd pz_agent
git checkout charles/local-state-2026-04-23-clean
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## What another OpenClaw should read first

Read these before touching code:
1. `README.md`
2. `TRANSITION.md`
3. `PROJECT_SUMMARY.md`
4. `PLAN.md`

That is the shortest path to reconstructing intent plus current operational reality.

## First smoke run

Use the CLI entrypoint from the repo venv:

```bash
.venv/bin/python -m pz_agent.cli run configs/phenothiazine_genmol_auto_loop_dry.yaml --run-dir artifacts/smoke_dry
```

Optional quick regression pass:

```bash
.venv/bin/python -m pytest tests/test_genmol_import.py tests/test_htvs_backend.py -q
```

## What is actually working right now

- HTVS-backed Supercloud execution is the main live remote-execution path
- a Grimm-backed GenMol smoke test succeeded through one full remote round
- remote launch, output detection, import, recycle-config writing, and re-analysis all worked in that one-round test
- the exploration-biased loop rule now stops only when both solubility and synthesizability worsen beyond tolerance

## What is still the next blocker

The current next implementation target is multi-round remote orchestration.

Specifically:
- when round N+1 is still `submitted` or `running`, the loop currently stops with `no_completed_outputs`
- that should become a resumable waiting state, closer to `awaiting_remote_outputs`
- the next coding pass should preserve enough round metadata to resume monitor -> recycle -> analysis later instead of treating in-flight work as terminal

## Important non-git local state

- Large generated experiment outputs under `artifacts/` are intentionally ignored for a cleaner handoff.
- Temporary local debug shell scripts like `tmp_*.sh` are ignored.
- Follow-up YAML presets previously living under `artifacts/` were moved to `configs/artifact_presets/` so they are included in git.
- `artifacts/kg_prod_2026_04_22/` on this machine contains about 1.0G of D3TaLES KG snapshots and audit outputs.
- If the other laptop needs any exact artifact directory from this machine, transfer it separately rather than expecting git to provide it.
