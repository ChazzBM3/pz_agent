from __future__ import annotations

from pathlib import Path

from pz_agent.kg.scaffold_features import build_scaffold_feature_index


def test_build_scaffold_feature_index_extracts_family_context() -> None:
    graph = {
        "nodes": [
            {"id": "mol::a", "type": "Molecule", "attrs": {}},
            {"id": "mol::b", "type": "Molecule", "attrs": {}},
            {"id": "scaffold::1", "type": "Scaffold", "attrs": {"smiles": "c1ccccc1"}},
        ],
        "edges": [
            {"source": "mol::a", "target": "scaffold::1", "type": "HAS_SCAFFOLD"},
            {"source": "mol::b", "target": "scaffold::1", "type": "HAS_SCAFFOLD"},
            {"source": "meas::1", "target": "mol::a", "type": "MEASURED_FOR"},
            {"source": "meas::2", "target": "mol::a", "type": "MEASURED_FOR"},
            {"source": "meas::3", "target": "mol::b", "type": "MEASURED_FOR"},
        ],
    }

    features = build_scaffold_feature_index(graph)

    assert features["mol::a"]["scaffold_smiles"] == "c1ccccc1"
    assert features["mol::a"]["scaffold_family_size"] == 2
    assert features["mol::a"]["scaffold_measurement_density"] == 2
    assert features["mol::a"]["scaffold_family_avg_measurements"] == 1.5
