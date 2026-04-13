from __future__ import annotations

from pathlib import Path

from pz_agent.retrieval.page_image_retrieval import COLPALI_HINT, assemble_page_image_retrieval_for_candidate



def test_assemble_page_image_retrieval_for_candidate_builds_targets(tmp_path: Path) -> None:
    fig_path = tmp_path / "fig1.png"
    fig_path.write_bytes(b"phenothiazine-figure")
    candidate = {
        "id": "cand_1",
        "smiles": "CCN1c2ccccc2Sc2ccccc21",
        "figure_corpus": {
            "figures": [
                {
                    "figure_id": "figure::cand_1::abc",
                    "storage_ref": str(fig_path),
                    "source_document_path": str(tmp_path / "doc1.pdf"),
                    "caption": "Figure 1. Phenothiazine redox",
                    "ocr_text": "compound phenothiazine",
                }
            ]
        },
    }
    result = assemble_page_image_retrieval_for_candidate(candidate, tmp_path)
    assert result["status"] == "ok"
    assert result["target_count"] == 1
    assert result["targets"][0]["status"] == COLPALI_HINT
    assert result["targets"][0]["score"] > 0.1



def test_assemble_page_image_retrieval_for_candidate_handles_empty_figures(tmp_path: Path) -> None:
    candidate = {"id": "cand_2", "smiles": "CC", "figure_corpus": {"figures": []}}
    result = assemble_page_image_retrieval_for_candidate(candidate, tmp_path)
    assert result["status"] == "empty"
    assert result["target_count"] == 0
