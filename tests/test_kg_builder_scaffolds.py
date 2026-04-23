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



def test_build_graph_snapshot_adds_simulation_failure_nodes(tmp_path: Path) -> None:
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
        simulation_failures=[
            {
                "candidate_id": "cand-1",
                "submission_id": "submit-001",
                "job_id": "job-001",
                "status": "failed",
                "backend": "htvs_supercloud",
                "engine": "orca",
                "simulation_type": "geometry_optimization",
                "failure_source": "simulation_extract",
                "failure_log": {
                    "job_spec_path": "/tmp/orca_job.json",
                    "logged_for_followup": True,
                },
            }
        ],
    )

    graph = build_graph_snapshot(state)
    failure_nodes = [node for node in graph["nodes"] if node["type"] == "SimulationFailure"]
    failure_edges = [edge for edge in graph["edges"] if edge["type"] == "CONTRADICTED_BY"]

    assert len(failure_nodes) == 1
    assert failure_nodes[0]["attrs"]["candidate_id"] == "cand-1"
    assert failure_nodes[0]["attrs"]["failure_log"]["logged_for_followup"] is True
    assert failure_edges == [
        {
            "source": failure_nodes[0]["id"],
            "target": "cand-1",
            "type": "CONTRADICTED_BY",
        }
    ]
