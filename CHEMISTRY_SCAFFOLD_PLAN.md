# CHEMISTRY_SCAFFOLD_PLAN.md

## Goal

Add a chemistry identity and normalization layer so molecules have stable identities and future literature matching can distinguish exact vs analog vs family evidence.

## Implemented pieces
- `MoleculeIdentity` schema
- normalization module with RDKit support
- Murcko scaffold extraction when RDKit is available
- simple match classifier scaffold

## Current behavior
- if RDKit is available:
  - canonical SMILES is generated
  - InChI and InChIKey are attempted
  - Murcko scaffold is derived when possible
- if RDKit is unavailable:
  - raw SMILES is preserved as canonical placeholder
- a phenothiazine query hint is still retained for broader literature search support

## Next steps
- use substructure logic for phenothiazine-core detection
- add better exact/analog classification using structure-aware comparisons
- use normalized identity in literature query generation and enriched reranking
- propagate identity fields into enriched KG relations
