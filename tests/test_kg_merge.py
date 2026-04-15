from __future__ import annotations

from pz_agent.kg.merge import append_graph_update, ingest_graph_update, merge_graphs


def test_merge_graphs_deduplicates_nodes_and_edges() -> None:
    graph_a = {
        "nodes": [
            {"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1"}},
            {"id": "paper::1", "type": "Paper", "attrs": {"title": "Paper A", "url": None}},
        ],
        "edges": [
            {"source": "cand_1", "target": "paper::1", "type": "SUPPORTED_BY"},
        ],
        "prediction_provenance_summary": [{"id": "cand_1", "prediction_provenance": {"model": "a"}}],
    }
    graph_b = {
        "nodes": [
            {"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1", "canonical_smiles": "CC"}},
            {"id": "paper::1", "type": "Paper", "attrs": {"title": "Paper A", "url": "https://example.org"}},
        ],
        "edges": [
            {"source": "cand_1", "target": "paper::1", "type": "SUPPORTED_BY"},
        ],
        "prediction_provenance_summary": [{"id": "cand_1", "prediction_provenance": {"model": "a"}}],
    }

    merged = merge_graphs(graph_a, graph_b)

    assert len(merged["nodes"]) == 2
    assert len(merged["edges"]) == 1
    molecule = next(node for node in merged["nodes"] if node["id"] == "cand_1")
    paper = next(node for node in merged["nodes"] if node["id"] == "paper::1")
    assert molecule["attrs"]["canonical_smiles"] == "CC"
    assert paper["attrs"]["url"] == "https://example.org"
    assert len(merged["prediction_provenance_summary"]) == 1


def test_merge_graphs_adds_identity_grouping_edges_non_destructively() -> None:
    graph_a = {
        "nodes": [
            {"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1", "stable_identity_key": "mol_identity::shared"}},
            {"id": "cand_2", "type": "Molecule", "attrs": {"id": "cand_2", "stable_identity_key": "mol_identity::shared"}},
        ],
        "edges": [],
        "prediction_provenance_summary": [],
    }

    merged = merge_graphs(graph_a)

    assert any(node["id"] == "mol_identity::shared" and node["type"] == "MolecularRepresentation" for node in merged["nodes"])
    assert any(edge["source"] == "cand_1" and edge["target"] == "mol_identity::shared" and edge["type"] == "HAS_REPRESENTATION" for edge in merged["edges"])
    assert any(edge["source"] == "cand_2" and edge["target"] == "mol_identity::shared" and edge["type"] == "HAS_REPRESENTATION" for edge in merged["edges"])


def test_append_graph_update_merges_existing_and_new_graph() -> None:
    existing = {
        "nodes": [{"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1"}}],
        "edges": [],
        "prediction_provenance_summary": [],
    }
    update = {
        "nodes": [{"id": "claim::cand_1", "type": "Claim", "attrs": {"candidate_id": "cand_1"}}],
        "edges": [{"source": "claim::cand_1", "target": "cand_1", "type": "ABOUT_MOLECULE"}],
        "prediction_provenance_summary": [],
    }

    merged = append_graph_update(existing, update)

    assert len(merged["nodes"]) == 2
    assert len(merged["edges"]) == 1


def test_ingest_graph_update_wraps_nodes_and_edges() -> None:
    base = {
        "nodes": [{"id": "cand_1", "type": "Molecule", "attrs": {"id": "cand_1"}}],
        "edges": [],
        "prediction_provenance_summary": [],
    }
    merged = ingest_graph_update(
        base,
        update_nodes=[{"id": "property::solubility", "type": "Property", "attrs": {"name": "solubility"}}],
        update_edges=[{"source": "cand_1", "target": "property::solubility", "type": "ABOUT_PROPERTY"}],
    )

    assert len(merged["nodes"]) == 2
    assert any(node["id"] == "property::solubility" for node in merged["nodes"])
    assert any(edge["type"] == "ABOUT_PROPERTY" for edge in merged["edges"])
