from __future__ import annotations

from pathlib import Path

from pz_agent.chemistry.normalize import normalize_molecule_identity
from pz_agent.chemistry.visual_identity import attach_visual_identity
from pz_agent.kg.retrieval import build_candidate_queries



def test_attach_visual_identity_adds_render_bundle(tmp_path: Path) -> None:
    candidate = normalize_molecule_identity({
        'id': '05TRCY',
        'smiles': 'CCN1c2ccccc2Sc2ccc(C(F)(F)F)cc21',
    })
    enriched = attach_visual_identity(candidate, tmp_path)
    bundle = enriched.get('visual_bundle') or {}
    assert bundle.get('vision_status') in {'rendered_ready_for_vision', 'image_unavailable', 'gemini_auth_missing', 'gemini_cli_missing', 'gemini_api_key_missing', 'gemini_http_error', 'gemini_ok'}
    assert 'visual_identity' in bundle
    assert isinstance(bundle['visual_identity'].get('retrieval_phrases'), list)



def test_build_candidate_queries_uses_visual_retrieval_phrases(tmp_path: Path) -> None:
    candidate = normalize_molecule_identity({
        'id': '05BCMO',
        'smiles': 'CCN1c2ccc(C(F)(F)F)cc2Sc2cc(C(F)(F)F)ccc21',
    })
    candidate = attach_visual_identity(candidate, tmp_path)
    queries = build_candidate_queries(candidate)
    joined = ' || '.join(queries)
    assert 'phenothiazine' in joined
    assert any('di substituted' in q or 'CF3' in q or 'position' in q for q in queries)
