from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique import _infer_evidence_tier
from pz_agent.kg.retrieval import attach_critique_placeholders, synthesize_evidence_from_queries



def test_attach_critique_placeholders_includes_structure_and_retrieval_signals(tmp_path: Path) -> None:
    shortlist = [
        {
            "id": "cand_1",
            "identity": {"name": "cand_1", "scaffold": "phenothiazine"},
            "structure_expansion": {
                "query_smiles": "CC",
                "exact_matches": [{"cid": 1, "title": "Exact A", "pubchem_url": "https://pubchem.ncbi.nlm.nih.gov/compound/1"}],
                "similarity_matches": [{"cid": 2, "title": "Analog B", "pubchem_url": "https://pubchem.ncbi.nlm.nih.gov/compound/2"}],
                "substructure_matches": [],
            },
            "patent_retrieval": {
                "surechembl": [{"query": "foo patent", "hits": [{"title": "Patent hit"}]}],
                "patcid": [],
            },
            "scholarly_retrieval": {
                "openalex": [{"query": "foo chemistry", "hits": [{"title": "Paper hit", "url": "https://doi.org/x", "snippet": "phenothiazine redox"}]}],
            },
        }
    ]
    notes = attach_critique_placeholders(shortlist, enable_web_search=False, max_candidates=5, search_fields=["phenothiazine"], graph_path=None)
    note = notes[0]
    assert note["signals"]["exact_match_hits"] >= 1
    assert note["signals"]["analog_match_hits"] >= 1
    assert note["signals"]["patent_hit_count"] >= 1
    assert note["signals"]["scholarly_hit_count"] >= 1



def test_synthesize_evidence_from_queries_includes_pubchem_and_retrieval_bundles() -> None:
    notes = [
        {
            "candidate_id": "cand_1",
            "web_search_enabled": False,
            "status": "disabled",
            "queries": ["phenothiazine chemistry"],
            "kg_context": {},
            "measurement_context": {},
            "structure_expansion": {
                "query_smiles": "CC",
                "exact_matches": [{"cid": 1, "title": "Exact A", "pubchem_url": "https://pubchem.ncbi.nlm.nih.gov/compound/1", "molecular_formula": "C2H6"}],
                "similarity_matches": [{"cid": 2, "title": "Analog B", "pubchem_url": "https://pubchem.ncbi.nlm.nih.gov/compound/2", "molecular_formula": "C3H8"}],
                "substructure_matches": [],
            },
            "patent_retrieval": {
                "surechembl": [{"query": "foo patent", "hits": [{"title": "Patent hit", "url": "https://patent.example"}]}],
                "patcid": [],
            },
            "scholarly_retrieval": {
                "openalex": [{"query": "foo chemistry", "hits": [{"title": "Paper hit", "url": "https://doi.org/x", "snippet": "phenothiazine redox"}]}],
            },
            "signals": {"exact_match_hits": 1, "analog_match_hits": 1, "patent_hit_count": 1, "scholarly_hit_count": 1},
        }
    ]
    out = synthesize_evidence_from_queries(notes)
    kinds = {item["kind"] for item in out[0]["evidence"]}
    assert "pubchem_exact_match" in kinds
    assert "pubchem_analog_match" in kinds
    assert "patent_result" in kinds
    assert "scholarly_result" in kinds



def test_infer_evidence_tier_supports_patent_tier() -> None:
    assert _infer_evidence_tier({"exact_match_hits": 0, "analog_match_hits": 0, "patent_hit_count": 2, "scholarly_hit_count": 0}) == "patent"
