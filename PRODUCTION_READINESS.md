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
8. Write report and prepare DFT handoff shortlist

## What is already good enough

- Pipeline orchestration is coherent and testable
- D3TaLES ingestion works for demo-scale runs
- Structure-first retrieval path is now wired into the demo config
- KG-backed critique and reranking are operational
- Adaptive graph-expansion loop is functioning as a supervised scaffold

## Main bottlenecks before production runs

### 1. Production-grade scoring
- Replace placeholder/stub scoring with credible synthesizeability and solubility models
- Add uncertainty/confidence outputs
- Add benchmark thresholds that can fail a run

### 2. D3TaLES-native KG backbone
- Promote D3TaLES records to first-class source-record nodes
- Use stable cross-run IDs for records and measurements
- Preserve dataset provenance independently of run-local candidates
- Make measurement provenance queryable without depending on a single run snapshot

### 3. Evidence reliability
- Improve exact-vs-analog identity resolution
- Tighten literature/patent relevance filtering
- Weight evidence by source quality and match type more robustly
- Make contradiction signals influence downstream ranking more explicitly

### 4. DFT handoff
- Promote shortlist sorting to a true DFT queue package
- Add compute-budget fields
- Add rationale / confidence / exploit-vs-validate annotations
- Add explicit job manifests and status tracking

### 5. Reporting
- Replace placeholder report language with decision-grade summaries
- Add per-candidate rationale and evidence provenance summaries
- Distinguish measured vs predicted vs inferred support in the report

### 6. Acceptance tests for production behavior
- Fixed benchmark suite of known phenothiazines / D3TaLES records
- Regression tests for retrieval specificity
- Regression tests for evidence-tier behavior
- Regression tests for candidate ranking stability under small retrieval changes

## Recommended work order

1. D3TaLES-native KG backbone
2. Scoring + benchmark hardening
3. Evidence typing / identity-resolution hardening
4. DFT handoff packaging
5. Reporting cleanup
6. Production pilot runs

## Minimal definition of “production-ready enough”

A run should not be considered production-ready unless it:
- passes calibrated benchmark checks
- persists D3TaLES measurements/provenance as stable KG entities
- produces a shortlist with auditable evidence and confidence
- emits a DFT-ready queue package rather than only a sorted list
