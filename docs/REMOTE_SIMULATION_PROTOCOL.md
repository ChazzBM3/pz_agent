# Remote simulation submission protocol

This document defines the recommended first real remote execution path for `pz_agent` when AtomisticSkills is installed on a supercomputer.

## Recommendation

Use a **file-backed remote job protocol** with a thin remote wrapper script.

Keep:
- `pz_agent` as the local orchestrator
- AtomisticSkills as the remote execution substrate
- scheduler or shell scripts as the execution mechanism

Do **not** put an interactive Claude Code session in the steady-state submission path. Claude Code is useful for setup, debugging, and remote maintenance, but routine simulation submission should be deterministic and script-driven.

## Design goals

1. Preserve the current `submit -> check -> extract -> validation_ingest` lifecycle.
2. Keep request and response payloads durable on disk.
3. Make remote execution debuggable with plain files and logs.
4. Support migration from simple SSH submission to scheduler-native submission later.
5. Avoid hidden state inside an interactive agent session.

## Core model

Each simulation job is represented by a remote job directory.

Recommended remote layout:

```text
<remote_root>/
  inbox/<job_id>/
  running/<job_id>/
  completed/<job_id>/
  failed/<job_id>/
```

Each job directory should contain at minimum:

```text
orca_job.json
input_structure.xyz
status.json
result.json            # on success
failure.json           # on terminal failure
run.log
scheduler.json
run_orca_job.sh        # generated scheduled payload script
```

## Minimal lifecycle

### 1. Local handoff

`simulation_handoff` already writes a local job bundle with:
- `orca_job.json`
- `input_structure.xyz`
- queue and manifest metadata

That local bundle becomes the submission payload.

### 2. Submit

Local submit should:
1. choose or mint a `submission_id`
2. derive a remote `job_id`
3. copy the bundle to remote `inbox/<job_id>/`
4. invoke one remote wrapper command
5. receive a structured submission acknowledgement

Recommended transport for the first implementation:
- `scp` or `rsync` for bundle staging
- `ssh` for remote wrapper invocation

### 3. Remote wrapper behavior

A remote wrapper should:
1. validate required files exist
2. move the job from `inbox/` to `running/`
3. submit through Slurm or another scheduler
4. write `scheduler.json`
5. write `status.json`
6. let the scheduled payload run AtomisticSkills ORCA execution
7. update `status.json` as state changes
8. write `result.json` on success or `failure.json` on failure
9. move the job directory to `completed/` or `failed/`

A practical split is:
- `remote_submit_orca_job.py` handles validation, directory movement, and `sbatch`
- a generated payload script such as `run_orca_job.sh` does the actual scheduled execution

### 4. Check

Local check should read remote `status.json` and return a `status_envelope`.

Authoritative statuses should come from the remote artifact, not a local default.

### 5. Extract

Local extract should pull:
- `result.json` when complete
- `failure.json` when failed
- optional logs or selected artifacts for provenance

## Required remote artifacts

## `status.json`

Recommended shape:

```json
{
  "contract_version": "atomisticskills.request_response.v1",
  "request_type": "check_simulation",
  "response_type": "status_envelope",
  "candidate_id": "rec_a",
  "submission_id": "submit-001",
  "job_id": "job-001",
  "status": "running",
  "authoritative": true,
  "backend": "atomisticskills_orca",
  "engine": "orca",
  "skill": "chem-dft-orca-optimization",
  "execution_mode": "remote",
  "remote_target": "cluster-alpha",
  "scheduler": {
    "system": "slurm",
    "scheduler_job_id": "12345678",
    "queue": "normal"
  },
  "paths": {
    "run_log": "run.log",
    "result": "result.json",
    "failure": "failure.json"
  },
  "checked_at": "2026-04-20T19:00:00Z"
}
```

## `result.json`

Recommended successful terminal shape:

```json
{
  "contract_version": "atomisticskills.request_response.v1",
  "request_type": "extract_simulation_result",
  "response_type": "result_envelope",
  "candidate_id": "rec_a",
  "submission_id": "submit-001",
  "job_id": "job-001",
  "status": "completed",
  "backend": "atomisticskills_orca",
  "engine": "orca",
  "simulation_type": "geometry_optimization",
  "outputs": {
    "status": "completed",
    "final_energy": -1234.567,
    "optimized_structure": "...",
    "groundState.solvation_energy": -12.34,
    "groundState.homo": -5.1,
    "groundState.lumo": -2.2,
    "groundState.homo_lumo_gap": 2.9,
    "groundState.dipole_moment": 4.8
  },
  "operation": {
    "check_only": false,
    "remote_settings": {
      "target": "cluster-alpha"
    }
  },
  "provenance": {
    "request_id": "simreq::run_x::rec_a"
  }
}
```

## `failure.json`

Recommended failed terminal shape:

```json
{
  "contract_version": "atomisticskills.request_response.v1",
  "request_type": "extract_simulation_result",
  "response_type": "failure_envelope",
  "candidate_id": "rec_a",
  "submission_id": "submit-001",
  "job_id": "job-001",
  "status": "failed",
  "backend": "atomisticskills_orca",
  "engine": "orca",
  "simulation_type": "geometry_optimization",
  "failure_kind": "convergence_failure",
  "failure_message": "SCF did not converge",
  "operation": {
    "check_only": false,
    "remote_settings": {
      "target": "cluster-alpha"
    }
  },
  "provenance": {
    "request_id": "simreq::run_x::rec_a"
  }
}
```

## Recommended backend phases

### Phase 1: SSH plus file staging

Implement the first real backend around:
- local `scp` or `rsync`
- local `ssh remote_submit_orca_job.py <remote_job_dir>`
- local `ssh cat <remote_job_dir>/status.json`
- local `scp` or `rsync` back `result.json` or `failure.json`

This is the best starting point because it is simple, observable, and compatible with later scheduler hardening.

### Phase 2: Scheduler-native remote wrapper

Once phase 1 works, the remote wrapper should submit via Slurm and track:
- scheduler job id
- scheduler state
- working directory
- exit code
- payload script path
- stdout and stderr from the `sbatch` submission call

The `status.json` contract can stay stable while the remote implementation grows more sophisticated.

The repo template `docs/remote_submit_orca_job.py` is now explicitly Slurm-shaped and generates a `run_orca_job.sh` payload script plus `scheduler.json`.

## Claude Code role

Claude Code should be used for:
- creating the remote wrapper scripts
- inspecting remote environment details
- debugging failed submissions
- iterating on scheduler integration

Claude Code should **not** be the normal submission engine for production jobs.

## Suggested config additions

A future real backend config will likely need fields like:

```yaml
simulation:
  backend: atomisticskills_orca
  remote_target: cluster-alpha

simulation_submit:
  transport: ssh
  remote_host: user@cluster.example.edu
  remote_root: /path/to/pz_agent_jobs
  remote_submit_command: /path/to/bin/submit_orca_job.py
  stage_method: rsync

simulation_check:
  transport: ssh
  remote_host: user@cluster.example.edu
  remote_root: /path/to/pz_agent_jobs
```

## Acceptance criteria for first real integration

The first real remote integration should be considered successful only if:

1. a local job bundle is copied to the supercomputer
2. a remote wrapper produces authoritative `status.json`
3. local check consumes that remote status artifact
4. local extract ingests a real `result.json` or `failure.json`
5. the current report and validation flow continue to work without contract changes
6. a failed run still lands in the deferred rerun queue with the preserved lineage you already added

## Implementation recommendation

Build this in the repo next as:
1. protocol doc
2. remote wrapper script templates
3. a real SSH-backed AtomisticSkills backend adapter
4. end-to-end acceptance tests around staged remote artifacts

Template added in this repo:
- `docs/remote_submit_orca_job.py`

That is the cleanest path from today’s contract scaffolding to real supercomputer execution.
