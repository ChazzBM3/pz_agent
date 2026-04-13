from __future__ import annotations

from typing import Any

from pz_agent.kg.claims import stable_node_id



def compound_id_from_candidate(candidate: dict[str, Any]) -> str:
    identity = candidate.get("identity") or {}
    return str(identity.get("inchikey") or stable_node_id("compound", identity.get("canonical_smiles") or candidate.get("smiles") or candidate.get("id")))



def scaffold_id_from_identity(identity: dict[str, Any]) -> str:
    scaffold = identity.get("scaffold") or "phenothiazine"
    return stable_node_id("scaffold", scaffold)



def substituent_id_from_assignment(candidate_id: str, assignment: dict[str, Any]) -> str:
    return stable_node_id("substituent", candidate_id, str(assignment.get("substituent_class") or "unknown"))



def site_id_from_assignment(identity: dict[str, Any], assignment: dict[str, Any]) -> str:
    return stable_node_id("site", scaffold_id_from_identity(identity), str(assignment.get("site") or "unknown"))



def build_compound_node(candidate: dict[str, Any]) -> dict[str, Any]:
    identity = candidate.get("identity") or {}
    return {
        "id": f"identity::compound::{compound_id_from_candidate(candidate)}",
        "type": "Compound",
        "attrs": {
            "compound_id": compound_id_from_candidate(candidate),
            "canonical_smiles": identity.get("canonical_smiles") or candidate.get("smiles"),
            "inchi": identity.get("inchi"),
            "inchi_key": identity.get("inchikey"),
            "formula": identity.get("molecular_formula"),
            "family": "phenothiazine",
            "is_generated": True,
            "is_known": False,
        },
    }



def build_scaffold_node(identity: dict[str, Any]) -> dict[str, Any]:
    scaffold_name = identity.get("scaffold") or "phenothiazine"
    return {
        "id": f"identity::scaffold::{scaffold_id_from_identity(identity)}",
        "type": "Scaffold",
        "attrs": {
            "scaffold_id": scaffold_id_from_identity(identity),
            "family": "phenothiazine",
            "scaffold_name": scaffold_name,
            "scaffold_smarts": scaffold_name,
        },
    }



def build_attachment_site_node(identity: dict[str, Any], assignment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"identity::site::{site_id_from_assignment(identity, assignment)}",
        "type": "AttachmentSite",
        "attrs": {
            "site_id": site_id_from_assignment(identity, assignment),
            "scaffold_id": scaffold_id_from_identity(identity),
            "site_label": assignment.get("site"),
            "site_type": assignment.get("role_label"),
            "symmetry_class": None,
            "is_equivalent_group": False,
        },
    }



def build_substituent_node(candidate_id: str, assignment: dict[str, Any]) -> dict[str, Any]:
    substituent_id = substituent_id_from_assignment(candidate_id, assignment)
    return {
        "id": f"identity::substituent::{substituent_id}",
        "type": "Substituent",
        "attrs": {
            "substituent_id": substituent_id,
            "canonical_smiles": None,
            "class_tags": [assignment.get("substituent_class")],
            "charge_bearing": False,
        },
    }
