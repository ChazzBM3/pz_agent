from __future__ import annotations

from pz_agent.kg.identity_spine import (
    build_attachment_site_node,
    build_compound_node,
    build_scaffold_node,
    build_substituent_node,
)



def test_identity_spine_builders_emit_canonical_node_shapes() -> None:
    candidate = {
        "id": "cand_1",
        "smiles": "CC",
        "identity": {"canonical_smiles": "CC", "inchikey": "TESTKEY", "scaffold": "phenothiazine", "molecular_formula": "C2H6"},
    }
    assignment = {"site": "ring_3", "role_label": "position 3 OMe", "substituent_class": "OMe"}
    assert build_compound_node(candidate)["type"] == "Compound"
    assert build_scaffold_node(candidate["identity"])["type"] == "Scaffold"
    assert build_attachment_site_node(candidate["identity"], assignment)["type"] == "AttachmentSite"
    assert build_substituent_node(candidate["id"], assignment)["type"] == "Substituent"
