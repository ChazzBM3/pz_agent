# STRUCTURE_MATCHING_PLAN.md

## Goal

Improve evidence typing from broad text heuristics toward chemistry-aware matching.

## Current scaffold
- `exact` if canonical SMILES or explicit name appears in evidence text
- `analog` if scaffold token appears
- `family` if the text only indicates phenothiazine-level relevance

## Future upgrade path
- exact matching by canonical identity / InChIKey
- analog matching by scaffold + substituent comparison
- fingerprint similarity thresholds via RDKit
- core-substructure detection for phenothiazine family assignment
