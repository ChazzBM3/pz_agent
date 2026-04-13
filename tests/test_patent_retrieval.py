from __future__ import annotations

from pz_agent.retrieval import patents
from pz_agent.retrieval.patents import build_patent_queries, retrieve_patent_evidence_for_candidate



def test_build_patent_queries_uses_iupac_synonyms_and_formula() -> None:
    candidate = {
        "identity": {
            "iupac_name": "10-ethyl-2-(trifluoromethyl)phenothiazine",
            "core_assumption": "phenothiazine",
            "substitution_pattern": "mono_substituted",
            "molecular_formula": "C15H12F3NS",
        },
        "structure_expansion": {
            "synonyms": ["Phenothiazine, 10-ethyl-2-(trifluoromethyl)-"],
            "exact_matches": [{"title": "Triflupromazine analog"}],
        },
    }
    queries = build_patent_queries(candidate)
    assert any("10-ethyl-2-(trifluoromethyl)phenothiazine" in q for q in queries)
    assert any("Phenothiazine, 10-ethyl-2-(trifluoromethyl)-" in q for q in queries)
    assert any("C15H12F3NS" in q for q in queries)



def test_retrieve_patent_evidence_for_candidate_collects_adapter_results(monkeypatch) -> None:
    monkeypatch.setattr(patents, "fetch_surechembl_hits", lambda query, count=5, timeout=20: [{"doc_id": "SC1", "title": query}])
    monkeypatch.setattr(patents, "fetch_patcid_hits", lambda query, count=5, timeout=20: [{"patent_id": "PC1", "title": query}])

    candidate = {
        "identity": {"iupac_name": "10-ethylphenothiazine", "core_assumption": "phenothiazine"},
        "structure_expansion": {"synonyms": [], "exact_matches": []},
    }
    result = retrieve_patent_evidence_for_candidate(candidate)
    assert result["status"] == "ok"
    assert result["surechembl"][0]["hits"][0]["doc_id"] == "SC1"
    assert result["patcid"][0]["hits"][0]["patent_id"] == "PC1"
