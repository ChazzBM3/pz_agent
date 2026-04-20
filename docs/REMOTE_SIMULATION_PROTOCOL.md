# Remote ORCA over Slurm submission protocol

This document defines the recommended first real remote execution path for `pz_agent` for direct ORCA calculations on a remote HPC system.

## Recommendation

Use a **file-backed remote job protocol** with a thin remote wrapper script.

Keep:
- `pz_agent` as the local orchestrator
- direct ORCA execution as the remote calculation layer
- Slurm plus shell or Python wrappers as the execution mechanism

Do **not** put a dedicated agentic execution framework in the steady-state submission path for this narrow simulation workflow.

## Design goals

1. Preserve the current `submit -> check -> extract -> validation_ingest` lifecycle.
2. Keep request and response payloads durable on disk.
3. Make remote execution debuggable with plain files and logs.
4. Keep the execution path narrow, deterministic, and cheap.
5. Avoid hidden state inside an interactive agent session or extra framework.

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
job.inp                # rendered ORCA input
job.out                # ORCA stdout or main output
```

## Minimal lifecycle

### 1. Local handoff

`simulation_handoff` writes a local job bundle with:
- `orca_job.json`
- `input_structure.xyz`
- queue and manifest metadata

That local bundle becomes the submission payload.

### 2. Submit

Local submit should:
1. mint a `submission_id`
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
3. render `job.inp` from `orca_job.json`
4. generate `run_orca_job.sh`
5. submit through Slurm with `sbatch`
6. write `scheduler.json`
7. write `status.json`
8. let the scheduled payload run ORCA
9. write `result.json` on success or `failure.json` on failure
10. move the job directory to `completed/` or `failed/`

A practical split is:
- `remote_submit_orca_job.py` handles validation, directory movement, input rendering, payload generation, and `sbatch`
- `run_orca_job.sh` does the actual scheduled ORCA execution

### 4. Check

Local check should read remote `status.json` and return a `status_envelope`.

Authoritative statuses should come from the remote artifact, not a local default.

### 5. Extract

Local extract should pull:
- `result.json` when complete
- `failure.json` when failed
- optionally `job.out`, logs, and selected output artifacts for provenance

## Required remote artifacts

## `status.json`

Recommended shape:

```json
{
  "contract_version": "orca_slurm.request_response.v1",
  "request_type": "check_simulation",
  "response_type": "status_envelope",
  "candidate_id": "rec_a",
  "submission_id": "submit-001",
  "job_id": "job-001",
  "status": "running",
  "authoritative": true,
  "backend": "orca_slurm",
  "engine": "orca",
  "job_driver": "direct_orca",
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
    "failure": "failure.json",
    "orca_input": "job.inp",
    "orca_output": "job.out"
  },
  "checked_at": "2026-04-20T19:00:00Z"
}
```

## `result.json`

Recommended successful terminal shape:

```json
{
  "contract_version": "orca_slurm.request_response.v1",
  "request_type": "extract_simulation_result",
  "response_type": "result_envelope",
  "candidate_id": "rec_a",
  "submission_id": "submit-001",
  "job_id": "job-001",
  "status": "completed",
  "backend": "orca_slurm",
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
  "contract_version": "orca_slurm.request_response.v1",
  "request_type": "extract_simulation_result",
  "response_type": "failure_envelope",
  "candidate_id": "rec_a",
  "submission_id": "submit-001",
  "job_id": "job-001",
  "status": "failed",
  "backend": "orca_slurm",
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

This is the best starting point because it is simple, observable, and directly compatible with ORCA-over-Slurm execution.

### Phase 2: Scheduler-aware status and parsing hardening

Once phase 1 works, harden the remote path to track:
- scheduler job id
- scheduler state
- working directory
- exit code
- payload script path
- stdout and stderr from the `sbatch` submission call
- parsed ORCA termination and convergence signals from `job.out`

## Suggested config additions

A future real backend config will likely need fields like:

```yaml
simulation:
  backend: orca_slurm
  engine: orca
  remote_target: cluster-alpha
  job_driver: direct_orca

simulation_submit:
  transport: ssh
  remote_host: user@cluster.example.edu
  remote_root: /path/to/pz_agent_jobs
  remote_submit_command: /path/to/bin/remote_submit_orca_job.py
  remote_scheduler: slurm
  stage_method: rsync

simulation_check:
  transport: ssh
  remote_host: user@cluster.example.edu
  remote_root: /path/to/pz_agent_jobs
```

Current cluster-shaped template assumptions now mirror the provided dummy Supercloud-style submission pattern:
- partition: `xeon-p8`
- `#SBATCH -N 1`
- task count derived from ORCA `nprocs`
- `--mem-per-cpu=2000`
- `--no-requeue`
- `module load mpi/openmpi-4.1.8`
- ORCA directory rooted at `/home/gridsan/groups/rgb_shared/software/orca/orca_6_0_0_linux_x86-64_shared_openmpi416`
- scratch-first execution with copy-back into `SLURM_SUBMIT_DIR`

## Acceptance criteria for first real integration

The first real remote integration should be considered successful only if:

1. a local job bundle is copied to the HPC system
2. a remote wrapper renders ORCA input and submits through Slurm
3. the remote side produces authoritative `status.json`
4. local check consumes that remote status artifact
5. local extract ingests a real `result.json` or `failure.json`
6. the current report and validation flow continue to work without contract changes
7. a failed run still lands in the deferred rerun queue with the preserved lineage already implemented

## Implementation recommendation

Build this in the repo as:
1. protocol doc
2. remote wrapper script template
3. SSH-backed ORCA-over-Slurm backend adapter
4. end-to-end acceptance tests around staged remote artifacts

Template added in this repo:
- `docs/remote_submit_orca_job.py`

The wrapper now renders `job.inp` from `orca_job.json` and writes a Slurm payload script that runs `orca job.inp > job.out 2>&1`.

That is the cleanest path from today’s contract scaffolding to a real remote ORCA execution path.
