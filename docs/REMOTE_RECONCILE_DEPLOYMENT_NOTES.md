# Remote reconcile deployment notes

These notes describe how the cluster-side reconcile sweep should fit into the `pz_agent` HTVS-backed remote ORCA flow.

## Current local/remote split

Local `pz_agent` now supports:
- remote handoff execution from `simulation_submit`
- remote `status.json` fetch from `simulation_check`
- remote `result.json` / `failure.json` fetch from `simulation_extract`
- deferred rerun queue construction for failed simulations

Remote helper templates in this repo:
- `docs/remote_submit_orca_job.py`
- `docs/remote_reconcile_orca_job.py`

The next cluster-side operational layer is a sweep script that iterates `running/*` and invokes `remote_reconcile_orca_job.py` for each job.

## Recommended cluster deployment layout

Prefer a stable ops location on the cluster, for example:

```text
<ops_root>/
  remote_submit_orca_job.py
  remote_reconcile_orca_job.py
  remote_reconcile_orca_jobs.py
  logs/
```

Keep this separate from volatile run directories.

Example remote job root:

```text
<remote_job_root>/
  inbox/
  running/
  completed/
  failed/
```

## Recommended cron model

Use one cron entry for the sweep script, not one cron line per job.

Recommended cadence:
- every 5 minutes for normal use
- every 2 to 3 minutes only if the cluster and queue volume justify it

The cron job should:
1. acquire a sweep-level lock
2. iterate `running/*`
3. call the per-job reconcile helper
4. log a concise summary

## Recommended config notes for future pz_agent integration

The current local code does not need all of these fields yet, but these are the most natural config anchors if we want to formalize deployment metadata later.

```yaml
simulation_submit:
  transport: ssh
  ssh_host: user@cluster.example.edu
  htvs_root: /path/to/htvs
  remote_job_root_base: /path/to/pz_agent_jobs/inbox
  project: pz_agent_htvs
  job_config: dft_opt_orca
  source_jobconfig: seed_xyz_import

simulation_check:
  transport: ssh
  ssh_host: user@cluster.example.edu

simulation_extract:
  transport: ssh
  ssh_host: user@cluster.example.edu

simulation_remote_ops:
  reconcile_script: /path/to/remote_reconcile_orca_job.py
  reconcile_sweep_script: /path/to/remote_reconcile_orca_jobs.py
  running_root: /path/to/pz_agent_jobs/running
  log_dir: /path/to/logs
  cron_interval: "*/5 * * * *"
```

Compatibility note: local adapters still accept legacy wrapper-style keys like `remote_host`, `remote_root`, and `remote_submit_command`, but new deployment examples should use the HTVS-native fields above.

## Manual validation before enabling cron

Before enabling cron cluster-side:

1. submit one test job
2. verify the job appears under `running/`
3. run the per-job reconcile helper manually
4. inspect `status.json` and `scheduler.json`
5. run the sweep script manually
6. confirm terminal jobs move into `completed/` or `failed/`
7. only then enable cron

## Review focus when Codex returns

Check especially for:
- cron-safe Python path
- lock strategy
- log path choice
- actual Slurm command behavior on the cluster
- whether `sacct` is delayed or restricted on this site
- whether the script needs absolute paths to `sacct` or `squeue`

## Design stance

Keep the system boring:
- Slurm decides execution state
- files store workflow state
- cron performs periodic repair
- tmux is optional operator convenience only
