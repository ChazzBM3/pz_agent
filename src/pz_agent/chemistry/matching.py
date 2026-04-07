from __future__ import annotations

from typing import Any


def classify_match(candidate: dict[str, Any], evidence_text: str | None) -> str:
    identity = candidate.get("identity", {})
    evidence_text = (evidence_text or "").lower()

    canonical = (identity.get("canonical_smiles") or "").lower()
    name = (identity.get("name") or "").lower()
    scaffold = (identity.get("scaffold") or "").lower()

    if canonical and canonical in evidence_text:
        return "exact"
    if name and name in evidence_text:
        return "exact"
    if scaffold and scaffold in evidence_text:
        return "analog"
    return "family"
