from __future__ import annotations

import json
from pathlib import Path

from pz_agent.chemistry.vision_client import _build_request_payload, _extract_candidate_text, gemini_vision_available



def test_gemini_vision_available_reports_missing_auth(monkeypatch) -> None:
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    available, reason = gemini_vision_available()
    assert available is False
    assert reason == 'gemini_api_key_missing'



def test_build_request_payload_embeds_inline_image(tmp_path: Path) -> None:
    image_path = tmp_path / 'x.png'
    image_path.write_bytes(b'fakepng')
    payload = _build_request_payload(image_path, 'describe this')
    parts = payload['contents'][0]['parts']
    assert parts[0]['text'].startswith('describe this')
    assert parts[1]['inline_data']['mime_type'] == 'image/png'
    assert isinstance(parts[1]['inline_data']['data'], str)



def test_extract_candidate_text_reads_first_text_part() -> None:
    payload = {
        'candidates': [
            {
                'content': {
                    'parts': [
                        {'text': json.dumps({'ok': True})}
                    ]
                }
            }
        ]
    }
    assert _extract_candidate_text(payload) == '{"ok": true}'
