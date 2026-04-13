from __future__ import annotations

from pz_agent.chemistry.normalize import normalize_molecule_identity



def test_normalize_molecule_identity_adds_site_assignments_when_available() -> None:
    record = {"id": "cand_1", "smiles": "CN1c2ccccc2Sc2ccccc21", "name": "test"}
    result = normalize_molecule_identity(record)
    identity = result["identity"]
    assert "attachment_sites" in identity
    assert "site_assignments" in identity
    assert isinstance(identity["attachment_sites"], list)
    assert isinstance(identity["site_assignments"], list)
