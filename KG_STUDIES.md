# KG_STUDIES.md

A running notebook for substantive knowledge-graph studies in `pz_agent`.

---

## 2026-04-22, Scaffold-aware support vs novelty ranking on a scaffold-diverse D3TaLES batch

### Purpose

Test whether the new parallel scaffold-aware ranking views actually diverge on a more scaffold-diverse real run, rather than on the earlier phenothiazine-heavy batch where most candidates fell into the same scaffold family.

### Run setup

Primary successful run:
- config: `configs/d3tales_scaffold_diverse_rankonly.yaml`
- run dir: `artifacts/run_scaffold_diverse_rankonly`

Supporting config created but not used for final interpretation because it failed in PubChem structure expansion on wider chemistry:
- `configs/d3tales_scaffold_diverse_demo.yaml`

### Top-level result

This run produced the first meaningful divergence between support-aware and novelty-aware shortlists.

Support top-8:
- `05JHCB`
- `05KCEN`
- `05QDYA`
- `05MNXL`
- `05KFIE`
- `05MJZZ`
- `05TRCY`
- `05PESY`

Novelty top-8:
- `05JHCB`
- `05QDYA`
- `05MNXL`
- `05KCEN`
- `05VEUX`
- `05KFIE`
- `05MJZZ`
- `05DUQU`

Overlap:
- `05JHCB`
- `05KCEN`
- `05KFIE`
- `05MJZZ`
- `05MNXL`
- `05QDYA`

Support-only:
- `05TRCY`
- `05PESY`

Novelty-only:
- `05VEUX`
- `05DUQU`

### Interpretation of support-only cases

#### `05TRCY`
- SMILES: `CCN1c2ccccc2Sc2ccc(C(F)(F)F)cc21`
- predicted priority: `0.6923`
- predicted synthesizability: `0.7333`
- predicted solubility: `0.53`
- scaffold: `c1ccc2c(c1)Nc1ccccc1S2`
- scaffold family size: `11`
- novelty adjustment: `0.045`
- support rank: `7`
- novelty rank: `9`

Interpretation:
- This remains attractive in the support-aware view because it sits in a denser, more familiar phenothiazine-family neighborhood.
- The molecule also has a reasonable predicted priority, so it stays near the shortlist boundary even without novelty emphasis.
- The trifluoromethyl substituent and electron-withdrawing skew suggest a more conventional “optimize within known phenothiazine family” direction than a true edge-of-distribution jump.

#### `05PESY`
- SMILES: `CCN1c2ccc(C)cc2Sc2cc(C)ccc21`
- predicted priority: `0.6757`
- predicted synthesizability: `0.7667`
- predicted solubility: `0.53`
- scaffold: `c1ccc2c(c1)Nc1ccccc1S2`
- scaffold family size: `11`
- novelty adjustment: `0.045`
- support rank: `8`
- novelty rank: `12`

Interpretation:
- This is an even more in-family case: a denser scaffold neighborhood and strong synthesizability, but no special novelty advantage.
- It looks like a safe, incremental phenothiazine-family candidate rather than a frontier candidate.

### Interpretation of novelty-only cases

#### `05VEUX`
- SMILES: `COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1`
- predicted priority: `0.66125`
- predicted synthesizability: `0.675`
- predicted solubility: `0.61`
- scaffold: `c1ccc(N(c2ccccc2)c2ccccc2)cc1`
- scaffold family size: `2`
- novelty adjustment: `0.09`
- support rank: `10`
- novelty rank: `5`

Interpretation:
- This is a smaller scaffold-family neighborhood with decent solubility and a strong novelty lift.
- It is not a random outlier. It remains reasonably competitive on predicted properties while also being much less in-distribution than the denser phenothiazine-family cases.
- Chemically, it looks like the kind of edge case that could broaden the search away from the main phenothiazine core while still preserving aromatic redox-relevant character.

#### `05DUQU`
- SMILES: `c1ccc(N(c2ccccc2)c2ccccc2)cc1`
- predicted priority: `0.6531`
- predicted synthesizability: `0.7583`
- predicted solubility: `0.49`
- scaffold: `c1ccc(N(c2ccccc2)c2ccccc2)cc1`
- scaffold family size: `2`
- novelty adjustment: `0.09`
- support rank: `12`
- novelty rank: `8`

Interpretation:
- This is the cleaner scaffold-edge case: highly supported by novelty because it sits in a tiny scaffold family, but less strong than the support-shortlist phenothiazines on the default score.
- It looks like a legitimate exploratory pick rather than a top exploitation pick.

### Main scientific takeaway

The support vs novelty split is now doing something chemically interpretable:
- support-aware ranking tends to favor candidates in the denser phenothiazine-family neighborhood
- novelty-aware ranking is willing to elevate candidates from a much smaller scaffold family when their predicted properties remain competitive

This is important because it means the parallel ranking design is not merely numerical decoration. It is exposing a real exploration vs exploitation tradeoff.

### Important implementation lesson

Earlier real runs showed no divergence because scaffold context was absent from the live campaign KG.
That was fixed by adding scaffold derivation to the runtime KG builder, after which real novelty adjustments became nonzero.

### Short interpretation note comparing the four focal molecules

Taken together, these four molecules show the distinction between exploitation and exploration quite cleanly.

- `05TRCY` and `05PESY` are both phenothiazine-family cases that look like safer local refinements.
  - They sit in the denser scaffold family `c1ccc2c(c1)Nc1ccccc1S2`.
  - Their ranking strength comes from staying near the established phenothiazine neighborhood while preserving decent predicted performance.
  - They look like sensible candidates when the goal is to keep learning inside the known phenothiazine basin.

- `05VEUX` and `05DUQU` are the exploratory counterpoint.
  - They sit in the much smaller scaffold family `c1ccc(N(c2ccccc2)c2ccccc2)cc1`.
  - They are not obviously dominant on the base score alone, but they become interesting once the ranking explicitly rewards edge-of-distribution scaffold neighborhoods.
  - `05VEUX` looks like the more attractive exploratory pick of the two because it keeps somewhat better solubility than `05DUQU` while still benefiting from the same novelty lift.

A useful way to summarize the quartet is:
- `05TRCY` and `05PESY` are better exploitation candidates
- `05VEUX` is the most compelling exploration candidate
- `05DUQU` is a cleaner but somewhat harsher exploratory baseline inside the same smaller scaffold family

That makes this set a good teaching example for why the project should keep support-aware and novelty-aware ranking as parallel views rather than collapsing them into one score.

## 2026-04-22, Scaffold-family comparison for support-only vs novelty-only cases

### Purpose

Compare the two scaffold families surfaced by the scaffold-diverse rank-only run to understand whether the novelty-only family is winning purely by a heuristic bonus or whether it remains reasonably competitive on the base predicted properties.

### Families compared

#### Dense phenothiazine-family scaffold
- scaffold: `c1ccc2c(c1)Nc1ccccc1S2`
- role in run: source of the support-only cases `05TRCY` and `05PESY`
- family size in the run KG: `11`

#### Smaller novelty-favored scaffold family
- scaffold: `c1ccc(N(c2ccccc2)c2ccccc2)cc1`
- role in run: source of the novelty-only cases `05VEUX` and `05DUQU`
- family size in the run KG: `2`

### Property comparison from the run

#### Dense phenothiazine-family scaffold `c1ccc2c(c1)Nc1ccccc1S2`
- molecule count: `11`
- predicted priority:
  - min: `0.5473`
  - median: `0.6757`
  - max: `0.7545`
  - mean: `0.6729`
- predicted synthesizability:
  - min: `0.5333`
  - median: `0.7333`
  - max: `0.7667`
  - mean: `0.6856`
- predicted solubility:
  - min: `0.53`
  - median: `0.53`
  - max: `0.77`
  - mean: `0.5664`
- novelty adjustment:
  - uniformly `0.045`

Interpretation:
- This family is broader and stronger on the default support-oriented view because it occupies the established phenothiazine neighborhood.
- It also spans a wider performance range, including some of the strongest base-score molecules in the run.
- The novelty view does not reject this family; it simply does not reward it as aggressively because it is already relatively in-distribution.

#### Smaller scaffold family `c1ccc(N(c2ccccc2)c2ccccc2)cc1`
- molecule count: `2`
- predicted priority:
  - min: `0.6531`
  - median: `0.6572`
  - max: `0.6613`
  - mean: `0.6572`
- predicted synthesizability:
  - min: `0.6750`
  - median: `0.7167`
  - max: `0.7583`
  - mean: `0.7167`
- predicted solubility:
  - min: `0.49`
  - median: `0.55`
  - max: `0.61`
  - mean: `0.55`
- novelty adjustment:
  - uniformly `0.09`

Interpretation:
- This family is not outperforming the dense phenothiazine family on raw predicted priority alone.
- But it is close enough to remain scientifically plausible, especially given decent synthesizability and acceptable solubility.
- That is what makes it a useful novelty target: it is small and less in-distribution, but not obviously weak.

### Main takeaway

The novelty-only family is not being promoted from irrelevance. It is being promoted from **competitive but less-supported territory**.

That distinction matters:
- if the family were much worse on base predicted properties, the novelty ranking would look like a noise generator
- instead, the family appears plausible enough that rewarding edge-of-distribution scaffold neighborhoods produces a scientifically interpretable exploratory shortlist

### Limitations of this study

This particular run was intentionally rank-focused and did not carry rich literature/critique support into the final comparison. So this study is best understood as:
- a scaffold-family and property-profile comparison
- not yet a full literature-support comparison

### Suggested next studies

1. Run a larger scaffold-diverse batch to see whether the novelty view continues to surface coherent families rather than one-off anomalies.
2. Add literature and critique context back into a scaffold-diverse run once the wider-chemistry retrieval path is made less brittle.
3. Compare whether novelty-only families eventually receive simulation budget and whether they validate as promising exploratory directions.
