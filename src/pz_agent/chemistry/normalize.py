from __future__ import annotations

from typing import Any

from pz_agent.chemistry.identity import MoleculeIdentity

try:
    from rdkit import Chem
    from rdkit.Chem import inchi
    RDKIT_AVAILABLE = True
except Exception:
    Chem = None
    inchi = None
    RDKIT_AVAILABLE = False


PHENOTHIAZINE_SCAFFOLD_HINT = "phenothiazine"


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
            scaffold = PHENOTHIAZINE_SCAFFOLD_HINT
    else:
        canonical_smiles = input_smiles
        if input_smiles:
            scaffold = PHENOTHIAZINE_SCAFFOLD_HINT

    identity = MoleculeIdentity(
        input_smiles=input_smiles,
        canonical_smiles=canonical_smiles,
        inchi=inchi_value,
        inchikey=inchikey,
        scaffold=scaffold,
        name=name,
        source_name=name,
        match_tokens=[token for token in [name, canonical_smiles, scaffold] if token],
    )

    enriched = dict(record)
    enriched["identity"] = identity.to_dict()
    enriched["rdkit_available"] = RDKIT_AVAILABLE
    return enriched


def normalize_library(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_molecule_identity(record) for record in records]
