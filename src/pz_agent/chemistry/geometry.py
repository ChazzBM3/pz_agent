from __future__ import annotations

from dataclasses import dataclass

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    RDKIT_GEOMETRY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency guard
    Chem = None  # type: ignore[assignment]
    AllChem = None  # type: ignore[assignment]
    RDKIT_GEOMETRY_AVAILABLE = False


@dataclass
class XyzGeometry:
    atom_count: int
    xyz_text: str
    embed_method: str
    smiles: str
    canonical_smiles: str | None = None


class GeometryGenerationError(RuntimeError):
    pass


def smiles_to_xyz(smiles: str, *, random_seed: int = 0xF00D, optimize: bool = True) -> XyzGeometry:
    if not smiles:
        raise GeometryGenerationError("SMILES is required for XYZ generation")
    if not RDKIT_GEOMETRY_AVAILABLE or Chem is None or AllChem is None:
        raise GeometryGenerationError("RDKit is not available for SMILES -> XYZ generation")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise GeometryGenerationError(f"Failed to parse SMILES: {smiles}")

    canonical_smiles = Chem.MolToSmiles(mol, canonical=True)
    mol = Chem.AddHs(mol)

    params = AllChem.ETKDGv3()
    params.randomSeed = int(random_seed)
    embed_status = AllChem.EmbedMolecule(mol, params)
    embed_method = "ETKDGv3"
    if embed_status != 0:
        embed_status = AllChem.EmbedMolecule(mol, randomSeed=int(random_seed), useRandomCoords=True)
        embed_method = "distance-geometry-random-coords"
    if embed_status != 0:
        raise GeometryGenerationError(f"RDKit embedding failed for SMILES: {smiles}")

    if optimize:
        try:
            mmff_props = AllChem.MMFFGetMoleculeProperties(mol)
            if mmff_props is not None:
                AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94s")
            else:
                AllChem.UFFOptimizeMolecule(mol)
        except Exception:
            try:
                AllChem.UFFOptimizeMolecule(mol)
            except Exception:
                pass

    conf = mol.GetConformer()
    lines = [str(mol.GetNumAtoms()), canonical_smiles]
    for atom in mol.GetAtoms():
        pos = conf.GetAtomPosition(atom.GetIdx())
        lines.append(f"{atom.GetSymbol()} {pos.x:.8f} {pos.y:.8f} {pos.z:.8f}")

    return XyzGeometry(
        atom_count=mol.GetNumAtoms(),
        xyz_text="\n".join(lines) + "\n",
        embed_method=embed_method,
        smiles=smiles,
        canonical_smiles=canonical_smiles,
    )
