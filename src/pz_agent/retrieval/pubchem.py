from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen


PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


@dataclass
class PubChemRecord:
    cid: int
    title: str | None
    molecular_formula: str | None
    canonical_smiles: str | None
    isomeric_smiles: str | None
    inchi: str | None
    inchikey: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cid": self.cid,
            "title": self.title,
            "molecular_formula": self.molecular_formula,
            "canonical_smiles": self.canonical_smiles,
            "isomeric_smiles": self.isomeric_smiles,
            "inchi": self.inchi,
            "inchikey": self.inchikey,
            "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{self.cid}",
        }


@dataclass
class StructureExpansionResult:
    query_smiles: str | None
    synonyms: list[str]
    exact_matches: list[dict[str, Any]]
    similarity_matches: list[dict[str, Any]]
    substructure_matches: list[dict[str, Any]]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_smiles": self.query_smiles,
            "synonyms": self.synonyms,
            "exact_matches": self.exact_matches,
            "similarity_matches": self.similarity_matches,
            "substructure_matches": self.substructure_matches,
            "status": self.status,
        }


def _fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _record_from_property_row(row: dict[str, Any]) -> PubChemRecord:
    return PubChemRecord(
        cid=int(row.get("CID")),
        title=row.get("Title"),
        molecular_formula=row.get("MolecularFormula"),
        canonical_smiles=row.get("CanonicalSMILES"),
        isomeric_smiles=row.get("IsomericSMILES"),
        inchi=row.get("InChI"),
        inchikey=row.get("InChIKey"),
    )


def _fetch_properties_for_cids(cids: list[int], timeout: int = 20) -> list[dict[str, Any]]:
    if not cids:
        return []
    joined = ",".join(str(cid) for cid in cids)
    url = (
        f"{PUBCHEM_BASE}/compound/cid/{joined}/property/"
        "Title,MolecularFormula,CanonicalSMILES,IsomericSMILES,InChI,InChIKey/JSON"
    )
    payload = _fetch_json(url, timeout=timeout)
    rows = payload.get("PropertyTable", {}).get("Properties", [])
    return [_record_from_property_row(row).to_dict() for row in rows]


def fetch_pubchem_synonyms(cid: int, timeout: int = 20, limit: int = 10) -> list[str]:
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON"
    payload = _fetch_json(url, timeout=timeout)
    info = payload.get("InformationList", {}).get("Information", [])
    if not info:
        return []
    synonyms = list(info[0].get("Synonym", []) or [])
    deduped: list[str] = []
    seen: set[str] = set()
    for synonym in synonyms:
        text = str(synonym).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        deduped.append(text)
        if len(deduped) >= limit:
            break
    return deduped


def _fetch_cids_for_smiles(smiles: str, namespace: str, timeout: int = 20) -> list[int]:
    encoded = quote(smiles, safe="")
    url = f"{PUBCHEM_BASE}/compound/{namespace}/smiles/{encoded}/cids/JSON"
    payload = _fetch_json(url, timeout=timeout)
    return [int(cid) for cid in payload.get("IdentifierList", {}).get("CID", [])]


def fetch_pubchem_exact_matches(smiles: str, timeout: int = 20) -> list[dict[str, Any]]:
    return _fetch_properties_for_cids(_fetch_cids_for_smiles(smiles, namespace="fastidentity", timeout=timeout), timeout=timeout)


def fetch_pubchem_similarity_matches(smiles: str, threshold: int = 90, max_records: int = 5, timeout: int = 20) -> list[dict[str, Any]]:
    encoded = quote(smiles, safe="")
    url = (
        f"{PUBCHEM_BASE}/compound/fastsimilarity_2d/smiles/{encoded}/cids/JSON?"
        f"Threshold={int(threshold)}&MaxRecords={int(max_records)}"
    )
    payload = _fetch_json(url, timeout=timeout)
    cids = [int(cid) for cid in payload.get("IdentifierList", {}).get("CID", [])]
    return _fetch_properties_for_cids(cids, timeout=timeout)


def fetch_pubchem_substructure_matches(smiles: str, max_records: int = 5, timeout: int = 20) -> list[dict[str, Any]]:
    encoded = quote(smiles, safe="")
    url = f"{PUBCHEM_BASE}/compound/fastsubstructure/smiles/{encoded}/cids/JSON?MaxRecords={int(max_records)}"
    payload = _fetch_json(url, timeout=timeout)
    cids = [int(cid) for cid in payload.get("IdentifierList", {}).get("CID", [])]
    return _fetch_properties_for_cids(cids, timeout=timeout)


def expand_structure_with_pubchem(
    candidate: dict[str, Any],
    similarity_threshold: int = 90,
    similarity_max_records: int = 5,
    substructure_max_records: int = 5,
    timeout: int = 20,
) -> dict[str, Any]:
    identity = candidate.get("identity", {}) or {}
    smiles = candidate.get("smiles") or identity.get("canonical_smiles")
    if not smiles:
        return StructureExpansionResult(
            query_smiles=None,
            synonyms=[],
            exact_matches=[],
            similarity_matches=[],
            substructure_matches=[],
            status="missing_smiles",
        ).to_dict()

    exact_matches = fetch_pubchem_exact_matches(smiles, timeout=timeout)
    synonyms: list[str] = []
    if exact_matches:
        first_cid = exact_matches[0].get("cid")
        if isinstance(first_cid, int):
            try:
                synonyms = fetch_pubchem_synonyms(first_cid, timeout=timeout)
            except Exception:
                synonyms = []

    try:
        similarity_matches = fetch_pubchem_similarity_matches(
            smiles,
            threshold=similarity_threshold,
            max_records=similarity_max_records,
            timeout=timeout,
        )
    except Exception:
        similarity_matches = []

    try:
        substructure_matches = fetch_pubchem_substructure_matches(
            smiles,
            max_records=substructure_max_records,
            timeout=timeout,
        )
    except Exception:
        substructure_matches = []

    return StructureExpansionResult(
        query_smiles=smiles,
        synonyms=synonyms,
        exact_matches=exact_matches,
        similarity_matches=similarity_matches,
        substructure_matches=substructure_matches,
        status="ok",
    ).to_dict()
