from __future__ import annotations

from pz_agent.retrieval.page_corpus import assemble_page_corpus_for_candidate



def test_assemble_page_corpus_collects_structure_patent_and_scholarly_pages() -> None:
    candidate = {
        "id": "cand_1",
        "structure_expansion": {
            "query_smiles": "CC",
            "exact_matches": [{"cid": 1, "title": "Exact A", "pubchem_url": "https://pubchem.ncbi.nlm.nih.gov/compound/1"}],
            "similarity_matches": [{"cid": 2, "title": "Analog B", "pubchem_url": "https://pubchem.ncbi.nlm.nih.gov/compound/2"}],
            "substructure_matches": [],
        },
        "patent_retrieval": {
            "surechembl": [{"query": "foo patent", "hits": [{"title": "Patent hit", "url": "https://patents.example/doc1", "snippet": "patent text"}]}],
            "patcid": [],
        },
        "scholarly_retrieval": {
            "openalex": [{"query": "foo chemistry", "hits": [{"title": "Paper hit", "url": "https://doi.org/10.1000/example", "snippet": "phenothiazine redox"}]}],
        },
    }
    result = assemble_page_corpus_for_candidate(candidate)
    assert result["status"] == "ok"
    assert result["page_count"] == 4
    kinds = {page["evidence_kind"] for page in result["pages"]}
    assert "exact_structure_page" in kinds
    assert "analog_structure_page" in kinds
    assert "patent_page" in kinds
    assert "scholarly_page" in kinds



def test_assemble_page_corpus_deduplicates_by_url() -> None:
    candidate = {
        "id": "cand_2",
        "structure_expansion": {"exact_matches": [], "similarity_matches": [], "substructure_matches": []},
        "patent_retrieval": {"surechembl": [], "patcid": []},
        "scholarly_retrieval": {
            "openalex": [
                {"query": "q1", "hits": [{"title": "Paper", "url": "https://doi.org/10.1/x", "snippet": "a"}]},
                {"query": "q2", "hits": [{"title": "Paper", "url": "https://doi.org/10.1/x", "snippet": "b"}]},
            ],
        },
    }
    result = assemble_page_corpus_for_candidate(candidate)
    assert result["page_count"] == 1
