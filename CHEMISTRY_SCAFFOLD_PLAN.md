# CHEMISTRY_SCAFFOLD_PLAN.md

## Goal

Add a chemistry identity and normalization layer so molecules have stable identities and future literature matching can distinguish exact vs analog vs family evidence.

## Implemented pieces
- `MoleculeIdentity` schema
- normalization module with optional RDKit support
- simple match classifier scaffold

## Current behavior
- if RDKit is available:
  - canonical SMILES is generated
  - InChI and InChIKey are attempted
- if RDKit is unavailable:
  - raw SMILES is preserved as canonical placeholder
- scaffold is currently set to a phenothiazine hint placeholder

## Next steps
- use RDKit Murcko scaffold or substructure logic
- add better exact/analog classification
- use normalized identity in literature query generation
- propagate identity fields into enriched KG relations
