from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


CACHE_PATH = Path(__file__).resolve().parents[3] / "artifacts" / "pubchem_name_cache.json"


def _load_cache() -> dict[str, str | None]:
    try:
        return json.loads(CACHE_PATH.read_text())
    except Exception:
        return {}



def _save_cache(cache: dict[str, str | None]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))



def _cache_key(smiles: str) -> str:
    return hashlib.sha1(smiles.encode("utf-8")).hexdigest()



def smiles_to_iupac_name(smiles: str | None, timeout: int = 20, retries: int = 2) -> str | None:
    if not smiles:
        return None
    cache = _load_cache()
    key = _cache_key(smiles)
    if key in cache:
        return cache[key]

    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/"
        f"{quote(smiles, safe='')}/property/IUPACName/JSON"
    )
    result = None
    for _ in range(max(1, retries)):
        try:
            with urlopen(url, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            props = payload.get("PropertyTable", {}).get("Properties", [])
            result = props[0].get("IUPACName") if props else None
            if result:
                break
        except Exception:
            result = None
    cache[key] = result
    _save_cache(cache)
    return result
