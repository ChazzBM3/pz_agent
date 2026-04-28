# GenMol Loop Control Schema

This document defines how convergence criteria for the GenMol iteration loop are supplied.

## Sources of truth

The loop resolves controls in this priority order:

1. **Agent-produced generation action payload** (`payload.loop_controls`)
2. **User config defaults** (`generation.loop.*` and `screening.primary_objectives`)

If no agent override is present, the loop uses the user config.

## Agent payload contract

Upstream agents that enqueue a `generation_iteration` action may include:

```json
{
  "action_type": "generation_iteration",
  "candidate_id": "cand_123",
  "priority": 0.82,
  "payload": {
    "candidate": {"smiles": "..."},
    "loop_controls": {
      "primary_objectives": ["solubility"],
      "convergence_tolerance": {
        "solubility": 0.02,
        "synthesizability": 0.01
      },
      "taper_min_improvement": {
        "solubility": 0.01,
        "synthesizability": 0.005
      }
    }
  }
}
```

Canonical helper for emitting this shape:

- `pz_agent.generation_loop_controls.build_loop_controls(...)`

Use that helper instead of hand-building `payload.loop_controls` dictionaries.

## Fields

### `payload.loop_controls.primary_objectives`

- Type: array of strings
- Allowed values: `"solubility"`, `"synthesizability"`
- Meaning: metrics that determine ranking emphasis and loop stopping behavior

Examples:

- `["solubility"]` → solubility-only stopping/ranking
- `["synthesizability", "solubility"]` → two-objective stopping/ranking

### `payload.loop_controls.convergence_tolerance`

- Type: object keyed by metric name
- Meaning: absolute delta threshold treated as converged for each metric

### `payload.loop_controls.taper_min_improvement`

- Type: object keyed by metric name
- Meaning: negative delta threshold that counts as worsening for stop checks

## Normalization rules

- Missing metrics inherit from user config defaults.
- Missing `primary_objectives` inherits from `screening.primary_objectives`.
- Unknown objective names are ignored.
- If no valid objectives remain, fallback is `["solubility", "synthesizability"]`.

## Current behavior

- Ranking honors `screening.primary_objectives`.
- Loop convergence/worsening checks honor resolved `primary_objectives`.
- For the legacy two-objective case, the stop reason remains `both_metrics_worsened` for compatibility.
- For agent-driven subsets such as solubility-only, the stop reason is `primary_objectives_worsened`.

## Recommendation for upstream agents

Agents should only emit `payload.loop_controls` when they have a concrete reason to override user defaults, for example:

- a user explicitly requests solubility-only optimization
- a critic determines one metric should be monitored but not optimized
- a round-specific exploration policy needs looser/tighter convergence

Otherwise, leave `loop_controls` absent and let user config drive behavior.
