# LITERATURE_NOTES.md

## Knowledge-graph / multi-agent directions relevant to this project

This is a lightweight literature memo to guide the design of a KG-backed phenothiazine screening workflow.

## Most relevant themes

### 1. Knowledge-graph-driven scientific agents
- Example surfaced in search: **SciToolAgent** (Nature / Semantic Scholar listing)
- Key idea: a scientific agent can use a knowledge graph to guide what tools or procedures to call, rather than relying on unstructured memory alone.
- Relevance here: the KG can guide which surrogate, validation, or literature evidence is most relevant for a candidate.

### 2. Multi-agent scientific discovery with ontological knowledge graphs
- Example surfaced in search: **SciAgents** (arXiv / Wiley listing)
- Key idea: multi-agent systems can reason over ontological or literature-derived knowledge graphs to generate hypotheses and connect concepts.
- Relevance here: instead of only ranking molecules numerically, the system can connect molecules to motifs, literature evidence, and validation history.

### 3. Knowledge graphs in chemistry / drug discovery
- Search results surfaced multiple reviews and surveys on KGs in drug discovery and scientific discovery.
- Core repeated point: KGs are especially useful for integrating heterogeneous evidence, maintaining provenance, and enabling explainable retrieval.
- Relevance here: phenothiazine screening naturally combines structure, predicted properties, validated properties, literature, and model provenance.

### 4. Automatic chemical knowledge graph construction from literature
- Search result surfaced: **CEAR: Automatic construction of a knowledge graph of chemical entities and roles from scientific literature**.
- Key idea: LLM + ontology pipelines can extract chemistry entities/roles from papers into structured graph form.
- Relevance here: later versions of the project could ingest phenothiazine literature and add paper-derived claims directly into the campaign KG.

---

## Recommended conclusion for pz_agent

A knowledge graph is worth adding, but **as structured scientific memory**, not as a replacement for the main computational pipeline.

### Best use in this project
- store campaign memory across runs
- connect molecules to scaffolds, substituents, positions, predictions, DFT outcomes, and literature claims
- provide retrieval and explanation context for ranking and reports

### Not the best use
- replacing numerical surrogate models
- replacing Pareto ranking
- replacing raw artifacts like CSV outputs

### Recommended implementation path

#### v1
- local JSON/NetworkX graph
- explicit provenance fields
- graph builder fed by pipeline artifacts
- retrieval helpers for molecule- and motif-centric summaries

#### v2
- Neo4j / Memgraph backend
- literature extraction agent
- cross-run motif mining
- evidence-aware recommendation queries

---

## Proposed KG schema sketch

### Entity types
- Molecule
- Scaffold
- Substituent
- Site
- Property
- Prediction
- Validation
- DFTJob
- SurrogateModel
- LiteraturePaper
- LiteratureClaim
- CandidateSet
- Run

### Relation types
- HAS_SCAFFOLD
- SUBSTITUTED_AT
- HAS_SUBSTITUENT
- HAS_DESCRIPTOR
- PREDICTED_PROPERTY
- VALIDATED_PROPERTY
- GENERATED_IN_RUN
- SELECTED_FOR_DFT
- SUPPORTED_BY
- CONTRADICTED_BY
- SIMILAR_TO
- APPEARS_IN_PAPER
- EXTRACTED_FROM
- OUTPERFORMS
- DOMINATES

### Provenance fields
- source_type
- source_id
- timestamp
- model_version
- code_version
- confidence
- units
- note

---

## Practical research takeaway

For this phenothiazine project, the right architecture is:
- **pipeline for computation**
- **knowledge graph for memory, provenance, and explanation**

That is more defensible scientifically than trying to make a graph database do the optimization itself.
