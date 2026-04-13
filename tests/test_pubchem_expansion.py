from __future__ import annotations

from pz_agent.retrieval import pubchem
from pz_agent.retrieval.pubchem import expand_structure_with_pubchem



def test_expand_structure_with_pubchem_aggregates_exact_similarity_and_substructure(monkeypatch) -> None:
    monkeypatch.setattr(pubchem, "fetch_pubchem_exact_matches", lambda smiles, timeout=20: [{"cid": 1, "title": "Exact A"}])
    monkeypatch.setattr(pubchem, "fetch_pubchem_synonyms", lambda cid, timeout=20, limit=10: ["Alpha", "Beta"])
    monkeypatch.setattr(pubchem, "fetch_pubchem_similarity_matches", lambda smiles, threshold=90, max_records=5, timeout=20: [{"cid": 2, "title": "Similar B"}])
    monkeypatch.setattr(pubchem, "fetch_pubchem_substructure_matches", lambda smiles, max_records=5, timeout=20: [{"cid": 3, "title": "Sub C"}])

    candidate = {"id": "cand_1", "smiles": "CCN1c2ccccc2Sc2ccccc21", "identity": {"canonical_smiles": "CCN1c2ccccc2Sc2ccccc21"}}
    result = expand_structure_with_pubchem(candidate)

    assert result["status"] == "ok"
    assert result["exact_matches"][0]["cid"] == 1
    assert result["synonyms"] == ["Alpha", "Beta"]
    assert result["similarity_matches"][0]["cid"] == 2
    assert result["substructure_matches"][0]["cid"] == 3



def test_expand_structure_with_pubchem_handles_missing_smiles() -> None:
    result = expand_structure_with_pubchem({"id": "cand_2", "identity": {}})
    assert result["status"] == "missing_smiles"
    assert result["exact_matches"] == []
    assert result["similarity_matches"] == []
    assert result["substructure_matches"] == []
