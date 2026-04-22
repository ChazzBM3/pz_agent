from __future__ import annotations

from pathlib import Path

from pz_agent.kg.builder import build_graph_snapshot
from pz_agent.state import RunState


def test_build_graph_snapshot_adds_scaffold_nodes_and_edges(tmp_path: Path) -> None:
    state = RunState(
        config={},
        run_dir=tmp_path,
        library_clean=[
            {
                "id": "cand-1",
                "smiles": "c1ccc2c(c1)Nc1ccccc1S2",
                "identity": {"canonical_smiles": "c1ccc2c(c1)Nc1ccccc1S2"},
            }
        ],
    )

    graph = build_graph_snapshot(state)
    scaffold_nodes = [node for node in graph["nodes"] if node["type"] == "Scaffold"]
    has_scaffold_edges = [edge for edge in graph["edges"] if edge["type"] == "HAS_SCAFFOLD"]

    assert scaffold_nodes
    assert scaffold_nodes[0]["attrs"]["smiles"] == "c1ccc2c(c1)Nc1ccccc1S2"
    assert has_scaffold_edges == [
        {
            "source": "cand-1",
            "target": "scaffold::c1ccc2c(c1)Nc1ccccc1S2",
            "type": "HAS_SCAFFOLD",
        }
    ]
