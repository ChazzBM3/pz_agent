from __future__ import annotations

from typing import Any

from pz_agent.chemistry.identity import MoleculeIdentity
from pz_agent.chemistry.naming import smiles_to_iupac_name

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

EDG_TOKENS = {"N", "O"}
EWG_TOKENS = {"F", "Cl", "Br", "I", "C#N", "C(=O)"}


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


def _estimate_decoration_summary(canonical_smiles: str | None) -> tuple[str | None, int | None, list[str], list[str], str | None]:
    if not canonical_smiles:
        return None, None, [], [], None
    detected = []
    for token in ["N", "O", "S", "F", "Cl", "Br", "I", "C#N", "C(=O)"]:
        if token in canonical_smiles:
            detected.append(token)
    unique_tokens = sorted(set(detected))
    substituent_count = len(unique_tokens)
    summary = "none_detected" if not unique_tokens else "+".join(unique_tokens)
    fragments = [f"frag:{token}" for token in unique_tokens]
    edg_count = len([t for t in unique_tokens if t in EDG_TOKENS])
    ewg_count = len([t for t in unique_tokens if t in EWG_TOKENS])
    if edg_count > ewg_count:
        bias = "electron_donating_skew"
    elif ewg_count > edg_count:
        bias = "electron_withdrawing_skew"
    elif unique_tokens:
        bias = "mixed"
    else:
        bias = None
    return summary, substituent_count, unique_tokens, fragments, bias


def _attachment_summary(unique_tokens: list[str]) -> list[str]:
    return [f"phenothiazine_core+{token}" for token in unique_tokens]


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

    decoration_summary, substituent_count, decoration_tokens, substituent_fragments, electronic_bias = _estimate_decoration_summary(canonical_smiles)
    attachment_summary = _attachment_summary(decoration_tokens)
    iupac_name = smiles_to_iupac_name(input_smiles)

    identity = MoleculeIdentity(
        input_smiles=input_smiles,
        canonical_smiles=canonical_smiles,
        inchi=inchi_value,
        inchikey=inchikey,
        scaffold=scaffold or PHENOTHIAZINE_QUERY_HINT,
        name=name,
        source_name=name,
        iupac_name=iupac_name,
        core_assumption=PHENOTHIAZINE_CORE_ASSUMPTION,
        decoration_summary=decoration_summary,
        substituent_count=substituent_count,
        decoration_tokens=decoration_tokens,
        substituent_fragments=substituent_fragments,
        attachment_summary=attachment_summary,
        electronic_bias=electronic_bias,
        match_tokens=[
            token
            for token in [
                name,
                canonical_smiles,
                scaffold,
                iupac_name,
                decoration_summary,
                electronic_bias,
                *decoration_tokens,
                *substituent_fragments,
                *attachment_summary,
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
