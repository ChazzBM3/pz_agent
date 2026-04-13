from __future__ import annotations

from pz_agent.retrieval import openalex_expanded
from pz_agent.retrieval.openalex_expanded import build_openalex_queries, retrieve_openalex_evidence_for_candidate



def test_build_openalex_queries_uses_structure_and_patent_context() -> None:
    candidate = {
        "identity": {
            "iupac_name": "10-ethyl-2-(trifluoromethyl)phenothiazine",
            "core_assumption": "phenothiazine",
            "substitution_pattern": "mono_substituted",
        },
        "structure_expansion": {"synonyms": ["Syn A"]},
        "patent_retrieval": {"queries": ["\"Syn A\" patent", "\"phenothiazine\" compound patent"]},
    }
    queries = build_openalex_queries(candidate)
    assert any("10-ethyl-2-(trifluoromethyl)phenothiazine" in q for q in queries)
    assert any("Syn A" in q for q in queries)
    assert any("chemistry" in q for q in queries)



def test_retrieve_openalex_evidence_for_candidate_collects_hits(monkeypatch) -> None:
    class _FakeBackend:
        def search(self, query: str, count: int = 5):
            return [type("Hit", (), {"__dict__": {"title": query, "url": "https://example.org", "snippet": "snippet", "source": "openalex", "confidence": None, "match_type": "unknown"}})()]

    monkeypatch.setattr(openalex_expanded, "OpenAlexSearchBackend", lambda: _FakeBackend())

    candidate = {
        "identity": {"iupac_name": "10-ethylphenothiazine", "core_assumption": "phenothiazine"},
        "structure_expansion": {"synonyms": []},
        "patent_retrieval": {"queries": []},
    }
    result = retrieve_openalex_evidence_for_candidate(candidate)
    assert result["status"] == "ok"
    assert result["openalex"][0]["hits"][0]["title"]
