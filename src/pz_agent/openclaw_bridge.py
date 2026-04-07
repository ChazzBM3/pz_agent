from __future__ import annotations

from pathlib import Path

from pz_agent.io import read_json, write_json


def normalize_openclaw_search_results(candidate_id: str, query: str, results: list[dict]) -> dict:
    hits = []
    for item in results:
        hits.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("snippet"),
                "source": "openclaw_web_search",
                "match_type": item.get("match_type", "unknown"),
                "confidence": item.get("confidence"),
            }
        )
    return {
        "candidate_id": candidate_id,
        "query": query,
        "hits": hits,
    }


def merge_live_search_results(run_dir: str | Path, live_results: list[dict]) -> Path:
    run_dir = Path(run_dir)
    critique_path = run_dir / "critique_notes.json"
    critique_notes = read_json(critique_path)

    grouped: dict[tuple[str, str], dict] = {}
    for bundle in live_results:
        grouped[(bundle["candidate_id"], bundle["query"])] = bundle

    for note in critique_notes:
        note["search_backend"] = "openclaw_web_search"
        note["live_evidence"] = []
        for query in note.get("queries", []):
            bundle = grouped.get((note["candidate_id"], query))
            if bundle:
                note["live_evidence"].append(bundle)
        if note.get("live_evidence"):
            note["status"] = "search_enriched"
            note["signals"]["exact_match_hits"] = sum(
                1
                for bundle in note["live_evidence"]
                for hit in bundle["hits"]
                if hit.get("match_type") == "exact"
            )
            note["signals"]["analog_match_hits"] = sum(
                1
                for bundle in note["live_evidence"]
                for hit in bundle["hits"]
                if hit.get("match_type") == "analog"
            )

    out_path = run_dir / "critique_notes.enriched.json"
    write_json(out_path, critique_notes)
    return out_path


def rebuild_graph_and_report_from_enriched(run_dir: str | Path) -> tuple[Path, Path]:
    run_dir = Path(run_dir)
    critique_path = run_dir / "critique_notes.enriched.json"
    knowledge_graph_path = run_dir / "knowledge_graph.enriched.json"
    report_path = run_dir / "report.enriched.json"

    critique_notes = read_json(critique_path)
    base_graph = read_json(run_dir / "knowledge_graph.json")
    base_report = read_json(run_dir / "report.json")

    enriched_graph = dict(base_graph)
    enriched_graph["enriched_from"] = str(critique_path)
    enriched_graph["critique_notes"] = critique_notes

    enriched_report = dict(base_report)
    enriched_report["summary"] = "Enriched report with live web search evidence"
    enriched_report["critique_notes"] = critique_notes
    enriched_report["knowledge_graph"] = str(knowledge_graph_path)

    write_json(knowledge_graph_path, enriched_graph)
    write_json(report_path, enriched_report)
    return knowledge_graph_path, report_path
