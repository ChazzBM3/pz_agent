# Literature Asymmetry + Phenothiazine Shortlist

## Slide title

**Why use a knowledge graph for phenothiazine discovery?**

## Left side: literature asymmetry

Using OpenAlex title/abstract search counts as a rough proxy for literature density:

- **Quinone**: `65,977` works
- **Phenothiazine**: `16,683` works
- **Quinone + redox flow battery**: `366` works
- **Phenothiazine + redox flow battery**: `74` works

### Interpretation

- Quinones occupy a much denser and more mature literature space.
- Phenothiazines are substantially sparser overall and also sparser in the redox-flow-battery-specific literature.
- That makes phenothiazines a poor fit for naive “just look it up” discovery.
- It also makes them a strong fit for structured transfer, retrieval, and graph-based reasoning.

## Right side: what the KG already recovers anyway

Even in this sparser literature space, the current KG already isolates an exact phenothiazine scaffold family with **22 molecules**, including **21 with oxidation-potential measurements**.

A simple KG-guided prioritization pass already surfaces a practical shortlist:

1. `05PNOK` — oxidation potential `1.151`, SA `2.88`
2. `05HONX` — oxidation potential `1.077`, SA `3.10`
3. `05KCEN` — oxidation potential `1.038`, SA `2.57`
4. `05PTMH` — oxidation potential `0.905`, SA `2.37`
5. `05BCMO` — oxidation potential `0.901`, SA `2.47`

## Bottom-line message

The point of the KG is not just to store a big chemistry dataset.

The point is that it lets us operate productively in a molecular space where:
- direct literature is thinner than in mature families such as quinones,
- measured evidence is uneven but not absent,
- and prioritization requires linking structures, measurements, provenance, and next-step actions.

## Suggested narration

“Quinones live in a much denser literature space than phenothiazines, both overall and in redox flow batteries specifically. That asymmetry is exactly why we need something more structured than keyword search. The knowledge graph gives us a way to organize sparse but real phenothiazine evidence, recover a compact measurement-rich subspace, and still produce an actionable shortlist for the next round of computational or experimental evaluation.”
