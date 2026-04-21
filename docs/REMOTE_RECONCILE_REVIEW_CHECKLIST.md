# Remote reconcile sweep review checklist

Use this to review Codex-generated cluster-side reconciliation scripts before adopting them.

## 1. Paths and environment

- Uses real cluster paths discovered from the environment, not made-up placeholders
- Uses an explicit Python path suitable for cron on this cluster
- Documents any needed environment bootstrapping for cron
- Notes whether `sacct` and `squeue` are on cron's default PATH or need absolute paths

## 2. Correct source of truth

- Treats Slurm as execution authority
- Treats file artifacts (`status.json`, `result.json`, `failure.json`) as workflow state
- Does not depend on tmux for authoritative status
- Does not create a second shadow state store

## 3. Sweep behavior

- Iterates `running/*` rather than one cron entry per job
- Skips non-directories safely
- Skips malformed job dirs without crashing the whole run
- Continues processing after one bad job
- Returns nonzero if any per-job reconcile fails
- Produces a concise end-of-run summary

## 4. Locking and overlap protection

- Prevents overlapping cron runs
- Clearly documents lock strategy (`flock`, `lockf`, or Python lockfile)
- Handles stale lock behavior sensibly
- Keeps lock scope at the sweep level, not per job unless justified

## 5. Logging

- Writes logs to a stable location
- Produces concise cron-friendly logs
- Includes enough context to identify which job failed
- Avoids excessively noisy per-job output during normal operation
- Captures stderr for failed reconcile calls

## 6. Reconcile correctness

- Calls the per-job reconcile script, rather than duplicating business logic everywhere
- Preserves the file-backed protocol contract
- Works when `result.json` or `failure.json` already exists
- Works when only `scheduler.json` and `status.json` exist
- Handles missing `scheduler_job_id` gracefully
- Does not overwrite valid terminal artifacts unnecessarily

## 7. Slurm-awareness

- Uses `sacct` first and `squeue` second, or documents a cluster-specific reason not to
- Handles scheduler states cleanly
- Treats terminal failure states as failures
- Documents any site-specific Slurm quirks discovered on this cluster

## 8. Cron readiness

- Provides an exact cron stanza
- Uses absolute paths in the cron stanza
- Redirects stdout/stderr intentionally
- Notes any required shell or module environment caveats
- Recommends a sensible interval, usually every 3 to 5 minutes

## 9. Security and operability

- Avoids shell injection hazards from job directory names or paths
- Uses straightforward subprocess invocation where possible
- Fails visibly rather than silently masking real problems
- Keeps the script simple enough for an operator to debug quickly

## 10. Adoption decision

Before merging, confirm:

- I know where the scripts will live on the cluster
- I know what cron user will run them
- I know where logs will go
- I know how to test one manual run before enabling cron
- I know how to disable or roll back the cron entry if needed
