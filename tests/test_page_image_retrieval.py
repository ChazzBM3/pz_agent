from __future__ import annotations

from pathlib import Path

from pz_agent.retrieval.page_image_retrieval import COLPALI_HINT, assemble_page_image_retrieval_for_candidate



def test_assemble_page_image_retrieval_for_candidate_builds_targets(tmp_path: Path) -> None:
    candidate = {
        "id": "cand_1",
        "smiles": "CCN1c2ccccc2Sc2ccccc21",
        "figure_corpus": {
            "figures": [
                {
                    "figure_id": "figure::cand_1::abc",
                    "storage_ref": str(tmp_path / "fig1.png"),
                    "source_document_path": str(tmp_path / "doc1.pdf"),
                    "caption": None,
                }
            ]
        },
    }
    result = assemble_page_image_retrieval_for_candidate(candidate, tmp_path)
    assert result["status"] == "ok"
    assert result["target_count"] == 1
    assert result["targets"][0]["status"] == COLPALI_HINT



def test_assemble_page_image_retrieval_for_candidate_handles_empty_figures(tmp_path: Path) -> None:
    candidate = {"id": "cand_2", "smiles": "CC", "figure_corpus": {"figures": []}}
    result = assemble_page_image_retrieval_for_candidate(candidate, tmp_path)
    assert result["status"] == "empty"
    assert result["target_count"] == 0
