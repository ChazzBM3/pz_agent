from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class MoleculeIdentity:
    input_smiles: str | None = None
    canonical_smiles: str | None = None
    inchi: str | None = None
    inchikey: str | None = None
    scaffold: str | None = None
    name: str | None = None
    source_name: str | None = None
    iupac_name: str | None = None
    core_assumption: str | None = None
    decoration_summary: str | None = None
    substituent_count: int | None = None
    decoration_tokens: list[str] | None = None
    substituent_fragments: list[str] | None = None
    attachment_summary: list[str] | None = None
    substitution_pattern: str | None = None
    positional_tokens: list[str] | None = None
    molecular_formula: str | None = None
    electronic_bias: str | None = None
    match_tokens: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
