# GENMOL_EXTERNAL_PLAN.md

## Assumption

GenMol generation is performed outside `pz_agent`.
`pz_agent` is responsible for importing generated candidates plus provenance and then continuing the screening workflow.

## Supported initial import formats
- JSON
- CSV

## Validation
Imported records are validated with Pydantic.
At minimum, a candidate must provide:
- `smiles`

Optional fields:
- `id`
- `name`
- `prompt`
- `seed`
- `score`
- `generation_round`
- `notes`

## Config hook
Set in `configs/default.yaml`:
- `generation.external_genmol_path`

When set, `LibraryDesignerAgent` imports external candidates from that path instead of using placeholder molecules.

## KG provenance behavior
Imported generation metadata is surfaced in the KG via:
- `GenerationBatch` nodes
- `GENERATED_BY_BATCH` edges from molecules to the imported generation batch

## Why this is the right split
- keeps `pz_agent` independent of GenMol runtime details
- makes generation provenance explicit
- allows batch generation elsewhere and screening here
- matches the likely real workflow better than trying to run GenMol inside the pipeline package

## Next step after this scaffold
- propagate prompt/seed/round metadata more deeply into KG queries and reports
- add exact-match chemistry normalization once real molecules are imported
