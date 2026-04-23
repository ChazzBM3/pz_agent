# Phenothiazine KG Slide Notes

## What the current KG already knows about phenothiazines

Using the current production KG artifact (`artifacts/kg_prod_2026_04_22/d3tales_kg.json`), the exact phenothiazine scaffold `c1ccc2c(c1)Nc1ccccc1S2` currently maps to **22 molecules**.

All 22 come from the `Odom_aman` source group, and coverage is surprisingly dense within this narrow family:

- `22/22` have `sa_score`
- `22/22` have HOMO, LUMO, HOMO-LUMO gap, solvation energy, dipole moment, molecular weight, globular volume, atom count, and `omega`
- `21/22` have `oxidation_potential`
- `21/22` have `adiabatic_ionization_energy`
- `21/22` have `hole_reorganization_energy`
- `20/22` have `reduction_potential`
- `20/22` have `electron_reorganization_energy`
- `20/22` have `adiabatic_electron_affinity`

So the KG is not just large in aggregate, it already contains a compact, measurement-rich phenothiazine subspace that is immediately useful for prioritization.

## Top phenothiazines by oxidation potential in the current KG

Top measured examples are:

1. `05PNOK` — oxidation potential `1.151`, reduction potential `5.436`, SA score `2.88`
2. `05HONX` — oxidation potential `1.077`, SA score `3.10`
3. `05KCEN` — oxidation potential `1.038`, reduction potential `6.647`, SA score `2.57`
4. `05UYEV` — oxidation potential `0.924`, reduction potential `6.263`, SA score `3.01`
5. `05PTMH` — oxidation potential `0.905`, reduction potential `5.506`, SA score `2.37`

## Suggested slide message

- The global KG is large, but the phenothiazine slice is already scientifically useful on its own.
- Even within a small exact-scaffold family, the KG preserves dense property coverage rather than just sparse identifiers.
- This means the next discovery step can be guided by measured phenothiazine structure-property relationships, not only by transfer from quinones.
