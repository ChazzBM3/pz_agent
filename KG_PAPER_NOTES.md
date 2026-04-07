# KG_PAPER_NOTES.md

## What I could reliably extract

The local PDF parser did not yield clean text from `kg1.pdf`, `kg2.pdf`, and `kg3.pdf`, but it did reveal enough metadata and structure to be useful:

- `kg1.pdf` includes DOI metadata pointing to **10.1002/adma.202413523**.
- Web search confirms this is the **SciAgents** paper:
  - *SciAgents: Automating scientific discovery through multi-agent intelligent graph reasoning*
- `kg2.pdf` clearly contains embedded figure/image assets and page-linked graphics.
- `kg3.pdf` also appears image/PDF-object heavy rather than plain-text extractable through the current reader.

## Literature signals worth borrowing

### 1. SciAgents pattern
From search results around `10.1002/adma.202413523`:
- combines **ontological knowledge graphs** with **multi-agent reasoning**
- uses scientific-paper-derived graph structure for hypothesis generation
- treats graph reasoning as more than document retrieval

### 2. Scholarly knowledge graph literature
The broader KG literature repeatedly supports:
- provenance-aware scholarly entities
- graph storage for linked evidence, methods, datasets, and claims
- graph representations that support visual artifacts and figure references, not just raw text

### 3. Chemistry KG construction literature
The CEAR-style direction supports:
- extracting chemistry entities and relations from literature
- grounding graph statements in papers
- keeping links back to source literature rather than storing only interpreted summaries

## Design takeaway for pz_agent

The KG for this project should include both:
- **text evidence**
  - snippets
  - claims
  - paper metadata
  - extracted assertions
- **media evidence**
  - figure references
  - plot references
  - local generated plots
  - external figure/image provenance when available

## Proposed media-aware KG additions

### New entity type
- `MediaArtifact`

### New relation
- `HAS_MEDIA_EVIDENCE`

### Example media artifact payload
```json
{
  "id": "media::pz_001::0",
  "kind": "plot_or_figure",
  "caption": "Solubility ranking plot for candidate pz_001",
  "source_url": null,
  "image_path": "artifacts/plots/pz_001_solubility.png",
  "media_type": "plot",
  "provenance": {
    "source_type": "generated_plot",
    "confidence": 1.0
  }
}
```

## Recommendation

Use the KG as a **multi-modal scientific memory**:
- molecules
- predictions
- literature evidence
- critique summaries
- DFT results
- generated plots/images
- literature figure references

That is a better fit for this project than plain text long-term memory alone.
