from __future__ import annotations

from pathlib import Path
from typing import Any

from pz_agent.chemistry.vision_client import DEFAULT_VISION_MODEL, extract_visual_identity_with_gemini

try:
    from rdkit import Chem
    from rdkit.Chem import Draw
    RDKIT_DRAW_AVAILABLE = True
except Exception:
    Chem = None
    Draw = None
    RDKIT_DRAW_AVAILABLE = False


PHENOTHIAZINE_VISUAL_PROMPT = (
    "You are looking at a 2D skeletal structure of a phenothiazine derivative. "
    "Extract a compact structured description for literature retrieval. "
    "Return JSON with keys: scaffold_confirmed, likely_substituents, likely_ring_positions, "
    "n_substitution, substitution_pattern, retrieval_phrases, confidence, notes."
)



def render_candidate_structure_image(candidate: dict[str, Any], out_dir: str | Path) -> str | None:
    smiles = candidate.get("smiles") or candidate.get("identity", {}).get("canonical_smiles")
    candidate_id = str(candidate.get("id") or "candidate")
    if not RDKIT_DRAW_AVAILABLE or not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    out_path = Path(out_dir) / f"{candidate_id}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    drawer = Draw.MolToImage(mol, size=(600, 400))
    drawer.save(out_path)
    return str(out_path)



def build_visual_identity_stub(candidate: dict[str, Any], image_path: str | None) -> dict[str, Any]:
    identity = candidate.get("identity", {}) or {}
    retrieval_phrases: list[str] = []

    scaffold = identity.get("scaffold") or "phenothiazine"
    decoration_summary = identity.get("decoration_summary")
    positional_tokens = list(identity.get("positional_tokens") or [])
    substitution_pattern = identity.get("substitution_pattern")
    n_substitution = any(token.startswith("alpha ") for token in positional_tokens)

    if decoration_summary and decoration_summary != "none_detected":
        retrieval_phrases.append(f"{scaffold} {decoration_summary.replace('+', ' ')}")
    if positional_tokens:
        retrieval_phrases.append(f"{scaffold} {' '.join(positional_tokens[:3])}")
    if substitution_pattern:
        retrieval_phrases.append(f"{scaffold} {substitution_pattern.replace('_', ' ')}")

    return {
        "image_path": image_path,
        "vision_model": None,
        "vision_status": "rendered_ready_for_vision" if image_path else "image_unavailable",
        "vision_prompt": PHENOTHIAZINE_VISUAL_PROMPT,
        "visual_identity": {
            "scaffold_confirmed": "phenothiaz" in str(scaffold).lower(),
            "likely_substituents": list(identity.get("decoration_tokens") or []),
            "likely_ring_positions": positional_tokens,
            "n_substitution": n_substitution,
            "substitution_pattern": substitution_pattern,
            "retrieval_phrases": retrieval_phrases,
            "confidence": 0.4 if image_path else 0.0,
            "notes": "Stub visual identity derived from RDKit-rendered structure plus normalized identity. Replace with Gemma/Gemini vision extraction when hooked up.",
        },
    }



def maybe_extract_visual_identity(candidate: dict[str, Any], image_path: str | None, model: str = DEFAULT_VISION_MODEL) -> dict[str, Any]:
    stub = build_visual_identity_stub(candidate, image_path)
    if not image_path:
        return stub

    live = extract_visual_identity_with_gemini(image_path=image_path, prompt=PHENOTHIAZINE_VISUAL_PROMPT, model=model)
    if live.get("vision_status") != "gemini_ok" or not isinstance(live.get("visual_identity"), dict):
        stub["vision_model"] = live.get("vision_model")
        stub["vision_status"] = live.get("vision_status")
        stub["vision_raw_output"] = live.get("raw_output")
        return stub

    fused = dict(stub)
    fused["vision_model"] = live.get("vision_model")
    fused["vision_status"] = live.get("vision_status")
    fused["vision_raw_output"] = live.get("raw_output")
    fused["visual_identity"] = live.get("visual_identity")
    return fused



def attach_visual_identity(candidate: dict[str, Any], out_dir: str | Path, model: str = DEFAULT_VISION_MODEL) -> dict[str, Any]:
    enriched = dict(candidate)
    image_path = render_candidate_structure_image(candidate, out_dir)
    enriched["visual_bundle"] = maybe_extract_visual_identity(candidate, image_path, model=model)
    return enriched



def attach_visual_identity_batch(candidates: list[dict[str, Any]], out_dir: str | Path, model: str = DEFAULT_VISION_MODEL) -> list[dict[str, Any]]:
    return [attach_visual_identity(candidate, out_dir, model=model) for candidate in candidates]
