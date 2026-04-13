from __future__ import annotations

from pz_agent.retrieval.multimodal_rerank import assemble_multimodal_rerank_for_candidate



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
                }
            ]
        },
    }
    result = assemble_multimodal_rerank_for_candidate(candidate)
    assert result["status"] == "ok"
    assert result["bundle_count"] == 1
    assert result["bundles"][0]["backend"] == "gemma_planned"
    assert result["bundles"][0]["candidate_identity"]["scaffold"] == "phenothiazine"



def test_assemble_multimodal_rerank_for_candidate_handles_empty_targets() -> None:
    candidate = {"id": "cand_2", "page_image_retrieval": {"targets": []}, "document_fetch": {"documents": []}, "identity": {}}
    result = assemble_multimodal_rerank_for_candidate(candidate)
    assert result["status"] == "empty"
    assert result["bundle_count"] == 0
