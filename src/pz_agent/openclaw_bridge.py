from __future__ import annotations

from pathlib import Path
import hashlib

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


def _paper_key(hit: dict) -> str:
    raw = (hit.get("url") or hit.get("title") or "unknown").strip().lower()
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"paper::{digest}"


def _evidence_relation(hit: dict, note: dict) -> str:
    if hit.get("match_type") == "exact":
        return "EXACT_MATCH_OF"
    if note.get("signals", {}).get("warns_instability"):
        return "CONTRADICTED_BY"
    return "ANALOG_OF"


def rerank_from_enriched_critique(run_dir: str | Path) -> Path:
    run_dir = Path(run_dir)
    report_path = run_dir / "report.json"
    critique_path = run_dir / "critique_notes.enriched.json"
    out_path = run_dir / "report.literature_reranked.json"

    report = read_json(report_path)
    critique_notes = read_json(critique_path)
    note_map = {note["candidate_id"]: note for note in critique_notes}

    reranked = []
    for row in report.get("ranked", []):
        item = dict(row)
        note = note_map.get(item["id"])
        signals = (note or {}).get("signals", {})
        base = item.get("predicted_priority")
        if base is not None:
            bonus = 0.0
            if signals.get("supports_solubility"):
                bonus += 0.05
            if signals.get("supports_synthesizability"):
                bonus += 0.05
            analog_hits = int(signals.get("analog_match_hits", 0) or 0)
            bonus += min(0.05, analog_hits * 0.002)
            if signals.get("warns_instability"):
                bonus -= 0.08
            item["predicted_priority_literature_adjusted"] = float(base) + bonus
            item["literature_adjustment"] = bonus
        reranked.append(item)

    reranked.sort(
        key=lambda x: (
            -1.0 if x.get("predicted_priority_literature_adjusted") is None else -float(x["predicted_priority_literature_adjusted"]),
            x.get("id", ""),
        )
    )

    report["ranked"] = reranked
    report["shortlist"] = reranked[: len(report.get("shortlist", [])) or 3]
    report["enrichment_mode"] = "literature_reranked_from_enriched_critique"
    report["critique_notes"] = critique_notes
    write_json(out_path, report)
    return out_path


def rebuild_graph_and_report_from_enriched(run_dir: str | Path) -> tuple[Path, Path]:
    run_dir = Path(run_dir)
    critique_path = run_dir / "critique_notes.enriched.json"
    knowledge_graph_path = run_dir / "knowledge_graph.enriched.json"
    report_path = run_dir / "report.enriched.json"

    critique_notes = read_json(critique_path)
    base_graph = read_json(run_dir / "knowledge_graph.json")
    base_report = read_json(run_dir / "report.json")
    evidence_report = read_json(run_dir / "evidence_report.json") if (run_dir / "evidence_report.json").exists() else {}

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
                paper_id = _paper_key(hit)
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
                relation = _evidence_relation(hit, note)
                edges.append({"source": evidence_id, "target": candidate_id, "type": relation})

        for plot_path in evidence_report.get("plots", []):
            plot_name = Path(plot_path).name
            media_id = f"media_plot::{candidate_id}::{plot_name}"
            add_node({
                "id": media_id,
                "type": "MediaArtifact",
                "attrs": {
                    "candidate_id": candidate_id,
                    "image_path": plot_path,
                    "media_type": "plot",
                    "caption": f"Generated plot artifact {plot_name} for candidate {candidate_id}",
                    "source_url": None,
                    "provenance": {
                        "source_type": "generated_plot",
                        "confidence": 1.0,
                    },
                },
            })
            edges.append({"source": claim_id, "target": media_id, "type": "HAS_MEDIA_EVIDENCE"})

    enriched_graph = {
        "nodes": nodes,
        "edges": edges,
        "enriched_from": str(critique_path),
        "mode": "normalized_live_evidence",
        "paper_deduplication": "url_or_title_fingerprint",
    }

    enriched_report = dict(base_report)
    enriched_report["summary"] = "Enriched report with normalized live web search evidence"
    enriched_report["critique_notes"] = critique_notes
    enriched_report["knowledge_graph"] = str(knowledge_graph_path)
    enriched_report["enrichment_mode"] = "normalized_live_evidence"
    enriched_report["paper_deduplication"] = "url_or_title_fingerprint"

    write_json(knowledge_graph_path, enriched_graph)
    write_json(report_path, enriched_report)
    return knowledge_graph_path, report_path
