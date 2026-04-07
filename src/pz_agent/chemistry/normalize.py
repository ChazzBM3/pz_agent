from __future__ import annotations

from typing import Any

from pz_agent.chemistry.identity import MoleculeIdentity

try:
    from rdkit import Chem
    from rdkit.Chem import inchi
    from rdkit.Chem.Scaffolds import MurckoScaffold
    RDKIT_AVAILABLE = True
except Exception:
    Chem = None
    inchi = None
    MurckoScaffold = None
    RDKIT_AVAILABLE = False


PHENOTHIAZINE_QUERY_HINT = "phenothiazine derivative"
PHENOTHIAZINE_CORE_ASSUMPTION = "phenothiazine"


def _derive_scaffold(mol) -> str | None:
    if not RDKIT_AVAILABLE or mol is None:
        return None
    try:
        scaffold_mol = MurckoScaffold.GetScaffoldForMol(mol)
        if scaffold_mol is None:
            return None
        return Chem.MolToSmiles(scaffold_mol, canonical=True)
    except Exception:
        return None


def _estimate_decoration_summary(canonical_smiles: str | None) -> tuple[str | None, int | None, list[str]]:
    if not canonical_smiles:
        return None, None, []
    hetero_tokens = []
    for token in ["N", "O", "S", "F", "Cl", "Br", "I", "C#N", "C(=O)"]:
        if token in canonical_smiles:
            hetero_tokens.append(token)
    substituent_count = len(hetero_tokens)
    summary = "none_detected" if not hetero_tokens else "+".join(sorted(set(hetero_tokens)))
    return summary, substituent_count, sorted(set(hetero_tokens))


def normalize_molecule_identity(record: dict[str, Any]) -> dict[str, Any]:
    input_smiles = record.get("smiles")
    name = record.get("name")
    canonical_smiles = None
    inchi_value = None
    inchikey = None
    scaffold = None

    if RDKIT_AVAILABLE and input_smiles:
        mol = Chem.MolFromSmiles(input_smiles)
        if mol is not None:
            canonical_smiles = Chem.MolToSmiles(mol, canonical=True)
            try:
                inchi_value = inchi.MolToInchi(mol)
                inchikey = inchi.InchiToInchiKey(inchi_value) if inchi_value else None
            except Exception:
                inchi_value = None
                inchikey = None
            scaffold = _derive_scaffold(mol)
    else:
        canonical_smiles = input_smiles

    decoration_summary, substituent_count, decoration_tokens = _estimate_decoration_summary(canonical_smiles)

    identity = MoleculeIdentity(
        input_smiles=input_smiles,
        canonical_smiles=canonical_smiles,
        inchi=inchi_value,
        inchikey=inchikey,
        scaffold=scaffold or PHENOTHIAZINE_QUERY_HINT,
        name=name,
        source_name=name,
        core_assumption=PHENOTHIAZINE_CORE_ASSUMPTION,
        decoration_summary=decoration_summary,
        substituent_count=substituent_count,
        decoration_tokens=decoration_tokens,
        match_tokens=[
            token
            for token in [
                name,
                canonical_smiles,
                scaffold,
                decoration_summary,
                *decoration_tokens,
                PHENOTHIAZINE_QUERY_HINT,
            ]
            if token
        ],
    )

    enriched = dict(record)
    enriched["identity"] = identity.to_dict()
    enriched["rdkit_available"] = RDKIT_AVAILABLE
    return enriched


def normalize_library(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_molecule_identity(record) for record in records]
