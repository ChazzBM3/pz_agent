# PLAN.md

## Goal

Build a phenothiazine screening system that follows the spirit of a multi-agent scientific workflow, but **without LangGraph**. Instead of a graph orchestration library, use plain Python modules with a shared state object, explicit stage runners, and durable artifacts on disk.

The system should support:
- directed phenothiazine library generation
- surrogate-property prediction and benchmarking
- multi-objective ranking / Pareto analysis
- simulation handoff and remote submission for top candidates
- validation feedback from completed simulations
- auditability of every decision and intermediate result
- an agent-built scientific knowledge graph that can serve as structured long-term memory

---

## UROP-specific project framing

From `urop.pdf`, the intended project appears to be:

1. **Problem statement / motivation**
   - Screen phenothiazine molecules for promising candidates.
   - Use computational triage to reduce expensive high-level calculations.

2. **Research questions**
   - A primary question around whether computational screening can identify promising phenothiazine derivatives.
   - A methodological question around whether lower-cost surrogate models plus ranking can efficiently prioritize candidates.

3. **Scope boundaries**
   - Stay focused on phenothiazine scaffold exploration rather than broad unconstrained molecular discovery.
   - Keep the project to library generation, surrogate screening, Pareto analysis, and selective DFT validation.

4. **Methodology**
   - **Initial molecular generation via a generative AI pass using GenMol to create phenothiazine derivatives**
   - **Structure standardization and QC**
   - **Primary screening focused on synthesizability and solubility**
   - **Surrogate model benchmarking and scoring**
   - **Pareto front construction and analysis**
   - **DFT validation of top candidates**
   - **Validation checkpoint with known phenothiazines**

5. **Deliverables / outcomes**
   - Ranked candidate set
   - Reproducible workflow
   - Comparison of surrogate models
   - Validation results on top compounds

That suggests the repo should be built around a staged scientific pipeline, not a chatbot-style agent demo.

---

## High-level design

Use a **coordinator + specialist agents** pattern.

### Why not LangGraph

LangGraph is useful for explicit DAG/stateful conversations, but this project does not need a framework dependency to express the workflow. The tasks are already naturally staged and artifact-driven.

A simpler architecture is better:
- easier to debug
- easier to reproduce in a research setting
- easier to audit for scientific decisions
- less framework overhead

### Replacement orchestration pattern

Use:
- a central `RunState` object
- stage-specific Python classes/functions
- JSON/YAML artifacts written after each stage
- a deterministic runner that calls stages in order
- optional retry / resume from saved artifacts

In other words: **state machine + filesystem**, not agent graph runtime.

### Knowledge graph as long-term memory replacement

A strong extension for this project is to replace or augment ordinary long-term memory with a **scientific knowledge graph (KG)**. Instead of storing free-form notes, the system stores:
- entities: molecules, scaffolds, substituents, properties, methods, papers, datasets, DFT jobs, surrogate models
- relations: `has_substituent`, `predicted_property`, `validated_by`, `derived_from`, `appears_in_paper`, `fails_filter`, `dominates`, `belongs_to_cluster`, `measured_as`, `computed_with`
- provenance: source paper, model version, code version, timestamp, confidence, units

This is useful here because the project is cumulative and evidence-driven. A KG can remember:
- which phenothiazine variants have already been generated
- which motifs tend to help or hurt target properties
- which surrogate predictions were later confirmed or contradicted by DFT
- what literature evidence exists for a scaffold, substituent, or property trend
- how candidates connect to known phenothiazines and prior experiments

For this project, the KG should **not fully replace tabular artifacts**. Instead it should sit above them as a structured memory and reasoning layer.

---

## Proposed multi-agent system

## 1. Orchestrator Agent

### Responsibility
- Own the run lifecycle
- Decide which stage runs next
- Validate inputs/outputs between agents
- Persist state and metadata
- Stop the pipeline if quality gates fail

### Inputs
- project config
- scaffold definition
- substituent rules
- surrogate model specs
- DFT budget

### Outputs
- run manifest
- stage status
- final ranked report

### Key rule
The orchestrator should never do chemistry logic itself if a specialist can do it. It only routes, validates, and records.

---

## 2. Library Designer Agent

### Responsibility
Generate phenothiazine derivatives from an initial **GenMol-driven generative pass** constrained to the phenothiazine family.

### Tasks
- specify the phenothiazine scaffold and generation constraints for GenMol
- run a generative pass to propose phenothiazine derivatives
- optionally post-filter by allowed sites / motif constraints
- enforce synthetic / structural sanity filters
- deduplicate molecules by canonical SMILES / InChIKey

### Inputs
- parent phenothiazine scaffold
- allowed positions
- substituent catalog
- medicinal / electrochemical constraints

### Outputs
- candidate library CSV/JSON
- metadata on which positions were modified
- rejection log for invalid structures

### Notes
This should be **constrained generative chemistry**: use GenMol to propose derivatives, but keep generation tightly bounded to the phenothiazine scaffold family.

---

## 3. Structure Standardization Agent

### Responsibility
Prepare chemically consistent representations before scoring.

### Tasks
- sanitize molecules
- assign canonical SMILES
- generate 2D/3D structures if needed
- compute basic descriptors
- flag malformed, charged, unstable, or duplicate entries

### Outputs
- clean library table
- descriptor table
- QC report

---

## 4. Surrogate Screening Agent

### Responsibility
Run low-cost models to estimate relevant properties.

### Possible properties
Based on the current UROP framing, the **primary screening properties** should be:
- synthesizability / synthetic accessibility
- solubility

Secondary properties can include:
- stability proxies
- HOMO / LUMO or redox-relevant descriptors
- molecular size / planarity / steric descriptors
- novelty / diversity indicators

### Tasks
- call one or more surrogate models
- standardize outputs to common units/scales
- attach confidence / uncertainty if available
- record model provenance

### Outputs
- property prediction matrix
- model-by-model predictions
- uncertainty table

---

## 5. Benchmark / Calibration Agent

### Responsibility
Compare surrogate behavior on known phenothiazines before trusting the screen.

### Why this matters
This is explicitly aligned with the UROP checkpoint about **known phenothiazine calibration**.

### Tasks
- assemble a calibration set of known compounds
- compare predicted values against literature or trusted references
- score each surrogate on error / rank correlation
- choose a production model or weighted ensemble

### Outputs
- benchmark summary
- selected model(s)
- calibration report

### Quality gate
If no surrogate meets a minimum calibration threshold, the run should stop or fall back to a more conservative screen.

---

## 6. Multi-Objective Ranking Agent

### Responsibility
Convert raw properties into a screening decision, with **synthesizability and solubility as the primary objectives**.

### Tasks
- normalize objectives
- apply hard constraints first
- prioritize synthesizability and solubility in ranking
- compute weighted scores if needed
- compute Pareto front / non-dominated sorting
- cluster candidates to avoid trivial analog redundancy

### Outputs
- Pareto-optimal set
- ranked shortlist
- diversity-aware top-N list

### Important detail
Do not use only a single weighted score. Keep Pareto ranking explicit so tradeoffs remain visible.

---

## 7. Explanation / Report Agent

### Responsibility
Generate human-readable reasoning for why a molecule survived or was rejected.

### Tasks
- summarize top candidates
- explain dominant tradeoffs
- point to uncertainty / weak evidence
- prepare tables and plots for the PI/student

### Outputs
- markdown report
- CSV summary tables
- optional slide-ready figures

---

## 8. Simulation Handoff Agent

### Responsibility
Prepare the final shortlist for expensive validation and package it for remote execution.

### Tasks
- select top candidates within compute budget
- generate simulation input bundles and per-candidate job specs
- attach rationale, queue rank, and priority context
- emit queue and manifest artifacts that are suitable for remote execution contracts
- track which candidates have been packaged for submission

### Outputs
- simulation-ready input directory
- queue manifest
- validation queue

---

## 9. Simulation Submission Agent

### Responsibility
Convert packaged simulation jobs into concrete submission records for a target execution backend.

### Tasks
- resolve backend and remote target information
- submit or stage packaged jobs for remote execution
- persist submission metadata and identifiers
- keep orchestration-side status tracking separate from remote execution internals

### Outputs
- submission manifest
- submission records
- remote-target metadata

---

## 10. Knowledge Graph Agent

### Responsibility
Build and maintain a scientific knowledge graph that acts as structured long-term memory for the screening campaign.

### Tasks
- ingest entities from library generation, literature, surrogate predictions, and DFT outputs
- normalize identifiers for molecules, papers, methods, and properties
- store provenance and confidence on every edge
- support retrieval of prior evidence for a candidate or motif
- summarize graph neighborhoods for downstream ranking/report agents

### Example entity types
- Molecule
- Scaffold
- Substituent
- Position / substitution site
- Property
- Prediction
- DFTCalculation
- SurrogateModel
- LiteraturePaper
- Dataset
- CandidateSet

### Example relations
- `HAS_SCAFFOLD`
- `SUBSTITUTED_AT`
- `HAS_SUBSTITUENT`
- `PREDICTED_PROPERTY`
- `VALIDATED_PROPERTY`
- `SIMILAR_TO`
- `MENTIONED_IN`
- `SUPPORTED_BY`
- `CONTRADICTED_BY`
- `RANKED_IN`
- `SELECTED_FOR_SIMULATION`
- `GENERATED_FROM_RULE`

### Outputs
- graph database or graph JSON
- provenance-aware evidence bundles
- retrieval summaries for molecules, motifs, and hypotheses

### Design principle
The KG should function as **structured scientific memory**, not just a document index. It must retain provenance, confidence, and links back to raw artifacts.

A particularly useful pattern here is to let the **critique agent** update the KG each iteration by searching the web/literature for top candidates or close analogs, then attaching support/contradiction signals and provenance to candidate nodes.

---

## 11. Validation Agent

### Responsibility
Compare completed simulation results back to surrogate predictions and close the loop.

### Tasks
- ingest remote simulation outputs
- compare predicted vs validated properties
- identify systematic surrogate bias
- recommend next-round refinement
- write validated outcomes back into KG structures and reports

### Outputs
- validation report
- model error analysis
- suggestions for the next iteration

---

## Workflow

```text
Config / project brief
  -> GenMol-constrained Library Designer
  -> Structure Standardization
  -> Surrogate Screening (synthesizability + solubility first)
  -> Benchmark / Calibration
  -> Knowledge Graph Agent
  -> Multi-Objective Ranking
  -> Critique Agent (web/literature search on top candidates)
  -> Knowledge Graph Update
  -> Explanation / Report
  -> Simulation Handoff
  -> Simulation Submission
  -> Validation / Feedback
  -> Knowledge Graph Update
```

This can be implemented as a simple staged runner:

```python
for stage in pipeline:
    state = stage.run(state)
    save_artifacts(state)
    enforce_quality_gates(state)
```

---

## Shared state design

Use a typed state object, for example:

```python
@dataclass
class RunState:
    config: dict
    library_raw: pd.DataFrame | None = None
    library_clean: pd.DataFrame | None = None
    descriptors: pd.DataFrame | None = None
    predictions: pd.DataFrame | None = None
    benchmark: dict | None = None
    knowledge_graph_path: str | None = None
    ranked: pd.DataFrame | None = None
    shortlist: pd.DataFrame | None = None
    simulation_queue: pd.DataFrame | None = None
    validation: pd.DataFrame | None = None
    logs: list[str] = field(default_factory=list)
```

Also persist artifacts to disk after every stage:
- `artifacts/library_raw.csv`
- `artifacts/library_clean.csv`
- `artifacts/predictions.csv`
- `artifacts/benchmark.json`
- `artifacts/ranked.csv`
- `artifacts/shortlist.csv`
- `artifacts/validation.csv`

This gives resumability without a graph framework.

For the KG layer, store either:
- a property graph in Neo4j / Memgraph, or
- an RDF graph for standards-heavy interoperability, or
- a local NetworkX/JSON graph for the first prototype

My recommendation for this project is:
- **prototype:** local JSON/NetworkX graph with explicit provenance objects
- **later scale-up:** Neo4j if you want queryable campaign memory across many runs

---

## Recommended repo structure

```text
pz_agent/
  README.md
  PLAN.md
  pyproject.toml
  src/pz_agent/
    __init__.py
    config.py
    state.py
    runner.py
    io.py
    chemistry/
      scaffold.py
      standardize.py
      descriptors.py
    agents/
      orchestrator.py
      library_designer.py
      standardizer.py
      surrogate_screen.py
      benchmark.py
      knowledge_graph.py
      ranker.py
      reporter.py
      simulation_handoff.py
      validator.py
    models/
      base.py
      surrogate_registry.py
    analysis/
      pareto.py
      diversity.py
      metrics.py
    kg/
      schema.py
      builder.py
      retrieval.py
      provenance.py
    reports/
      templates.py
  configs/
    default.yaml
    phenothiazine_core.yaml
  data/
    known_phenothiazines.csv
    substituents.csv
  artifacts/
  notebooks/
  tests/
```

---

## Minimal implementation roadmap

## Phase 1 — research-grade skeleton
- initialize package structure
- define `RunState`
- implement file-based artifact persistence
- create a deterministic `runner.py`
- add config loading

## Phase 2 — chemistry input layer
- encode phenothiazine scaffold and GenMol generation constraints
- build GenMol prompt / generation adapter
- sanitize and deduplicate generated structures

## Phase 3 — surrogate scoring
- wire in descriptor calculation
- implement one baseline surrogate focused on synthesizability and solubility
- add benchmark/calibration set handling

## Phase 4 — knowledge graph layer
- define entity / relation schema
- ingest molecules, predictions, literature, and DFT metadata into the KG
- build provenance-aware retrieval for molecules and motifs

## Phase 5 — ranking and reports
- hard filters
- Pareto front generation
- KG-assisted evidence retrieval
- ranking report and plots

## Phase 6 — simulation and validation loop
- generate simulation input bundles for top candidates
- emit submission-ready queue and manifest artifacts
- add validation ingestion and feedback report
- write validated outcomes back into the KG

---

## Quality gates

The orchestrator should enforce these:

1. **Chemical validity gate**
   - invalid structures removed
   - duplicates removed

2. **Calibration gate**
   - surrogate must meet minimum benchmark quality on known phenothiazines

3. **Diversity gate**
   - shortlist cannot be dominated by near-identical analogs

4. **Uncertainty gate**
   - candidates with high uncertainty should be flagged, not silently promoted

5. **Budget gate**
   - simulation shortlist capped by compute budget

6. **Validation-contract gate**
   - packaged jobs must contain the fields required for remote execution and later result ingestion

---

## Why this multi-agent framing is useful

Even without LangGraph, the agent split is still valuable because each stage has a different job:
- generate chemistry
- standardize inputs
- score synthesizability / solubility and other properties
- benchmark models
- critique top candidates with external evidence
- rank candidates
- prepare simulation handoff and validation

That separation helps with:
- clean interfaces
- easier testing
- swapping models in/out
- scientific reproducibility
- future extension to more autonomous loops
- a natural place to attach a structured scientific memory layer via the KG

---

## Suggested first milestone

A strong first milestone would be:

1. define the phenothiazine scaffold and GenMol generation constraints
2. generate a small initial phenothiazine library with GenMol
3. compute descriptors
4. run one surrogate model focused on synthesizability and solubility
5. critique the top shortlist with web/literature search
6. write the evidence into the KG
7. validate workflow behavior on a few known phenothiazines

If that works, the project is already scientifically useful even before full automation.

---

## Concrete answer to the user's request

A **similar multi-agent approach without LangGraph** should be implemented as a **modular staged pipeline** with specialist agents and a plain Python orchestrator. The UROP plan strongly suggests the workflow should center on:
- GenMol-based phenothiazine derivative generation
- primary scoring on synthesizability and solubility
- surrogate model benchmarking and scoring
- critique-agent evidence gathering for top candidates
- Pareto front analysis
- simulation-backed validation of top candidates
- calibration against known phenothiazines

So the best architecture is not a conversation graph; it is a **research workflow engine with explicit artifacts and quality gates**, optionally augmented by a **provenance-aware scientific knowledge graph** that serves as structured long-term memory.

---

## Literature-informed recommendation for the knowledge graph

A literature search suggests a useful pattern:
- **knowledge-graph-driven scientific agents** use a KG to guide tool or method selection rather than storing everything as plain text memory
- **multi-agent scientific discovery systems** use ontological or literature-derived KGs to connect concepts, evidence, and hypotheses
- **chemistry / drug-discovery KG papers** emphasize that graphs are valuable for integrating entities, relations, provenance, and downstream explainability

For this project, the most practical interpretation is:

1. **Use the KG as campaign memory**
   - not just chat memory
   - store molecules, properties, predictions, validations, literature claims, and decision provenance

2. **Keep raw tables as source-of-truth artifacts**
   - CSV/JSON remain the immutable outputs of each pipeline stage
   - the KG indexes and links them for retrieval and reasoning

3. **Build the KG incrementally with agents**
   - literature extraction sub-agent adds paper-derived claims
   - library agent adds generated molecules and scaffold relations
   - surrogate agent adds prediction nodes/edges plus model provenance
   - validation agent adds DFT-backed corrections

4. **Use KG retrieval in ranking**
   - when ranking a molecule, retrieve its graph neighborhood:
     - related known phenothiazines
     - similar substituents
     - prior validation evidence
     - contradictory evidence
     - relevant literature claims

5. **Do not replace numeric screening with the KG**
   - the KG should improve memory, provenance, and explainability
   - the actual optimization still comes from descriptors, surrogate predictions, Pareto ranking, and simulation-backed validation

### Practical implementation choice

Best option for v1:
- represent each run’s memory as a local graph JSON plus helper query code
- optionally expose Cypher-like queries later if moved into Neo4j

Best option for v2:
- move to Neo4j or Memgraph
- add literature extraction pipelines
- support cross-run memory and motif-level trend mining

### Example KG queries this project should answer
- Which substituents at position X most often survive the surrogate filters?
- Which top-ranked molecules were later contradicted by DFT?
- What known phenothiazines are most similar to candidate Y?
- What literature supports the claim that motif Z improves the target property?
- Which surrogate model has historically performed best for this property family?
