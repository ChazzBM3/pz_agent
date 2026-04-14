from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_VISION_MODEL = "gemini-2.5-flash"
DEFAULT_VISION_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"



def _api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY")



def gemini_vision_available() -> tuple[bool, str | None]:
    if _api_key():
        return True, None
    return False, "gemini_api_key_missing"



def _guess_mime_type(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"



def _build_request_payload(image_path: str | Path, prompt: str) -> dict[str, Any]:
    image_bytes = Path(image_path).read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return {
        "contents": [
            {
                "parts": [
                    {"text": prompt + "\n\nRespond with JSON only, no markdown fences."},
                    {
                        "inline_data": {
                            "mime_type": _guess_mime_type(image_path),
                            "data": encoded,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }



def _extract_candidate_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                return text.strip()
    return None



def extract_visual_identity_with_gemini(
    image_path: str | Path,
    prompt: str,
    model: str = DEFAULT_VISION_MODEL,
    timeout: int = 120,
) -> dict[str, Any]:
    available, reason = gemini_vision_available()
    if not available:
        return {
            "vision_status": reason,
            "vision_model": model,
            "visual_identity": None,
            "raw_output": None,
        }

    api_key = _api_key()
    assert api_key is not None
    url = f"{DEFAULT_VISION_API_BASE}/{model}:generateContent?key={api_key}"
    body = json.dumps(_build_request_payload(image_path=image_path, prompt=prompt)).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urlopen(request, timeout=timeout) as response:
            raw_text = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore") if hasattr(exc, "read") else str(exc)
        return {
            "vision_status": "gemini_http_error",
            "vision_model": model,
            "visual_identity": None,
            "raw_output": detail,
        }
    except URLError as exc:
        return {
            "vision_status": "gemini_network_error",
            "vision_model": model,
            "visual_identity": None,
            "raw_output": str(exc),
        }
    except Exception as exc:
        return {
            "vision_status": "gemini_call_failed",
            "vision_model": model,
            "visual_identity": None,
            "raw_output": str(exc),
        }

    try:
        parsed_payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "vision_status": "gemini_non_json_output",
            "vision_model": model,
            "visual_identity": None,
            "raw_output": raw_text,
        }

    response_text = _extract_candidate_text(parsed_payload)
    if not response_text:
        return {
            "vision_status": "gemini_empty_response",
            "vision_model": model,
            "visual_identity": None,
            "raw_output": raw_text,
        }

    try:
        visual_identity = json.loads(response_text)
    except json.JSONDecodeError:
        return {
            "vision_status": "gemini_wrapped_non_json",
            "vision_model": model,
            "visual_identity": None,
            "raw_output": response_text,
        }

    return {
        "vision_status": "gemini_ok",
        "vision_model": model,
        "visual_identity": visual_identity,
        "raw_output": raw_text,
    }
