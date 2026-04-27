# Transition notes

## Current branch

Use this branch on the other laptop:

- `charles/local-state-2026-04-23-clean`

## Latest pushed commits

- `7b1037b` - Add generation loop updates and config changes
- `bb63eee` - previous local continuation point carried in memory

## Clone / continue

```bash
git clone git@github.com:ChazzBM3/pz_agent.git
cd pz_agent
git checkout charles/local-state-2026-04-23-clean
```

## Notes

- Large generated experiment outputs under `artifacts/` are intentionally ignored for a clean handoff.
- Temporary local debug shell scripts like `tmp_*.sh` are ignored.
- If you need any specific artifact directory from this machine later, transfer it separately rather than versioning it in git.
