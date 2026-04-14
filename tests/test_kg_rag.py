from __future__ import annotations

from pathlib import Path

from pz_agent.io import write_json
from pz_agent.kg.claims import build_bridge_case_nodes
from pz_agent.kg.rag import (
    get_claims_for_molecule,
    get_evidence_hits_for_candidate,
    get_measurements_for_molecule,
    summarize_property_coverage,
    summarize_support_contradiction,
)


SAMPLE_GRAPH = {
    "nodes": [
        {"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1"}},
        {
            "id": "claim::cand_1",
            "type": "Claim",
            "attrs": {
                "summary": "Solubility support for cand_1 from analog evidence.",
                "property_name": "solubility",
                "signals": {
                    "exact_match_hits": 1,
                    "analog_match_hits": 2,
                    "support_score": 3.5,
                    "contradiction_score": 0.0,
                    "property_support": {"solubility": 2},
                },
            },
        },
        {
            "id": "evidence::cand_1::0",
            "type": "EvidenceHit",
            "attrs": {
                "query": "cand_1 solubility phenothiazine",
                "match_type": "analog",
                "confidence": 0.8,
                "property_mentions": ["solubility"],
            },
        },
        {
            "id": "paper::abc",
            "type": "Paper",
            "attrs": {
                "title": "Example paper",
                "url": "https://example.org/paper",
            },
        },
    ],
    "edges": [
        {"source": "claim::cand_1", "target": "cand_1", "type": "ABOUT_MOLECULE"},
        {"source": "claim::cand_1", "target": "evidence::cand_1::0", "type": "HAS_EVIDENCE_HIT"},
        {"source": "evidence::cand_1::0", "target": "paper::abc", "type": "SUPPORTED_BY"},
        {"source": "evidence::cand_1::0", "target": "cand_1", "type": "ANALOG_OF"},
    ],
}


def test_claim_and_evidence_retrieval(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    write_json(graph_path, SAMPLE_GRAPH)

    claims = get_claims_for_molecule(graph_path, "cand_1")
    hits = get_evidence_hits_for_candidate(graph_path, "cand_1")

    assert len(claims) == 1
    assert len(hits) == 1
    assert claims[0]["id"] == "claim::cand_1"
    assert hits[0]["id"] == "evidence::cand_1::0"


def test_support_summary(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    write_json(graph_path, SAMPLE_GRAPH)

    summary = summarize_support_contradiction(graph_path, "cand_1", property_name="solubility")

    assert summary["candidate_id"] == "cand_1"
    assert summary["claim_count"] >= 1
    assert summary["evidence_count"] >= 1
    assert summary["exact_match_hits"] >= 1
    assert summary["analog_match_hits"] >= 2
    assert summary["support_score"] > 0


def test_measurement_retrieval_and_property_coverage(tmp_path: Path) -> None:
    graph = dict(SAMPLE_GRAPH)
    graph["nodes"] = list(SAMPLE_GRAPH["nodes"]) + [
        {
            "id": "measurement::cand_1::omega",
            "type": "Measurement",
            "attrs": {
                "record_id": "cand_1",
                "property_name": "omega",
                "value": 0.17,
            },
        }
    ]
    graph["edges"] = list(SAMPLE_GRAPH["edges"]) + [
        {"source": "measurement::cand_1::omega", "target": "cand_1", "type": "MEASURED_FOR"},
        {"source": "measurement::cand_1::omega", "target": "property::omega", "type": "HAS_PROPERTY"},
    ]
    graph_path = tmp_path / "graph.json"
    write_json(graph_path, graph)

    measurements = get_measurements_for_molecule(graph_path, "cand_1")
    coverage = summarize_property_coverage(graph_path, "cand_1")

    assert len(measurements) == 1
    assert coverage["measurement_count"] == 1
    assert coverage["property_count"] == 1
    assert coverage["properties"] == ["omega"]


def test_support_summary_property_filter_excludes_nonmatching_claims(tmp_path: Path) -> None:
    graph = dict(SAMPLE_GRAPH)
    graph["nodes"] = list(SAMPLE_GRAPH["nodes"]) + [
        {
            "id": "claim::cand_1::instability",
            "type": "Claim",
            "attrs": {
                "summary": "Instability warning for cand_1.",
                "property_name": "instability",
                "polarity": "contradiction",
                "signals": {
                    "exact_match_hits": 0,
                    "analog_match_hits": 0,
                    "support_score": 0.0,
                    "contradiction_score": 5.0,
                },
            },
        }
    ]
    graph["edges"] = list(SAMPLE_GRAPH["edges"]) + [
        {"source": "claim::cand_1::instability", "target": "cand_1", "type": "ABOUT_MOLECULE"}
    ]
    graph_path = tmp_path / "graph.json"
    write_json(graph_path, graph)

    summary = summarize_support_contradiction(graph_path, "cand_1", property_name="solubility")

    assert summary["contradictions"] == 0


def test_build_bridge_case_nodes_for_mixed_support_note() -> None:
    nodes = build_bridge_case_nodes(
        {
            "candidate_id": "cand_bridge",
            "summary": "Mixed PT and adjacent-scaffold support for solubility/redox tuning.",
            "signals": {"property_support": {"solubility": 2, "oxidation_potential": 1}},
            "support_mix": {
                "direct_pt_support": 0.6,
                "pt_scaffold_support": 0.2,
                "adjacent_scaffold_support": 0.4,
                "quinone_bridge_support": 0.0,
                "simulation_support": 0.0,
                "metadata_support": 0.0,
                "contradiction_count": 0,
                "transferability_score": 0.72,
            },
            "evidence": [{"id": "evidence::cand_bridge::0", "source_family": "adjacent"}],
        }
    )
    assert any(node["type"] == "BridgeCase" for node in nodes)
    bridge_case = next(node for node in nodes if node["type"] == "BridgeCase")
    assert bridge_case["attrs"]["transferability_score"] == 0.72
    assert "solubilizing_handle" in bridge_case["attrs"]["bridge_principle_refs"]



def test_evidence_match_type_is_inferred_from_exact_match_edges(tmp_path: Path) -> None:
    graph = {
        "nodes": [
            {"id": "cand_exact", "type": "Molecule", "attrs": {"id": "cand_exact"}},
            {
                "id": "evidence::cand_exact::0",
                "type": "EvidenceHit",
                "attrs": {
                    "query": "cand_exact oxidation potential phenothiazine",
                    "confidence": 0.9,
                },
            },
        ],
        "edges": [
            {"source": "evidence::cand_exact::0", "target": "cand_exact", "type": "EXACT_MATCH_OF"},
        ],
    }
    graph_path = tmp_path / "graph.json"
    write_json(graph_path, graph)

    hits = get_evidence_hits_for_candidate(graph_path, "cand_exact")
    summary = summarize_support_contradiction(graph_path, "cand_exact")

    assert hits[0]["attrs"]["match_type"] == "exact"
    assert summary["exact_match_hits"] == 1
    assert summary["support_score"] >= 0.9
