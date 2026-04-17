# Production Readiness for `pz_agent`

## Current workflow

1. Ingest candidates from D3TaLES CSV or external GenMol output
2. Standardize molecules and attach descriptors / identity
3. Run structure-first retrieval
   - visual identity
   - PubChem structure expansion
   - patent retrieval
   - scholarly retrieval
4. Run surrogate screening
5. Build/update KG snapshot
6. Rank + critique + critique rerank
7. Generate graph expansion proposals / action queue
8. Write report and prepare simulation handoff shortlist
9. Stage or emit simulation submission records

## What is already in place

- Pipeline orchestration is coherent and testable
- D3TaLES ingestion works for demo-scale runs
- Structure-first retrieval path is wired into the demo config
- KG-backed critique and reranking are operational
- Adaptive graph-expansion loop is functioning as a supervised scaffold
- D3TaLES dataset-record provenance is first-class in the KG
- Stable cross-run molecule identity keys are present
- Stable identity anchors are represented as `MolecularRepresentation` nodes
- KG retrieval is identity-aware
- KG merge reinforces identity grouping non-destructively
- Critique claims and evidence can attach at the identity-anchor level while preserving run-local links

## Main bottlenecks before pseudo-production runs

### 1. Production-grade ranking and scoring
- Replace placeholder ranker behavior with explicit evidence-aware aggregation
- Make ranking deliberately consume:
  - predicted properties
  - measured-property support
  - identity-level evidence
  - contradiction signals
  - uncertainty/confidence where available
- Add benchmark thresholds that can fail a run
- Add ranking regression fixtures so scoring changes are testable

### 2. Evidence reliability and anti-double-counting
- Improve exact-vs-analog identity resolution
- Tighten literature/patent relevance filtering
- Prevent over-crediting the same evidence through both candidate-local and identity-level paths
- Make contradiction signals influence downstream ranking more explicitly

### 3. Simulation handoff and submission packaging
- Promote shortlist sorting to a true simulation queue package
- Add compute-budget fields
- Add rationale / confidence / exploit-vs-validate annotations
- Add explicit job manifests and status tracking
- Validate that submission records are sufficient for a real remote-execution contract
- Keep the current packaged default calculation explicit and stable: ORCA geometry optimization with `PBE` / `def2-SVP`, `D3`, and implicit water via `CPCM`

### 4. Reporting
- Replace placeholder report language with decision-grade summaries
- Add per-candidate rationale and evidence provenance summaries
- Distinguish measured vs predicted vs inferred support in the report

### 5. Acceptance tests for pseudo-production behavior
- Fixed benchmark suite of known phenothiazines / D3TaLES records
- Regression tests for retrieval specificity
- Regression tests for evidence-tier behavior
- Regression tests for candidate ranking stability under small retrieval changes
- Run-level pass/fail gates for operator trust

## Revised recommended work order

1. Ranking + scoring hardening
2. Evidence typing / anti-double-counting hardening
3. Simulation handoff and submission packaging
4. Validation-contract checks and report cleanup
5. Acceptance gates and pilot run criteria
6. Small pseudo-production pilot runs

## Current pilot fixture coverage

A fixed small pilot fixture now exists in test form to exercise the pseudo-production path end to end. The fixture currently checks:
- D3TaLES-backed ingestion and stable ranking order on a fixed mini-batch
- identity-aware KG structure (`MolecularRepresentation`, `ABOUT_REPRESENTATION`)
- dataset-record provenance presence
- operator-facing report generation
- simulation queue + manifest packaging with explicit pilot defaults
- submission-record emission for remote execution scaffolding

This is not yet a true benchmark gate, but it is now a stable pilot-run scaffold that can be tightened into one.

## Minimal definition of “pseudo-production-ready enough”

A run should not be considered pseudo-production-ready unless it:
- passes calibrated benchmark checks
- persists D3TaLES measurements/provenance as stable KG entities
- preserves identity-aware cross-run evidence structure without collapsing run-local provenance
- produces a shortlist with auditable evidence and confidence
- emits a simulation-ready queue package rather than only a sorted list
- emits submission records that satisfy the current remote-execution contract
- passes ranking stability and retrieval-specificity regression tests
