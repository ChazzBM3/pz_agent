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

    nodes = list(base_graph.get("nodes", []))
    edges = list(base_graph.get("edges", []))
    existing_ids = {node["id"] for node in nodes}

    def add_node(node: dict) -> None:
        if node["id"] not in existing_ids:
            nodes.append(node)
            existing_ids.add(node["id"])

    for note in critique_notes:
        candidate_id = note["candidate_id"]
        claim_id = f"search::{candidate_id}::enriched"
        add_node({
            "id": claim_id,
            "type": "LiteratureClaim",
            "attrs": {
                "candidate_id": candidate_id,
                "status": note.get("status"),
                "summary": note.get("summary"),
                "signals": note.get("signals", {}),
                "search_backend": note.get("search_backend"),
            },
        })
        edges.append({"source": candidate_id, "target": claim_id, "type": "MENTIONED_IN_SEARCH"})

        for q_idx, bundle in enumerate(note.get("live_evidence", [])):
            query_node_id = f"enriched_query::{candidate_id}::{q_idx}"
            add_node({
                "id": query_node_id,
                "type": "LiteraturePaper",
                "attrs": {
                    "query": bundle.get("query"),
                    "candidate_id": candidate_id,
                    "kind": "search_query_bundle",
                },
            })
            edges.append({"source": claim_id, "target": query_node_id, "type": "SUPPORTED_BY"})

            for h_idx, hit in enumerate(bundle.get("hits", [])):
                paper_id = f"paper::{candidate_id}::{q_idx}::{h_idx}"
                evidence_id = f"evidence_hit::{candidate_id}::{q_idx}::{h_idx}"
                add_node({
                    "id": paper_id,
                    "type": "LiteraturePaper",
                    "attrs": {
                        "title": hit.get("title"),
                        "url": hit.get("url"),
                        "snippet": hit.get("snippet"),
                        "source": hit.get("source"),
                    },
                })
                add_node({
                    "id": evidence_id,
                    "type": "EvidenceHit",
                    "attrs": {
                        "query": bundle.get("query"),
                        "candidate_id": candidate_id,
                        "match_type": hit.get("match_type"),
                        "confidence": hit.get("confidence"),
                    },
                })
                edges.append({"source": query_node_id, "target": paper_id, "type": "SUPPORTED_BY"})
                edges.append({"source": claim_id, "target": evidence_id, "type": "HAS_EVIDENCE_HIT"})
                edges.append({"source": evidence_id, "target": paper_id, "type": "SUPPORTED_BY"})
                relation = "EXACT_MATCH_OF" if hit.get("match_type") == "exact" else "ANALOG_OF"
                edges.append({"source": evidence_id, "target": candidate_id, "type": relation})

    enriched_graph = {
        "nodes": nodes,
        "edges": edges,
        "enriched_from": str(critique_path),
        "mode": "normalized_live_evidence",
    }

    enriched_report = dict(base_report)
    enriched_report["summary"] = "Enriched report with normalized live web search evidence"
    enriched_report["critique_notes"] = critique_notes
    enriched_report["knowledge_graph"] = str(knowledge_graph_path)
    enriched_report["enrichment_mode"] = "normalized_live_evidence"

    write_json(knowledge_graph_path, enriched_graph)
    write_json(report_path, enriched_report)
    return knowledge_graph_path, report_path
