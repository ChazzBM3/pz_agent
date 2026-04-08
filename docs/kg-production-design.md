# Production Knowledge Graph Design for `pz_agent`

## Goal

Build a production-quality scientific knowledge graph (KG) for `pz_agent` that acts as:
- a durable scientific memory layer
- a provenance-aware evidence store
- a retrieval substrate for critique, ranking, reporting, and validation loops
- a bridge between generated candidate molecules, literature evidence, surrogate predictions, and later DFT validation

The KG should not be a graph-shaped dump of pipeline artifacts. It should store normalized scientific entities, claims, evidence, provenance, and decision context in a way that supports retrieval and reasoning across runs.

---

## Design principles

1. **Chemistry first**
   - Molecule identity, scaffold identity, substituent identity, and attachment-site information must be explicit and queryable.

2. **Claims over papers**
   - Papers are evidence sources, not the main semantic unit.
   - The main unit of scientific memory should be a normalized `Claim` supported or contradicted by evidence.

3. **Provenance everywhere**
   - Every important prediction, claim, evidence hit, and decision should carry source, method, timestamp, confidence, and version metadata.

4. **Evidence polarity matters**
   - The graph must support support, contradiction, ambiguity, and mixed evidence.

5. **Retrieval-driven schema**
   - The schema should be designed backward from the questions the critique and ranking agents need to answer.

6. **Graph-guided iteration**
   - Borrow from agentic graph-reasoning work by letting the current graph state shape the next critique/search/reasoning step.
   - Do not allow uncontrolled graph growth; new nodes and edges must remain chemistry-grounded and provenance-backed.

7. **Backend-agnostic semantics, Neo4j-friendly implementation**
   - Keep the semantic model backend-agnostic, but target a property-graph layout that can be stored in Neo4j.

---

## What the current KG gets right

The current repo already contains a useful scaffold:
- `Molecule`, `Prediction`, `LiteraturePaper`, `LiteratureClaim`, `EvidenceHit`, `MediaArtifact`, `GenerationBatch`, and `Run` nodes exist conceptually.
- There is a basic enriched graph flow.
- Some analog/exact notions and evidence confidence are emerging.

This is a solid starting point, but the current graph is still too search-centric and report-shaped.

Main current limitations:
- `LiteratureClaim` nodes are overloaded and often act like search bundles.
- `LiteraturePaper` sometimes means a real paper and sometimes just a query placeholder.
- Molecule identity is too weak for robust analog reasoning.
- Provenance is embedded inconsistently inside attrs instead of normalized.
- Claims, evidence, and decisions are not yet modeled as separate first-class objects.

---

## Proposed production KG architecture

The KG should be organized into six layers:

1. **Chemistry identity layer**
2. **Property and prediction layer**
3. **Evidence and claim layer**
4. **Workflow and provenance layer**
5. **Decision layer**
6. **Retrieval / RAG layer**

---

## 1. Chemistry identity layer

This layer supports exact matching, analog matching, motif retrieval, and decoration-aware critique.

### Node types

#### `Molecule`
Canonical chemical identity for a candidate or known compound.

Suggested attributes:
- `molecule_id`
- `canonical_smiles`
- `inchi`
- `inchikey`
- `molecular_formula`
- `formal_charge`
- `stereo_status`
- `tautomer_policy`
- `source_role` (`generated_candidate`, `literature_molecule`, `benchmark_molecule`, etc.)

#### `Scaffold`
Core scaffold identity.

Suggested attributes:
- `scaffold_id`
- `scaffold_smiles`
- `scaffold_family`
- `name`

#### `Substituent`
Normalized substituent or functional group.

Suggested attributes:
- `substituent_id`
- `substituent_smiles`
- `name`
- `class`
- `electronic_class`
- `steric_class`
- `hbond_role`

#### `AttachmentSite`
Position/site on the scaffold.

Suggested attributes:
- `site_id`
- `site_label`
- `site_index`
- `local_environment`

#### `DecorationPattern`
Multi-substituent pattern attached to a scaffold.

Suggested attributes:
- `pattern_id`
- `summary`
- `site_map`
- `electronic_signature`
- `steric_signature`

#### `MolecularRepresentation`
Featurized representations used for modeling.

Suggested attributes:
- `representation_id`
- `kind` (`ecfp`, `descriptor_vector`, `graph_embedding`, etc.)
- `version`
- `shape`
- `storage_ref`

### Edge types

- `HAS_SCAFFOLD` (`Molecule -> Scaffold`)
- `HAS_SUBSTITUENT` (`Molecule -> Substituent`)
- `ATTACHED_AT` (`Substituent -> AttachmentSite`)
- `HAS_DECORATION_PATTERN` (`Molecule -> DecorationPattern`)
- `HAS_REPRESENTATION` (`Molecule -> MolecularRepresentation`)
- `EXACT_MATCH_OF` (`Molecule -> Molecule` or `EvidenceHit -> Molecule`)
- `ANALOG_OF` (`Molecule -> Molecule`, `EvidenceHit -> Molecule`, or `Claim -> DecorationPattern`)
- `SIMILAR_TO` (`Molecule -> Molecule` with match metadata)

### Why this layer matters

Without explicit scaffold/substituent/site structure, the critique agent can only do vague candidate-level literature search. With this layer, critique can ask focused questions like:
- what evidence exists for electron-donating substituents at R2?
- what analogs share this decoration pattern?
- what synthesis evidence exists for this substituent class?

---

## 2. Property and prediction layer

This layer captures predicted, reported, and validated properties in a normalized way.

### Node types

#### `Property`
Canonical property concept.

Examples:
- solubility
- synthesizability
- instability risk
- redox proxy
- novelty

Suggested attributes:
- `property_id`
- `name`
- `unit`
- `objective_role` (`primary`, `secondary`, `diagnostic`)

#### `Condition`
Experimental or contextual condition.

Examples:
- solvent
- pH
- temperature
- ionic strength

Suggested attributes:
- `condition_id`
- `kind`
- `value`
- `unit`

#### `Prediction`
A model-generated property estimate.

Suggested attributes:
- `prediction_id`
- `value`
- `uncertainty`
- `confidence`
- `mode` (`predicted`, `imported`, `calibrated`)

#### `Measurement`
A measured or literature-reported property value.

Suggested attributes:
- `measurement_id`
- `value`
- `unit`
- `measurement_type` (`literature`, `experimental`, `dft`, etc.)
- `confidence`

#### `Model`
Surrogate or scoring model identity.

Suggested attributes:
- `model_id`
- `name`
- `family`
- `version`
- `input_type`
- `training_data_ref`

### Edge types

- `HAS_PROPERTY` (`Prediction -> Property`, `Measurement -> Property`)
- `PREDICTED_FOR` (`Prediction -> Molecule`)
- `MEASURED_FOR` (`Measurement -> Molecule`)
- `UNDER_CONDITION` (`Prediction/Measurement -> Condition`)
- `PREDICTED_BY` (`Prediction -> Model`)
- `CALIBRATED_AGAINST` (`Model -> Dataset` or `Prediction -> Measurement`)

### Why this layer matters

This is especially important for solvent-aware datasets like `EGP.json`. Solubility should not be stored as one undifferentiated scalar if it is condition-dependent.

---

## 3. Evidence and claim layer

This is the semantic center of the KG.

### Core principle

The main semantic object is `Claim`, not `Paper`.

A paper can support many claims, contradict others, or provide mixed evidence.

### Node types

#### `Paper`
Normalized literature source.

Suggested attributes:
- `paper_id`
- `title`
- `doi`
- `url`
- `year`
- `venue`
- `authors`
- `dedup_fingerprint`

#### `Claim`
Normalized scientific assertion.

Suggested attributes:
- `claim_id`
- `subject_type` (`molecule`, `scaffold`, `substituent`, `pattern`, `property_trend`, `route`, etc.)
- `predicate` (`improves`, `reduces`, `supports_route`, `warns_instability`, `correlates_with`)
- `object_type`
- `polarity` (`support`, `contradiction`, `mixed`, `uncertain`)
- `confidence`
- `curator_status` (`machine_extracted`, `reviewed`, `accepted`, `rejected`)

#### `EvidenceHit`
A raw or normalized evidence item returned by search or extraction.

Suggested attributes:
- `evidence_hit_id`
- `match_type` (`exact`, `analog`, `family`, `unknown`)
- `match_basis`
- `confidence`
- `retrieval_method`

#### `EvidenceSnippet`
Snippet, quote, or extracted local context.

Suggested attributes:
- `snippet_id`
- `text`
- `section`
- `page`
- `char_span`

#### `Figure`
Relevant figure or media evidence.

Suggested attributes:
- `figure_id`
- `caption`
- `figure_type`
- `source_url`
- `storage_ref`

#### `Hypothesis`
Tentative idea generated from graph-guided reasoning.

Suggested attributes:
- `hypothesis_id`
- `text`
- `scope`
- `confidence`
- `status` (`open`, `supported`, `contradicted`, `archived`)

#### `SynergyPattern`
Multi-factor pattern or interaction.

Suggested attributes:
- `synergy_id`
- `summary`
- `interaction_type`
- `confidence`

### Edge types

- `SUPPORTED_BY` (`Claim -> EvidenceHit`, `EvidenceHit -> Paper`)
- `CONTRADICTED_BY` (`Claim -> EvidenceHit`)
- `HAS_SNIPPET` (`EvidenceHit -> EvidenceSnippet`)
- `HAS_FIGURE` (`EvidenceHit -> Figure`)
- `ABOUT_MOLECULE` (`Claim -> Molecule`)
- `ABOUT_SCAFFOLD` (`Claim -> Scaffold`)
- `ABOUT_SUBSTITUENT` (`Claim -> Substituent`)
- `ABOUT_PATTERN` (`Claim -> DecorationPattern`)
- `ABOUT_PROPERTY` (`Claim -> Property`)
- `RELATES_TO_CONDITION` (`Claim -> Condition`)
- `SUGGESTS_HYPOTHESIS` (`Claim -> Hypothesis`)
- `SUPPORTS_HYPOTHESIS` (`Claim -> Hypothesis`)
- `PART_OF_SYNERGY` (`Substituent/Condition/Property -> SynergyPattern`)

### Why this layer matters

This allows critique and ranking to work with statements like:
- “alkoxy substitution at site R2 tends to improve solubility in polar solvents”
- “cationic side-chain analogs show synthesis feasibility under route family X”
- “this motif has conflicting evidence across solvents or pH conditions”

instead of only raw papers or vague search results.

---

## 4. Workflow and provenance layer

This layer makes the graph audit-ready and cross-run useful.

### Node types

#### `Run`
A single pipeline execution.

#### `GenerationBatch`
Imported or generated candidate batch.

#### `Dataset`
External dataset used for training, benchmarking, or import.

Examples:
- `EGP.json`
- benchmark panel of known phenothiazines
- GenMol export batch

#### `ProvenanceRecord`
Optional first-class provenance object for high-value records.

#### `ConfigSnapshot`
Pipeline configuration associated with a run or model invocation.

### Edge types

- `GENERATED_IN_RUN`
- `GENERATED_BY_BATCH`
- `USED_DATASET`
- `USED_CONFIG`
- `DERIVED_FROM`
- `INGESTED_FROM`
- `PROVENANCE_OF`

### Provenance attributes to standardize everywhere

Whether provenance is modeled as attrs or as a node, the following fields should be standardized:
- `source_type`
- `source_id`
- `source_url`
- `method`
- `model_name`
- `model_version`
- `timestamp`
- `confidence`
- `curator_status`

### Why this layer matters

A production KG must be able to answer:
- where did this claim come from?
- which model produced this prediction?
- which dataset calibrated this model?
- which run created this shortlist?
- when was this evidence retrieved and how confident are we in it?

---

## 5. Decision layer

This layer captures what the system actually decided and why.

### Node types

#### `RankingDecision`
A ranking event or score composition.

Suggested attributes:
- `decision_id`
- `ranking_method`
- `objective_weights`
- `timestamp`

#### `ShortlistDecision`
Selection for downstream follow-up.

Suggested attributes:
- `decision_id`
- `shortlist_reason`
- `budget_context`
- `uncertainty_flag`

#### `DFTJob`
DFT handoff entity.

#### `ValidationResult`
Comparison between predicted and validated outcomes.

### Edge types

- `RANKED_IN`
- `SELECTED_FOR_DFT`
- `VALIDATED_BY`
- `INFLUENCED_BY_CLAIM`
- `INFLUENCED_BY_PREDICTION`
- `INFLUENCED_BY_HYPOTHESIS`

### Why this layer matters

This lets you trace not just what the KG knows, but what the workflow *did* with that knowledge.

---

## 6. Retrieval / RAG layer

The KG should support retrieval-augmented reasoning for the critique agent and optionally other agents.

### Core idea

RAG in `pz_agent` should not be plain document similarity search over random text blobs. It should be **graph-aware retrieval** that combines:
- exact graph traversal
- typed neighborhood expansion
- structured filtering by entity/claim/property/condition/provenance
- optional vector retrieval over text snippets or claim summaries

### Retrieval modes

#### Mode A: Structured graph retrieval
Use typed graph traversal to fetch entities and edges relevant to a candidate.

Examples:
- retrieve all claims about this scaffold
- retrieve all analog evidence for this decoration pattern
- retrieve all synthesis-related claims attached to this substituent class
- retrieve all contradictory claims involving solubility under water-like solvents

#### Mode B: Claim/snippet semantic retrieval
Use embeddings over:
- claim text
- evidence snippets
- hypothesis text
- paper summaries

to find semantically related evidence when exact graph matches are sparse.

#### Mode C: Hybrid retrieval
Use graph retrieval to define a relevant subgraph, then use semantic ranking inside that subgraph.

This should be the default for critique.

---

## RAG implementation design

### 6.1 Retrieval objects

Add a retrieval layer under something like:
- `src/pz_agent/kg/retrieval.py`
- `src/pz_agent/kg/rag.py`
- `src/pz_agent/kg/query_planner.py`

Suggested internal objects:

#### `RetrievalQuery`
Fields:
- `candidate_id`
- `molecule_features`
- `scaffold_id`
- `substituent_ids`
- `attachment_sites`
- `properties_of_interest`
- `conditions_of_interest`
- `retrieval_mode`
- `top_k`

#### `RetrievedContext`
Fields:
- `candidate_summary`
- `exact_match_claims`
- `analog_claims`
- `contradictory_claims`
- `property_evidence`
- `synthesis_evidence`
- `open_questions`
- `provenance_summary`
- `support_score`
- `contradiction_score`

#### `GraphNeighborhood`
Fields:
- `nodes`
- `edges`
- `center_node`
- `hop_limit`
- `filters`

---

### 6.2 Critique-agent RAG flow

The critique agent should use the KG as follows:

#### Step 1: Build candidate retrieval query
Input:
- candidate molecule
- scaffold
- decoration pattern
- shortlist context
- target properties (synthesizability, solubility)

#### Step 2: Retrieve graph neighborhood
Fetch:
- exact-match molecule evidence
- analog molecules sharing scaffold or pattern
- claims about relevant substituent classes
- claims about target properties
- contradictory or negative evidence
- prior runs / validation outcomes for related motifs

#### Step 3: Identify information gaps
Examples:
- no solubility evidence for this substituent class
- strong analog evidence but no exact evidence
- conflicting synthesis evidence
- evidence exists only in non-matching solvents or conditions

#### Step 4: Generate targeted critique/search queries
Use the retrieval output to generate focused searches.

Example transformation:
- not: `candidate X phenothiazine literature`
- but: `phenothiazine para-alkoxy substitution aqueous solubility synthesis route`

#### Step 5: Ingest and normalize new evidence
Convert search hits into:
- `Paper`
- `EvidenceHit`
- `EvidenceSnippet`
- `Claim`
- optional `Hypothesis`

#### Step 6: Produce critique summary for reranking
Output structured features such as:
- exact evidence count
- analog evidence count
- contradiction count
- support score for solubility
- support score for synthesizability
- evidence coverage score
- novelty score
- unresolved-risk flags

---

### 6.3 RAG for other agents

#### Ranker / critique reranker
Use KG retrieval to compute:
- support-weighted reranking features
- contradiction penalties
- motif evidence bonuses
- route-feasibility modifiers
- uncertainty penalties

#### Benchmark / calibration agent
Use KG retrieval to fetch:
- known phenothiazines with measured data
- literature measurements under matched conditions
- prior model performance on related compounds

#### Reporter agent
Use KG retrieval to generate:
- evidence-backed candidate rationales
- support/contradiction summaries
- provenance-aware report sections

#### Validation agent
Use KG retrieval to compare:
- predicted vs validated properties
- motifs that systematically overperform or underperform
- claims that should be revised after DFT or experiment

---

## Graph-guided reasoning ideas borrowed from agentic deep graph reasoning

The paper `Agentic Deep Graph Reasoning Yields Self-Organizing Knowledge Networks` suggests several ideas worth adapting.

### Borrow directly

1. **Reasoning conditioned on current graph state**
   - Let the next critique prompt depend on the current KG neighborhood.

2. **Iterative graph expansion**
   - Use critique/search cycles to add evidence incrementally.

3. **Hub and bridge analysis**
   - Track important motif hubs and bridge concepts linking different literature/evidence clusters.

4. **Synergy-level abstraction**
   - Represent multi-factor interactions like motif + solvent + property trends.

### Adapt carefully

1. **Hypothesis generation**
   - Allow machine-generated hypotheses, but mark them clearly as tentative.

2. **Open-ended graph growth**
   - Permit expansion only when chemistry-grounded and provenance-backed.

### Do not copy blindly

1. Unbounded concept proliferation
2. Weakly grounded abstraction nodes
3. Search-driven growth without evidence thresholds

---

## Candidate retrieval questions the KG must answer

The schema is only useful if it can answer questions like:

### Critique questions
- What exact or analog evidence exists for this molecule?
- What claims exist for this decoration pattern?
- What evidence supports improved solubility under relevant solvents?
- What contradictory evidence exists?
- What synthesis-related claims exist for this substituent class?

### Ranking questions
- Which candidates have the strongest evidence-backed support?
- Which candidates rely mostly on weak analog evidence?
- Which motifs recur among top-ranked supported candidates?
- Which candidates sit in evidence deserts and should be penalized for uncertainty?

### Validation questions
- Which claims were supported or contradicted by DFT?
- Which surrogate predictions fail systematically for a motif family?
- Which hub motifs retain support after validation?

### Scientific memory questions
- What substituent classes repeatedly help or hurt solubility?
- What solvent-conditioned trends appear across papers and runs?
- Which route families are repeatedly associated with feasible synthesis?
- What bridge motifs connect distinct candidate families?

---

## Implementation plan

### Phase 1: Design + schema normalization
- Add this design doc.
- Refactor `kg/schema.py` into a more explicit schema module.
- Separate real `Paper` nodes from `SearchQuery` placeholders.
- Introduce explicit `Claim`, `Condition`, `Property`, and provenance conventions.

### Phase 2: Chemistry identity upgrade
- Implement stronger molecule identity normalization.
- Add scaffold/substituent/attachment-site entities.
- Add decoration-pattern construction.

### Phase 3: Evidence normalization
- Convert critique outputs into normalized `Paper`, `EvidenceHit`, `EvidenceSnippet`, and `Claim` nodes.
- Add polarity and contradiction handling.
- Deduplicate papers by DOI/URL/title fingerprint.

### Phase 4: Retrieval / RAG subsystem
- Implement graph traversal retrieval utilities.
- Add hybrid graph + semantic retrieval.
- Return structured contexts for critique/reranking/reporting.

### Phase 5: Decision integration
- Feed KG-derived features into critique reranking.
- Attach decision provenance to shortlist and DFT handoff.
- Write validation feedback back into the KG.

### Phase 6: Backend hardening
- Keep JSON snapshots for local artifacts.
- Add a Neo4j backend or export path for production querying.
- Maintain stable IDs and ingest/merge logic.

---

## Proposed module additions

Suggested additions under `src/pz_agent/kg/`:

- `schema_v2.py`
  - typed schema definitions and required attrs
- `identity.py`
  - molecule/scaffold/substituent/site normalization
- `claims.py`
  - claim construction and normalization helpers
- `provenance.py`
  - provenance utilities
- `query_planner.py`
  - convert candidate state into retrieval plans
- `rag.py`
  - graph-aware retrieval API
- `merge.py`
  - deduplication and merge logic
- `neo4j_export.py`
  - optional property-graph export

Optional additions outside KG:
- `src/pz_agent/agents/kg_retrieval.py`
- `src/pz_agent/agents/validation.py`

---

## Near-term refactors for the current codebase

### Current `builder.py`
Refactor `build_graph_snapshot` into staged builders:
- `ingest_generation_layer(state)`
- `ingest_identity_layer(state)`
- `ingest_prediction_layer(state)`
- `ingest_claim_layer(state)`
- `ingest_decision_layer(state)`

### Current critique flow
Replace query-bundle nodes masquerading as papers with:
- `SearchQuery`
- `Paper`
- `EvidenceHit`
- `Claim`

### Current evidence report
Use the KG retrieval layer to produce:
- concise evidence-backed narratives
- support/contradiction summaries
- provenance-aware tables

---

## Minimum viable production KG milestone

A strong first production milestone would be:

1. Normalize molecule / scaffold / substituent identity
2. Normalize `Paper`, `Claim`, and `EvidenceHit`
3. Add `Condition` and `Property` nodes
4. Implement graph retrieval for critique
5. Have critique produce targeted searches based on retrieved graph gaps
6. Feed graph-derived support/contradiction features into reranking

If those six pieces are working, the KG stops being decorative and starts being operational.

---

## Summary

The production KG for `pz_agent` should become a chemistry-aware, evidence-centric, provenance-rich memory system that supports graph-aware RAG.

The most important shifts are:
- from papers to claims
- from candidate blobs to chemistry identity
- from search logs to evidence graphs
- from passive storage to graph-guided critique and reranking
- from flat artifact snapshots to durable scientific memory across runs
