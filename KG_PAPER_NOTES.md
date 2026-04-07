# KG_PAPER_NOTES.md

## Linked paper takeaways

### 1. SciAgents
Link: <https://advanced.onlinelibrary.wiley.com/doi/full/10.1002/adma.202413523>

Web search confirms this is the SciAgents paper.
Core design signals:
- ontological knowledge graphs
- multi-agent scientific reasoning
- paper-derived graph construction
- graph-guided hypothesis generation

### 2. Agentic Deep Graph Reasoning Yields Self-Organizing Knowledge Networks
Link: <https://arxiv.org/html/2502.13025v1>

Readable content was available.
Key ideas from the abstract/introduction:
- iterative graph expansion
- feedback-driven graph refinement
- bridge nodes and hub formation
- self-organizing graph structure
- graph-native reasoning rather than one-shot extraction

This strongly supports an iterative KG update pattern for pz_agent.

### 3. ScienceDirect KG paper
Link: <https://www.sciencedirect.com/science/article/pii/S1570826824000313>

Readable extraction was blocked by the site, but the user-provided paper is still relevant enough to motivate a broader scholarly-KG design.

## Concrete implications for pz_agent

The KG should be:
- provenance-aware
- iterative
- able to accumulate evidence each screening round
- able to carry bridge concepts across runs
- multi-modal (text + plots/images)

## Borrowed design principles

1. **Iterative refinement**
   - critique updates the graph every cycle
   - the graph is not static metadata

2. **Bridge node concept**
   - track motifs or substituents that connect otherwise separate candidate clusters
   - useful for identifying promising scaffold modifications

3. **Hub concept tracking**
   - track frequently supported motifs, models, or property trends
   - useful for surfacing repeated positive or negative signals

4. **Multimodal evidence**
   - store text snippets
   - store local generated plots
   - store figure references from papers when available

## Recommendation

For phenothiazine screening, use the KG as a living campaign memory with:
- candidate nodes
- literature-claim nodes
- media-artifact nodes
- bridge/hub analysis later as a graph analytics layer
