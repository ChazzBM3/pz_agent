# PROJECT_SUMMARY.md

## 1. Project scope and current strategic direction

`pz_agent` is a phenothiazine screening workflow built as a modular scientific pipeline rather than a chat-style agent system.

The repo now centers on:
- phenothiazine-focused candidate generation/import
- chemistry normalization and stable molecule identity
- structure-first retrieval and evidence gathering
- KG-backed critique and reranking
- supervised graph expansion into actionable follow-up work
- simulation handoff and submission packaging for top candidates

The project is intentionally **not** broad de novo discovery. It is a tightly-scoped screening and validation workflow for phenothiazine derivatives.

## 2. Architectural stance

The implementation uses a **plain-Python multi-agent pipeline without LangGraph**:
- explicit stages
- shared `RunState`
- durable JSON artifacts
- deterministic orchestration
- config-driven stage selection

That decision still looks correct. The repo has become substantially richer, but it still benefits from being inspectable, testable, and recoverable from artifacts on disk.

## 3. What is now genuinely distinctive

The strongest part of the project is no longer just the stage layout. It is the combination of:

1. **Identity-aware chemistry and KG flow**
   - stable molecule identity keys, representation anchors, and non-destructive KG merge behavior

2. **Evidence-aware ranking and critique**
   - ranking can consume measured-property context, literature support, identity-level evidence, and belief-like support structures

3. **Supervised self-expansion**
   - the system can derive frontier hypotheses from KG state and turn them into structured action requests rather than free-form autonomous wandering

4. **Screening-to-simulation bridge**
   - top candidates can now be packaged into simulation queue artifacts and submission records, and usable validation results can be ingested back into reports and the KG

5. **Scientific memory with provenance**
   - molecules, papers, predictions, evidence, dataset records, reports, and queued actions are all represented as campaign memory rather than one-off run debris

## 4. Current repo status

## Overall maturity

The repo is now a **serious research prototype with a working but still-stubbed operational loop**.
It is no longer just an architecture scaffold. The interesting question is no longer “what should the system be?” so much as “which part of the loop should be hardened next?”

GitHub:
- <https://github.com/ChazzBM3/pz_agent>

## What is implemented

### Orchestration and CLI
- deterministic stage runner
- config-driven stage order with stage validation
- `RunState` snapshots after each stage
- CLI entrypoints for run and auxiliary workflows

### Chemistry and identity
- RDKit-backed normalization in the repo venv
- stable molecule identity keys
- canonical SMILES / InChI / InChIKey handling
- decoration-aware identity fields
- identity-aware KG retrieval and merge behavior
- representation-level evidence attachment

### Retrieval, critique, and reranking
- patent and scholarly retrieval stages
- critique generation and critique-aware reranking
- visual identity and multimodal support paths
- evidence deduplication improvements
- structure-first retrieval direction is established

### Knowledge graph and campaign memory
- local JSON property graph with provenance-rich entities
- molecule, representation, paper, claim, prediction, media, and dataset-record support
- identity anchors preserved across runs
- graph-expansion proposals can be derived from live KG state

### Supervised expansion and action queueing
- supervised graph expansion from KG frontier conditions
- proposal filtering through critic rules
- accepted action queue entries such as:
  - `simulation_request`
  - `evidence_query`
  - `bridge_expansion`

### Simulation and validation path
- `simulation_handoff` packages shortlisted candidates into queue records and per-candidate job bundles
- queue and manifest artifacts are written to disk
- current default packaged calculation is an ORCA geometry optimization / minimum search using `PBE`, `def2-SVP`, `D3`, and implicit water via `CPCM`
- `simulation_submit` emits backend submission records through a simulation backend abstraction
- `validation_ingest` reads remote result payloads, normalizes outputs/status, classifies result quality, and writes `validation_results.json`
- usable validation results are added back into the KG as `SimulationResult` and `ValidationOutcome` nodes
- current AtomisticSkills submit path remains stubbed for contract validation rather than live remote execution

## 5. Main gaps

The biggest remaining gap is now **remote execution hardening and downstream rigor**, not basic loop closure.

### 1. Validation path now works, but needs stronger contract hardening
The repo can now generate simulation-ready artifacts, emit submission records, ingest completed results, and write usable validation outcomes back into the KG and reports. The next hardening work is around making that path operationally trustworthy:
- queue artifacts still need explicit contract validation against a real executor
- submission records need to be checked against a real remote-execution design
- result payload requirements should be tightened and documented as an acceptance contract
- downstream validator / result-consumer stages should become more formal than simple ingest

### 2. Scoring remains partially heuristic
- synthesizability and solubility scoring are still not production-grade
- benchmark gates are not yet strong enough to fail a run with confidence
- ranking is stronger structurally than scientifically calibrated

### 3. Chemistry reasoning is still uneven
- bridge and substituent reasoning are richer than before, but still not fully chemistry-native
- exact-vs-analog evidence alignment is improved, not solved
- some chemistry interpretation remains heuristic

### 4. Evidence semantics still need tightening
- contradiction handling is still shallow
- evidence weighting can still drift toward over-crediting weak or correlated signals
- report language needs to stay explicit about measured vs inferred vs predicted support

## 6. Recommended near-term work order

The recommended next sequence is:

1. **Remote simulation contract hardening**
   - define the required request/response contract for a real ORCA or AtomisticSkills target
   - inspect emitted queue, manifest, submission, and validation artifacts for completeness
   - turn the current stub-backed simulation path into a testable acceptance gate

2. **Result-ingest and validator hardening**
   - define exactly what a remote ORCA or AtomisticSkills execution target must accept and return
   - keep `pz_agent` as orchestrator, not the executor

3. **Then deeper bridge chemistry refinement**
   - make bridge reasoning compete for simulation budget using actual validation outcomes instead of only internal belief structure

## 7. Bottom line

`pz_agent` is now best understood as a **KG-backed phenothiazine screening and validation orchestrator**.

The repo already has enough architecture for the next meaningful milestone. The highest-leverage move is to harden the now-working **screening -> simulation -> validation** loop into a real remote-execution contract before doing another large conceptual expansion.
