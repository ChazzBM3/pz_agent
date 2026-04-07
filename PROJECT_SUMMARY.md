# PROJECT_SUMMARY.md

## 1. Project scope, approach, novelty, and possible issues

## Scope

This project aims to build a **phenothiazine screening workflow** centered on:
- externally generated phenothiazine derivatives from **GenMol**
- primary scoring on **synthesizability** and **solubility**
- literature-aware critique and reranking
- a **knowledge graph** that serves as structured scientific memory
- later DFT handoff for a smaller shortlisted set

The scope is intentionally **not** broad de novo molecular discovery. The assumption is that GenMol already preserves the phenothiazine core and explores functional decorations around it.

## Approach

The implementation uses a **modular multi-agent pipeline without LangGraph**.

Core stages currently include:
- library import / design
- structure normalization
- surrogate scoring
- ranking
- critique generation
- literature-aware reranking
- knowledge graph updates
- report generation
- DFT handoff scaffolding

The orchestration model is:
- plain Python modules
- shared `RunState`
- file-backed artifacts
- explicit stage ordering

This makes the system easier to debug and reproduce than a heavier orchestration framework.

## Novelty

The most distinctive part of the project is not any single model, but the **combination** of ideas:

1. **Phenothiazine-focused generative screening**
   - the chemistry problem is tightly scoped around a known core and its decorations

2. **Knowledge graph as scientific memory**
   - molecules, predictions, literature claims, evidence hits, media artifacts, and provenance are all represented structurally

3. **Evidence-aware reranking**
   - the system does not rely only on numeric scoring; it can also incorporate literature-derived support/analog evidence

4. **Separation of generation from screening**
   - GenMol is assumed to run externally, while `pz_agent` focuses on import, scoring, critique, ranking, and memory

5. **Decoration-centric chemistry reasoning**
   - because the phenothiazine core is fixed, the project is evolving toward reasoning about functionalization patterns rather than core detection

## Potential areas of issue

### 1. Placeholder / heuristic components still dominate
At the moment, several pieces are still scaffolds rather than production-grade science:
- scoring heuristics are weak placeholders
- literature matching is still text-driven and approximate
- critique evidence integration is stronger structurally than chemically

### 2. Chemistry matching is not yet rigorous
Even with RDKit installed, the current matching logic is still not enough for robust literature identity resolution:
- exact matching is crude
- analog matching is scaffold/token-based
- substituent-level reasoning is still heuristic

### 3. Literature quality control remains hard
Web search can surface useful analog papers, but also noisy or only indirectly relevant results. The system still needs:
- better confidence weighting
- contradiction detection
- stronger paper/entity normalization

### 4. The KG is strong structurally but still semantically immature
The graph now has good shape, but some important semantics are still missing:
- canonical paper merging beyond URL/title fingerprinting
- chemistry-native analog relations
- deeper generation/scoring provenance propagation
- stronger use of enriched KG content in ranking decisions

### 5. Scoring realism is still limited
The current synthesizeability and solubility scores are placeholder heuristics. This is acceptable for scaffolding, but not enough for scientific conclusions.

---

## 2. Current repo status

## Overall maturity

The repo is now a **serious research scaffold**, not just notes.
It has a coherent architecture, real artifact flow, GitHub hosting, and several working subsystems.

GitHub:
- <https://github.com/ChazzBM3/pz_agent>

## What is implemented

### Orchestration and pipeline
- deterministic stage runner
- `RunState`
- config-driven stage order
- file-backed artifacts
- CLI entrypoints for run/enrichment/rebuild workflows

### Generation handling
- external GenMol import path
- JSON / CSV import support
- candidate validation with Pydantic
- generation provenance registry
- `GenerationBatch` nodes in the KG

### Chemistry layer
- RDKit installed in repo venv
- molecule identity schema
- canonical SMILES generation
- InChI / InChIKey attempts
- Murcko scaffold extraction
- decoration-aware identity fields
- simple structure matching scaffold (`exact`, `analog`, `family`, `unknown`)

### Scoring
- synthesizeability scorer scaffold
- solubility scorer scaffold
- heuristic baseline values
- external score import mode
- prediction provenance attached to outputs

### Ranking
- weighted baseline ranking using synthesizeability + solubility
- second-pass literature-aware reranking in pipeline
- enriched-critique reranking path available separately

### Knowledge graph
- local JSON property-graph approach
- molecules, predictions, generation batches, claims, papers, evidence hits, and media artifacts represented in the graph
- enriched KG rebuild from literature enrichment artifacts
- paper deduplication by URL/title fingerprint
- generated plot artifacts attached as media nodes

### Literature / critique layer
- critique query generation
- live enrichment artifact path
- normalized literature/evidence nodes in enriched graph
- enriched reranking path

## What is still scaffold-level / incomplete

### Chemistry
- substituent extraction is still heuristic
- attachment-aware decoration reasoning is not yet implemented
- chemistry matching is not yet robust enough for real exact-vs-analog literature alignment

### Scoring
- current numeric scoring is still heuristic
- no calibrated production synthesizeability model yet
- no calibrated production solubility model yet

### Ranking
- weighting is simplistic
- true Pareto / uncertainty-aware ranking is not fully implemented yet
- literature-aware reranking exists, but benefits are limited until evidence signals become richer

### Knowledge graph
- graph semantics are improving, but not fully mature
- evidence typing and contradiction handling are still shallow
- enriched KG is useful, but not yet the sole source of reranking decisions

## Bottom line

The repo is in a strong **architecture-first prototype** state:
- the pipeline shape is real
- the KG/memory approach is real
- RDKit-backed chemistry normalization is now present
- the system is ready to absorb real GenMol outputs and better scoring models

The biggest remaining gap is not architecture anymore.
It is the transition from scaffolding to **scientifically credible chemistry/scoring/matching**.
