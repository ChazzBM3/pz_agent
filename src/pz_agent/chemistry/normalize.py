from __future__ import annotations

from typing import Any

from pz_agent.chemistry.identity import MoleculeIdentity
from pz_agent.chemistry.naming import smiles_to_iupac_name

try:
    from rdkit import Chem
    from rdkit.Chem import inchi
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold
    RDKIT_AVAILABLE = True
except Exception:
    Chem = None
    inchi = None
    rdMolDescriptors = None
    MurckoScaffold = None
    RDKIT_AVAILABLE = False


PHENOTHIAZINE_QUERY_HINT = "phenothiazine derivative"
PHENOTHIAZINE_CORE_ASSUMPTION = "phenothiazine"

EDG_TOKENS = {"N", "O"}
EWG_TOKENS = {"F", "Cl", "Br", "I", "C#N", "C(=O)", "CF3"}

PHENOTHIAZINE_SMARTS = "c1ccc2c(c1)Nc1ccccc1S2"
THIANTHRENE_SMARTS = "c1ccc2c(c1)Sc1ccccc1S2"
PHENOXAZINE_SMARTS = "c1ccc2c(c1)Oc1ccccc1N2"


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


def _classify_neighbor_substituent(neighbor) -> str | None:
    atomic_num = neighbor.GetAtomicNum()
    if atomic_num == 9:
        return "F"
    if atomic_num == 17:
        return "Cl"
    if atomic_num == 35:
        return "Br"
    if atomic_num == 53:
        return "I"
    if atomic_num == 8:
        return "O"
    if atomic_num == 7:
        return "N"
    if atomic_num == 16:
        return "S"
    if atomic_num == 6:
        fluorine_neighbors = sum(1 for nn in neighbor.GetNeighbors() if nn.GetAtomicNum() == 9)
        oxygen_bond = any(
            bond.GetBondTypeAsDouble() == 2.0 and bond.GetOtherAtom(neighbor).GetAtomicNum() == 8
            for bond in neighbor.GetBonds()
        )
        nitrogen_bond = any(
            bond.GetBondTypeAsDouble() >= 2.0 and bond.GetOtherAtom(neighbor).GetAtomicNum() == 7
            for bond in neighbor.GetBonds()
        )
        if fluorine_neighbors >= 3:
            return "CF3"
        if oxygen_bond:
            return "C(=O)"
        if nitrogen_bond:
            return "C#N"
    return None



def _phenothiazine_position_map(match: tuple[int, ...]) -> dict[int, str]:
    if len(match) != 14:
        return {}
    return {
        match[0]: "2",
        match[1]: "3",
        match[2]: "4",
        match[8]: "6",
        match[9]: "7",
        match[10]: "8",
        match[6]: "10",
    }



def _relative_ring_label(position_numbers: list[str]) -> str | None:
    numeric = [p for p in position_numbers if p.isdigit()]
    if len(numeric) < 2:
        return None
    ring_positions = sorted(int(p) for p in numeric[:2])
    pair = tuple(ring_positions)
    if pair in {(2, 3), (6, 7)}:
        return "ortho"
    if pair in {(2, 4), (6, 8), (3, 4), (7, 8)}:
        return "meta"
    if pair in {(2, 7), (3, 6), (4, 8)}:
        return "para"
    return None



def _chain_position_label(atom, neighbor) -> str | None:
    if atom.GetAtomicNum() == 7 and neighbor.GetAtomicNum() == 6:
        carbon_neighbors = [nn for nn in neighbor.GetNeighbors() if nn.GetIdx() != atom.GetIdx() and nn.GetAtomicNum() == 6]
        if carbon_neighbors:
            return "alpha"
        return "alpha"
    return None



def _detect_core_family(mol) -> tuple[str, float]:
    if not RDKIT_AVAILABLE or mol is None:
        return PHENOTHIAZINE_CORE_ASSUMPTION, 0.0
    patterns = [
        ("phenothiazine", PHENOTHIAZINE_SMARTS, 1.0),
        ("thianthrene", THIANTHRENE_SMARTS, 0.95),
        ("phenoxazine", PHENOXAZINE_SMARTS, 0.95),
    ]
    for label, smarts, confidence in patterns:
        pattern = Chem.MolFromSmarts(smarts)
        if pattern is not None and mol.HasSubstructMatch(pattern):
            return label, confidence
    return PHENOTHIAZINE_CORE_ASSUMPTION, 0.2



def _estimate_decoration_summary_from_mol(mol) -> tuple[str | None, int | None, list[str], list[str], list[str], str | None, list[str]]:
    if not RDKIT_AVAILABLE or mol is None:
        return None, None, [], [], [], None, []
    pattern = Chem.MolFromSmarts(PHENOTHIAZINE_SMARTS)
    if pattern is None:
        return None, None, [], [], [], None, []
    matches = mol.GetSubstructMatches(pattern)
    if not matches:
        return None, None, [], [], [], None, []

    match = matches[0]
    core_atoms = set(match)
    position_map = _phenothiazine_position_map(match)
    detected_tokens: list[str] = []
    substituent_fragments: list[str] = []
    attachment_summary: list[str] = []
    positional_tokens: list[str] = []
    ring_positions: list[str] = []

    for atom_idx in match:
        atom = mol.GetAtomWithIdx(atom_idx)
        for neighbor in atom.GetNeighbors():
            if neighbor.GetIdx() in core_atoms:
                continue
            token = _classify_neighbor_substituent(neighbor)
            if not token:
                continue
            detected_tokens.append(token)
            attachment_summary.append(f"phenothiazine_core+{token}")
            position_label = position_map.get(atom_idx)
            if position_label:
                ring_positions.append(position_label)
                positional_tokens.append(f"position {position_label} {token}")
            chain_label = _chain_position_label(atom, neighbor)
            if chain_label:
                positional_tokens.append(f"{chain_label} {token}")
            if token == "CF3":
                substituent_fragments.append("frag:trifluoromethyl")
            elif token == "C(=O)":
                substituent_fragments.append("frag:carbonyl")
            elif token == "C#N":
                substituent_fragments.append("frag:cyano")
            else:
                substituent_fragments.append(f"frag:{token}")

    relative_label = _relative_ring_label(ring_positions)
    if relative_label:
        positional_tokens.append(relative_label)

    unique_tokens = sorted(set(detected_tokens))
    unique_fragments = substituent_fragments
    unique_attachments = attachment_summary
    unique_positions = positional_tokens
    substituent_count = len(substituent_fragments)
    summary = "none_detected" if not unique_tokens else "+".join(unique_tokens)
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
    substitution_pattern = None
    if substituent_count == 1:
        substitution_pattern = "mono_substituted"
    elif substituent_count == 2:
        substitution_pattern = "di_substituted"
    elif substituent_count >= 3:
        substitution_pattern = "poly_substituted"
    return summary, substituent_count, unique_tokens, unique_fragments, unique_attachments, bias, unique_positions


def normalize_molecule_identity(record: dict[str, Any]) -> dict[str, Any]:
    input_smiles = record.get("smiles")
    name = record.get("name")
    canonical_smiles = None
    inchi_value = None
    inchikey = None
    scaffold = None

    mol = None
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

    decoration_summary = None
    substituent_count = None
    decoration_tokens = []
    substituent_fragments = []
    attachment_summary = []
    electronic_bias = None
    positional_tokens: list[str] = []
    substitution_pattern = None
    if mol is not None:
        decoration_summary, substituent_count, decoration_tokens, substituent_fragments, attachment_summary, electronic_bias, positional_tokens = _estimate_decoration_summary_from_mol(mol)
        if substituent_count == 1:
            substitution_pattern = "mono_substituted"
        elif substituent_count == 2:
            substitution_pattern = "di_substituted"
        elif substituent_count and substituent_count >= 3:
            substitution_pattern = "poly_substituted"
    core_detected, core_confidence = _detect_core_family(mol)
    iupac_name = smiles_to_iupac_name(input_smiles)
    molecular_formula = None
    if mol is not None and rdMolDescriptors is not None:
        try:
            molecular_formula = rdMolDescriptors.CalcMolFormula(mol)
        except Exception:
            molecular_formula = None

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
        core_detected=core_detected,
        core_confidence=core_confidence,
        decoration_summary=decoration_summary,
        substituent_count=substituent_count,
        decoration_tokens=decoration_tokens,
        substituent_fragments=substituent_fragments,
        attachment_summary=attachment_summary,
        substitution_pattern=substitution_pattern,
        positional_tokens=positional_tokens,
        molecular_formula=molecular_formula,
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
                substitution_pattern,
                *positional_tokens,
                molecular_formula,
                core_detected,
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
