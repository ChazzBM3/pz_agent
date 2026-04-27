# Transition notes

## Current branch

Use this branch on the other laptop:

- `charles/local-state-2026-04-23-clean`

## Latest pushed commits

- `f4a11e9` - Stop GenMol loop only when both metrics worsen
- `608e716` - Base iteration stopping on score improvement only
- `9382ed3` - Add laptop bootstrap and dry smoke-run helper
- `d776959` - Track followup presets outside artifacts
- `7b1037b` - Add generation loop updates and config changes
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

## First smoke run

Use the CLI entrypoint from the repo venv:

```bash
.venv/bin/python -m pz_agent.cli run configs/phenothiazine_genmol_auto_loop_dry.yaml --run-dir artifacts/smoke_dry
```

Optional quick regression pass:

```bash
.venv/bin/python -m pytest tests/test_genmol_import.py tests/test_htvs_backend.py -q
```

## Notes

- Large generated experiment outputs under `artifacts/` are intentionally ignored for a clean handoff.
- Temporary local debug shell scripts like `tmp_*.sh` are ignored.
- If you need any specific artifact directory from this machine later, transfer it separately rather than versioning it in git.
- Follow-up YAML presets previously living under `artifacts/` were moved to `configs/artifact_presets/` so they are included in git for the laptop handoff.
- A real Grimm smoke test succeeded for round 1 remote GenMol launch, remote output detection, import, recycle-config writing, and re-analysis.
- The current next blocker is multi-round remote orchestration: when round N+1 is still in flight, the loop currently stops with `no_completed_outputs` instead of a resumable `awaiting_remote_outputs` style state.
- Current exploration-biased loop rule: stop only when both solubility and synthesizability worsen beyond tolerance, otherwise continue until convergence or `max_rounds`.
