from __future__ import annotations

from pathlib import Path
from typing import Any

from pz_agent.io import read_json
from pz_agent.kg.schema_v2 import RetrievalQuery, RetrievedContext


def _load_graph(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return read_json(path)


def _index_graph(graph: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.get("edges", []):
        adjacency.setdefault(edge["source"], []).append(edge)
        adjacency.setdefault(edge["target"], []).append(edge)
    return nodes, adjacency


def get_candidate_neighborhood(graph: dict[str, Any], candidate_id: str, hop_limit: int = 2) -> dict[str, Any]:
    nodes, adjacency = _index_graph(graph)
    visited = {candidate_id}
    frontier = {candidate_id}
    collected_edges: list[dict[str, Any]] = []

    for _ in range(max(hop_limit, 0)):
        next_frontier: set[str] = set()
        for node_id in frontier:
            for edge in adjacency.get(node_id, []):
                collected_edges.append(edge)
                neighbor = edge["target"] if edge["source"] == node_id else edge["source"]
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
        frontier = next_frontier
        if not frontier:
            break

    neighborhood_nodes = [nodes[node_id] for node_id in visited if node_id in nodes]
    unique_edges = []
    seen_edges = set()
    for edge in collected_edges:
        key = (edge.get("source"), edge.get("target"), edge.get("type"))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        unique_edges.append(edge)

    return {
        "nodes": neighborhood_nodes,
        "edges": unique_edges,
    }


def get_claims_for_molecule(graph_path: Path | None, candidate_id: str, hop_limit: int = 2) -> list[dict[str, Any]]:
    graph = _load_graph(graph_path)
    if graph is None:
        return []
    neighborhood = get_candidate_neighborhood(graph, candidate_id, hop_limit=hop_limit)
    claims = []
    for node in neighborhood.get("nodes", []):
        if node.get("type") in {"Claim", "LiteratureClaim"}:
            claims.append(node)
    claims.sort(key=lambda x: x.get("id", ""))
    return claims



def get_evidence_hits_for_candidate(graph_path: Path | None, candidate_id: str, hop_limit: int = 2) -> list[dict[str, Any]]:
    graph = _load_graph(graph_path)
    if graph is None:
        return []
    neighborhood = get_candidate_neighborhood(graph, candidate_id, hop_limit=hop_limit)
    hits = []
    exact_hit_ids: set[str] = set()
    analog_hit_ids: set[str] = set()

    for edge in neighborhood.get("edges", []):
        if edge.get("target") != candidate_id:
            continue
        source = edge.get("source")
        if not source:
            continue
        if edge.get("type") == "EXACT_MATCH_OF":
            exact_hit_ids.add(source)
        elif edge.get("type") in {"ANALOG_OF", "SIMILAR_TO"}:
            analog_hit_ids.add(source)

    for node in neighborhood.get("nodes", []):
        if node.get("type") != "EvidenceHit":
            continue
        item = dict(node)
        attrs = dict(item.get("attrs", {}))
        node_id = item.get("id")
        if node_id in exact_hit_ids:
            attrs["match_type"] = attrs.get("match_type") or "exact"
        elif node_id in analog_hit_ids:
            attrs["match_type"] = attrs.get("match_type") or "analog"
        item["attrs"] = attrs
        hits.append(item)
    hits.sort(key=lambda x: x.get("id", ""))
    return hits



def get_measurements_for_molecule(graph_path: Path | None, candidate_id: str, hop_limit: int = 2) -> list[dict[str, Any]]:
    graph = _load_graph(graph_path)
    if graph is None:
        return []
    neighborhood = get_candidate_neighborhood(graph, candidate_id, hop_limit=hop_limit)
    measurements = []
    for node in neighborhood.get("nodes", []):
        if node.get("type") == "Measurement":
            measurements.append(node)
    measurements.sort(key=lambda x: x.get("id", ""))
    return measurements



def get_measurements_for_property(graph_path: Path | None, property_name: str) -> list[dict[str, Any]]:
    graph = _load_graph(graph_path)
    if graph is None:
        return []
    target_property_id = f"property::{property_name}"
    nodes, adjacency = _index_graph(graph)
    measurements = []
    for edge in graph.get("edges", []):
        if edge.get("type") == "HAS_PROPERTY" and edge.get("target") == target_property_id:
            measurement_id = edge.get("source")
            node = nodes.get(measurement_id)
            if node and node.get("type") == "Measurement":
                measurements.append(node)
    measurements.sort(key=lambda x: x.get("id", ""))
    return measurements



def summarize_property_coverage(graph_path: Path | None, candidate_id: str) -> dict[str, Any]:
    measurements = get_measurements_for_molecule(graph_path, candidate_id)
    property_names: list[str] = []
    populated_measurements = []
    for node in measurements:
        attrs = node.get("attrs", {})
        property_name = attrs.get("property_name")
        if property_name:
            property_names.append(property_name)
        if attrs.get("value") is not None:
            populated_measurements.append(
                {
                    "property_name": property_name,
                    "value": attrs.get("value"),
                }
            )
    unique_properties = sorted(set(property_names))
    return {
        "candidate_id": candidate_id,
        "measurement_count": len(measurements),
        "property_count": len(unique_properties),
        "properties": unique_properties,
        "populated_measurements": populated_measurements,
    }



def get_measurement_for_molecule_property(
    graph_path: Path | None,
    candidate_id: str,
    property_name: str,
) -> dict[str, Any] | None:
    measurements = get_measurements_for_molecule(graph_path, candidate_id)
    for node in measurements:
        attrs = node.get("attrs", {})
        if attrs.get("property_name") == property_name:
            return node
    return None



def summarize_candidate_property_value(
    graph_path: Path | None,
    candidate_id: str,
    property_name: str,
) -> dict[str, Any] | None:
    measurement = get_measurement_for_molecule_property(graph_path, candidate_id, property_name)
    if measurement is None:
        return None
    attrs = measurement.get("attrs", {})
    return {
        "candidate_id": candidate_id,
        "property_name": property_name,
        "value": attrs.get("value"),
        "source_group": attrs.get("source_group"),
        "provenance": attrs.get("provenance"),
    }



def summarize_candidate_property_values(
    graph_path: Path | None,
    candidate_id: str,
    property_names: list[str],
) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for property_name in property_names:
        summary = summarize_candidate_property_value(graph_path, candidate_id, property_name)
        if summary is not None:
            values[property_name] = summary
    return values



def summarize_support_contradiction(
    graph_path: Path | None,
    candidate_id: str,
    property_name: str | None = None,
    hop_limit: int = 2,
) -> dict[str, Any]:
    claims = get_claims_for_molecule(graph_path, candidate_id, hop_limit=hop_limit)
    evidence_hits = get_evidence_hits_for_candidate(graph_path, candidate_id, hop_limit=hop_limit)

    exact_match_hits = 0
    analog_match_hits = 0
    support_score = 0.0
    contradiction_score = 0.0
    contradictions = 0

    for claim in claims:
        attrs = claim.get("attrs", {})
        signals = attrs.get("signals", {})
        polarity = attrs.get("polarity")
        summary_text = str(attrs.get("summary") or "").lower()
        claim_property_name = str(attrs.get("property_name") or "").lower()
        if property_name:
            wanted = property_name.lower()
            if claim_property_name != wanted and wanted not in summary_text:
                if not any(wanted in str(v).lower() for v in signals.values() if isinstance(v, (str, int, float))):
                    continue
        if polarity == "contradiction":
            contradictions += 1
            contradiction_score += 1.0
        exact_match_hits += int(signals.get("exact_match_hits", 0) or 0)
        analog_match_hits += int(signals.get("analog_match_hits", 0) or 0)
        support_score += float(signals.get("support_score", 0.0) or 0.0)
        contradiction_score += float(signals.get("contradiction_score", 0.0) or 0.0)

    for hit in evidence_hits:
        attrs = hit.get("attrs", {})
        match_type = attrs.get("match_type")
        confidence = float(attrs.get("confidence", 0.0) or 0.0)
        if match_type == "exact":
            exact_match_hits += 1
            support_score += max(confidence, 0.5)
        elif match_type in {"analog", "family"}:
            analog_match_hits += 1
            support_score += max(confidence * 0.5, 0.1)

    return {
        "candidate_id": candidate_id,
        "property_name": property_name,
        "claim_count": len(claims),
        "evidence_count": len(evidence_hits),
        "exact_match_hits": exact_match_hits,
        "analog_match_hits": analog_match_hits,
        "support_score": support_score,
        "contradiction_score": contradiction_score,
        "contradictions": contradictions,
    }



def retrieve_context(graph_path: Path | None, query: RetrievalQuery) -> RetrievedContext:
    context = RetrievedContext(candidate_id=query.candidate_id)
    graph = _load_graph(graph_path)
    if graph is None:
        context.open_questions.append("No knowledge graph available yet for this run.")
        context.query_hints.append(f"{query.candidate_id} phenothiazine literature")
        return context

    neighborhood = get_candidate_neighborhood(graph, query.candidate_id, hop_limit=query.hop_limit)
    nodes = neighborhood.get("nodes", [])
    edges = neighborhood.get("edges", [])
    context.neighborhood_node_count = len(nodes)
    context.neighborhood_edge_count = len(edges)

    papers = []
    claims = []
    evidence_hits = []
    measurements = []
    property_names: set[str] = set()
    for node in nodes:
        node_type = node.get("type")
        attrs = node.get("attrs", {})
        if node_type in {"Paper", "LiteraturePaper"}:
            papers.append(node)
        elif node_type in {"Claim", "LiteratureClaim"}:
            claims.append(node)
        elif node_type == "EvidenceHit":
            evidence_hits.append(node)
        elif node_type == "Measurement":
            measurements.append(node)
            if attrs.get("property_name"):
                property_names.add(str(attrs.get("property_name")))

    context.papers_count = len(papers)
    context.claim_count = len(claims)
    context.evidence_count = len(evidence_hits)
    context.measurement_count = len(measurements)
    context.property_count = len(property_names)

    for claim in claims[: query.max_claims]:
        attrs = claim.get("attrs", {})
        signals = attrs.get("signals", {})
        polarity = attrs.get("polarity")
        match_type = attrs.get("match_type") or signals.get("match_type") or "unknown"
        record = {
            "id": claim.get("id"),
            "summary": attrs.get("summary"),
            "status": attrs.get("status"),
            "signals": signals,
            "polarity": polarity,
            "match_type": match_type,
        }
        if polarity == "contradiction":
            context.contradictory_claims.append(record)
            context.contradiction_score += 1.0
        elif match_type == "exact":
            context.exact_match_claims.append(record)
            context.exact_match_hits += 1
            context.support_score += 2.0
        else:
            context.analog_claims.append(record)
            if signals.get("exact_match_hits"):
                context.exact_match_hits += int(signals.get("exact_match_hits", 0))
                context.support_score += float(signals.get("exact_match_hits", 0)) * 2.0
            if signals.get("analog_match_hits"):
                context.analog_match_hits += int(signals.get("analog_match_hits", 0))
                context.support_score += float(signals.get("analog_match_hits", 0)) * 0.5
            else:
                context.support_score += 0.25

    for hit in evidence_hits[: query.max_evidence]:
        attrs = hit.get("attrs", {})
        context.property_evidence.append(
            {
                "id": hit.get("id"),
                "query": attrs.get("query"),
                "match_type": attrs.get("match_type"),
                "confidence": attrs.get("confidence"),
            }
        )
        provenance = attrs.get("provenance")
        if provenance:
            context.provenance_summary.append(provenance)

    for measurement in measurements[: query.max_evidence]:
        attrs = measurement.get("attrs", {})
        context.measurement_summary.append(
            {
                "id": measurement.get("id"),
                "property_name": attrs.get("property_name"),
                "value": attrs.get("value"),
            }
        )
        provenance = attrs.get("provenance")
        if provenance:
            context.provenance_summary.append(provenance)

    if query.properties_of_interest:
        context.query_hints.extend(
            [
                f"{query.candidate_id} {' '.join(query.properties_of_interest)} phenothiazine",
                f"phenothiazine derivative {' '.join(query.properties_of_interest)} analog synthesis",
            ]
        )

    if context.claim_count == 0:
        context.open_questions.append("No prior claims found for this candidate neighborhood.")
    if context.measurement_count > 0:
        context.query_hints.append(f"{query.candidate_id} measured properties available")
    if context.exact_match_hits == 0:
        context.open_questions.append("No exact-match literature evidence found yet; rely on analog reasoning.")
    if context.analog_match_hits == 0:
        context.open_questions.append("No analog evidence found yet; broaden motif- or scaffold-level search.")
    if not context.property_evidence and query.properties_of_interest:
        context.open_questions.append(
            f"No explicit evidence hits found for target properties: {', '.join(query.properties_of_interest)}."
        )

    return context
