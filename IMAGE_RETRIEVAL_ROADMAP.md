# IMAGE_RETRIEVAL_ROADMAP.md

## Goal

Replace the current image-to-phrase experiment as the main multimodal direction with a structure-first retrieval pipeline:

**SMILES -> structure expansion -> patent/page retrieval -> page-image retrieval -> Gemma rerank/justify**

This should make multimodal reasoning support retrieval and evidence ranking, rather than asking a vision model to invent search phrases from a rendered structure.

---

## Why pivot away from the current Gemini phrase-search path

The direct Gemini image path is real and working:
- RDKit renders can be sent to Gemini
- Gemini can return useful chemistry descriptions
- the benchmark showed successful multimodal responses for 3 of 4 target compounds

But the benchmark also showed the core limitation:
- Gemini-derived outputs did not materially improve downstream query construction yet
- positional assignments can still be noisy
- the current value is better as reranking/explanation than as the primary search method

Conclusion:
- keep the benchmark and direct vision client as an experiment
- do **not** make phrase-generation from structure images the core retrieval path

---

## Recommended architecture

### Stage 0. Normalize the target structure

Input:
- candidate SMILES from GenMol / D3TaLES / external import

Use:
- RDKit canonicalization
- InChI / InChIKey generation
- Murcko scaffold extraction
- substituent summaries
- positional/substitution pattern heuristics

Outputs:
- canonical identity bundle
- scaffold bundle
- formula / synonyms / naming fragments
- depiction assets for retrieval probes

Suggested module:
- `src/pz_agent/chemistry/query_generation.py`

---

### Stage 1. Query asset generation with RDKit + RanDepict

Purpose:
- generate robust structure-native retrieval inputs, not just text phrases

Use:
- RDKit for canonical 2D render
- RanDepict for depiction variations that help page-image retrieval and multimodal matching

Outputs:
- canonical depiction PNG
- alternate depiction variants
- structured text query templates
- retrieval tokens such as:
  - exact name / IUPAC fragments
  - scaffold + substituent descriptors
  - formula + scaffold
  - exact and analog query packs

Suggested module:
- `src/pz_agent/chemistry/query_generation.py`

Notes:
- RanDepict should be optional behind a feature flag
- if unavailable, fall back to RDKit-only depiction assets

---

### Stage 2. Structure expansion with PubChem

Purpose:
- anchor exact identity and discover useful analogs / related records before literature search

Use PubChem for:
- exact identity lookup
- synonym expansion
- CID mapping
- similarity candidates
- substructure candidates
- formula / known-name recovery

Outputs:
- exact identity hits
- related analog set
- expanded synonym/name inventory
- candidate relationship graph

Suggested module:
- `src/pz_agent/retrieval/pubchem.py`

Key artifact:
- `structure_expansion.json`

Priority:
- **high**, likely the first new external retrieval integration to build

---

### Stage 3. Patent-first retrieval with SureChEMBL + PatCID

Purpose:
- retrieve chemistry-rich sources where structures, compound tables, and figure evidence are common

Use:
- SureChEMBL for chemistry-aware patent retrieval
- PatCID for patent metadata and document-level grounding

Outputs:
- patent candidate list
- matched compounds / analog candidates
- figure/table-rich document candidates
- snippets / metadata / document identifiers

Suggested module:
- `src/pz_agent/retrieval/patents.py`

Key artifact:
- `patent_retrieval.json`

Why patent-first:
- patents are more likely than standard scholarly metadata search to contain directly useful structure-adjacent evidence
- this fits the intended figure/page retrieval path better than raw web image search

---

### Stage 4. Scholarly metadata retrieval with OpenAlex

Purpose:
- complement structure expansion and patent retrieval with general scholarly coverage

Use OpenAlex for:
- title / abstract / full-text search where available
- semantic search for related works
- citation/context expansion from exact or analog hits

Outputs:
- scholarly works list
- metadata bundle
- text-side evidence candidates

Suggested module:
- `src/pz_agent/retrieval/openalex_expanded.py`

Key artifact:
- `scholarly_retrieval.json`

Notes:
- OpenAlex should be a companion layer after structure expansion, not the only retrieval path

---

### Stage 5. Page corpus assembly

Purpose:
- assemble a local evidence corpus before doing multimodal page-image retrieval

Inputs:
- patent retrieval outputs
- OpenAlex / publisher landing pages
- PDFs and supplemental materials where available
- figure-caption pages and local downloads

Outputs:
- normalized page records
- figure image records
- caption/snippet associations
- OCR-ready extraction targets

Suggested modules:
- `src/pz_agent/retrieval/page_corpus.py`
- `src/pz_agent/retrieval/document_fetch.py`

Key artifacts:
- `page_corpus.json`
- `figures.json`

Important rule:
- do retrieval first, then build a local multimodal corpus
- do **not** start from broad web image search

---

### Stage 6. Chemistry-object extraction from corpus

Purpose:
- turn pages and figures into chemistry-aware objects, not just text blobs

Use:
- MolScribe
- DECIMER
- OpenChemIE

Targets:
- patent figures
- article figures
- captions
- compound tables
- OCR’d compound labels / structure-adjacent text

Outputs:
- extracted structures
- extracted names / labels
- extracted reaction or property mentions
- structure-to-page associations

Suggested module:
- `src/pz_agent/vision/structure_extract.py`

Key artifact:
- `corpus_chemistry_extraction.json`

Notes:
- this is powerful, but should come after page corpus assembly
- defer until the retrieval/corpus path is stable enough to justify the added complexity

---

### Stage 7. Page-image retrieval with ColPali

Purpose:
- retrieve visually relevant pages or figures from the local corpus

Use ColPali for:
- page-image retrieval over already-collected pages
- matching target structure depictions to page/figure content

Inputs:
- target depiction assets from RDKit / RanDepict
- page images / figure crops from the local corpus

Outputs:
- ranked page candidates
- ranked figure candidates
- image similarity evidence

Suggested module:
- `src/pz_agent/vision/page_retrieval.py`

Key artifact:
- `page_image_retrieval.json`

Notes:
- this is the right place for image retrieval
- use retrieval over the local evidence corpus, not general web image search

---

### Stage 8. Gemma 4 multimodal reranking and explanation

Purpose:
- use multimodal models where they add the most value: scoring, disambiguation, and explanation

Gemma 4 inputs:
- target structure depiction
- retrieved page image or figure crop
- caption text
- OCR snippet
- candidate metadata
- exact/analog context from PubChem/patent expansion

Outputs:
- exact match / analog / unrelated judgment
- relevance to redox / solubility / synthesis
- concise justification
- confidence score

Suggested module:
- `src/pz_agent/vision/rerank_gemma.py`

Key artifact:
- `multimodal_rerank.json`

Important rule:
- Gemma should rerank and justify evidence
- Gemma should **not** be the first-stage retrieval engine

---

## Proposed stage ordering in the pipeline

Recommended future stage order:
1. `library_designer`
2. `standardizer`
3. `structure_expansion`
4. `patent_retrieval`
5. `scholarly_retrieval`
6. `page_corpus`
7. `page_image_retrieval`
8. `critique`
9. `multimodal_rerank`
10. `knowledge_graph`
11. `critique_reranker`
12. `reporter`

Initial MVP stage order:
1. `library_designer`
2. `standardizer`
3. `structure_expansion`
4. `patent_retrieval`
5. `scholarly_retrieval`
6. `critique`
7. `knowledge_graph`
8. `critique_reranker`
9. `reporter`

This keeps the first slice manageable while setting up the later page/vision work.

---

## MVP implementation plan

### MVP-1. Structure expansion

Build first:
- PubChem exact/similarity/substructure adapter
- normalized expansion artifact
- integration into candidate critique planning

Files:
- `src/pz_agent/retrieval/pubchem.py`
- `src/pz_agent/agents/structure_expansion.py`
- `tests/test_pubchem_expansion.py`

Success criteria:
- given a candidate SMILES, produce exact identity hits and related analog candidates
- attach expanded synonyms / IDs / formulas to candidate evidence bundles

---

### MVP-2. Patent retrieval

Build next:
- SureChEMBL + PatCID adapters
- merged patent candidate artifact
- compound/patent evidence bundles

Files:
- `src/pz_agent/retrieval/patents.py`
- `tests/test_patent_retrieval.py`

Success criteria:
- retrieve patent-side evidence candidates for a target or analog
- normalize identifiers and metadata for KG insertion

---

### MVP-3. OpenAlex scholarly companion

Build next:
- expanded OpenAlex retrieval driven by structure expansion outputs
- exact-name / analog-aware query templates

Files:
- `src/pz_agent/retrieval/openalex_expanded.py`
- `tests/test_openalex_expanded.py`

Success criteria:
- scholarly retrieval reflects exact names, analog names, and scaffold descriptors from structure expansion

---

### MVP-4. Critique integration

Build next:
- update critique to consume expansion/patent/scholarly artifacts
- rank evidence sources by confidence tier:
  - exact structure support
  - analog support
  - patent support
  - generic text support

Files:
- `src/pz_agent/agents/critique.py`
- `src/pz_agent/kg/builder.py`
- `src/pz_agent/kg/retrieval.py`

Success criteria:
- critique bundles are structure-aware before web text search heuristics fire
- KG gets explicit support provenance from structure expansion and patent retrieval

---

## Deferred multimodal slice

Once the MVP is stable:

### Phase 2
- page corpus assembly
- figure extraction
- OCR/caption association

### Phase 3
- ColPali page-image retrieval over local corpus

### Phase 4
- Gemma 4 rerank/justify for top page/figure evidence

### Phase 5
- MolScribe / DECIMER / OpenChemIE chemistry-object extraction from page corpus

---

## What to keep from the current Gemini work

Keep:
- `vision_client.py`
- `visual_benchmark.py`
- benchmark outputs and evaluation habit

Change the role:
- treat them as an experiment harness for multimodal chemistry extraction
- do not let them define the main retrieval architecture

Potential reuse:
- the current direct Gemini client can later become a benchmark baseline against Gemma 4 reranking

---

## Decision criteria for success

A new retrieval stage should only stay if it improves at least one of:
- exact identity recovery
- analog identification quality
- patent/page evidence quality
- ranking signal quality
- explanation quality for top candidates

Do not keep components just because they are multimodal or technically interesting.

---

## Immediate recommendation

Implement this next, in order:
1. `structure_expansion` via PubChem
2. `patent_retrieval` via SureChEMBL + PatCID
3. `scholarly_retrieval` refinement with OpenAlex using expansion outputs
4. critique/KG integration

Only after that:
5. page corpus assembly
6. ColPali page-image retrieval
7. Gemma 4 multimodal reranking
8. chemistry-object extraction with MolScribe / DECIMER / OpenChemIE

That path gives the highest chance of turning multimodal retrieval into something scientifically useful instead of just impressive-looking output.
