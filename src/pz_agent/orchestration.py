from __future__ import annotations

from pathlib import Path

from pz_agent.config import load_config
from pz_agent.io import ensure_dir, read_json, write_json
from pz_agent.search.backends import get_search_backend


def enrich_critique_with_search(run_dir: str | Path, config_path: str | Path) -> Path:
    run_dir = Path(run_dir)
    ensure_dir(run_dir)
    config = load_config(config_path)

    critique_path = run_dir / "critique_notes.json"
    if not critique_path.exists():
        raise FileNotFoundError(f"Missing critique notes: {critique_path}")

    critique_notes = read_json(critique_path)
    backend_name = config.get("search", {}).get("backend", "stub")
    hit_count = int(config.get("search", {}).get("count", 5))
    backend = get_search_backend(backend_name)

    for note in critique_notes:
        note["search_backend"] = backend.name
        note["live_evidence"] = []
        for query in note.get("queries", []):
            try:
                hits = backend.search(query, count=hit_count)
            except NotImplementedError as exc:
                note.setdefault("errors", []).append(str(exc))
                continue
            note["live_evidence"].append(
                {
                    "query": query,
                    "hits": [hit.__dict__ for hit in hits],
                }
            )
        if note.get("live_evidence"):
            note["status"] = "search_enriched"
            note["signals"]["exact_match_hits"] = 0
            note["signals"]["analog_match_hits"] = sum(len(bundle["hits"]) for bundle in note["live_evidence"])

    output_path = run_dir / "critique_notes.enriched.json"
    write_json(output_path, critique_notes)
    return output_path
