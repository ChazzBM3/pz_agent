from __future__ import annotations

from pz_agent.chemistry.normalize import normalize_molecule_identity


def test_normalize_molecule_identity_adds_stable_identity_key() -> None:
    record = {"id": "cand_1", "smiles": "CCO", "name": "ethanol"}

    enriched = normalize_molecule_identity(record)

    assert enriched.get("stable_identity_key") is not None
    assert enriched["identity"].get("stable_identity_key") == enriched.get("stable_identity_key")
