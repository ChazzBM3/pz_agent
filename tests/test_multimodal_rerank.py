from __future__ import annotations

from pz_agent.retrieval.multimodal_rerank import (
    assemble_multimodal_rerank_for_candidate,
    build_gemma_multimodal_prompt,
    invoke_gemma_multimodal,
    parse_gemma_multimodal_response,
)



def test_assemble_multimodal_rerank_for_candidate_builds_bundles() -> None:
    candidate = {
        "id": "cand_1",
        "identity": {
            "iupac_name": "10-ethylphenothiazine",
            "scaffold": "phenothiazine",
            "substitution_pattern": "mono_substituted",
            "molecular_formula": "C14H13NS",
        },
        "document_fetch": {
            "documents": [
                {
                    "local_artifact_path": "artifacts/page_assets/cand_1/doc1.html",
                    "metadata_path": "artifacts/page_assets/cand_1/doc1.json",
                    "url": "https://doi.org/10.1000/example",
                    "snippet": "phenothiazine redox",
                    "title": "Paper",
                }
            ]
        },
        "page_image_retrieval": {
            "targets": [
                {
                    "figure_id": "figure::cand_1::abc",
                    "query_image_path": "artifacts/page_image_retrieval/cand_1/queries/cand_1.png",
                    "target_image_path": "artifacts/figure_assets/cand_1/fig1.png",
                    "source_document_path": "artifacts/page_assets/cand_1/doc1.html",
                    "caption": None,
                    "ocr_text": "compound 5 phenothiazine",
                    "score": 0.8,
                }
            ]
        },
    }
    result = assemble_multimodal_rerank_for_candidate(candidate, invoke_live=False)
    assert result["status"] == "ok"
    assert result["bundle_count"] == 1
    assert result["bundles"][0]["backend"] == "gemma_planned"
    assert result["bundles"][0]["candidate_identity"]["scaffold"] == "phenothiazine"
    assert "gemma_prompt" in result["bundles"][0]



def test_build_gemma_multimodal_prompt_contains_candidate_and_artifact_context() -> None:
    bundle = {
        "candidate_id": "cand_1",
        "query_image_path": "q.png",
        "target_image_path": "t.png",
        "caption": "Figure 2",
        "ocr_text": "compound 5",
        "title": "Paper",
        "snippet": "phenothiazine redox",
        "source_url": "https://doi.org/x",
        "retrieval_score": 0.7,
        "candidate_identity": {"iupac_name": "10-ethylphenothiazine", "scaffold": "phenothiazine"},
    }
    prompt = build_gemma_multimodal_prompt(bundle)
    assert "cand_1" in prompt
    assert "q.png" in prompt
    assert "compound 5" in prompt
    assert "0.7" in prompt



def test_parse_gemma_multimodal_response_handles_json_and_fallback() -> None:
    parsed = parse_gemma_multimodal_response('{"match_label":"analog","property_relevance":"redox","confidence":"medium","justification":"Looks related","needs_human_review":false}')
    assert parsed["status"] == "ok"
    assert parsed["match_label"] == "analog"

    fallback = parse_gemma_multimodal_response('not json')
    assert fallback["status"] == "parse_failed"
    assert fallback["needs_human_review"] is True



def test_invoke_gemma_multimodal_falls_back_when_backend_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("pz_agent.retrieval.multimodal_rerank.gemini_vision_available", lambda: (False, "gemini_api_key_missing"))
    bundle = {"retrieval_score": 0.8, "caption": "Phenothiazine figure", "ocr_text": "redox", "query_image_path": "q.png", "target_image_path": "t.png"}
    result = invoke_gemma_multimodal(bundle)
    assert result["backend"] == "fallback"
    assert result["gemma_judgment"]["status"] == "fallback"



def test_assemble_multimodal_rerank_for_candidate_handles_empty_targets() -> None:
    candidate = {"id": "cand_2", "page_image_retrieval": {"targets": []}, "document_fetch": {"documents": []}, "identity": {}}
    result = assemble_multimodal_rerank_for_candidate(candidate, invoke_live=False)
    assert result["status"] == "empty"
    assert result["bundle_count"] == 0
