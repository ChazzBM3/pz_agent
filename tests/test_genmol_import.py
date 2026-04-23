from __future__ import annotations

import json
from pathlib import Path

from pz_agent.chemistry.genmol_import import load_external_genmol_candidates
from pz_agent.runner import run_pipeline


GENMOL_PAYLOAD = {
    "metadata": {
        "input_smiles": "CCN1c2ccc(C(F)(F)F)cc2Sc2cc(C(F)(F)F)ccc21",
        "model_version": "v2",
        "num_generations_requested": 12,
        "num_generated_unique": 2,
        "num_conformers_per_molecule": 12,
        "seed": 42,
    },
    "site_fragments": [{"atom_index": 1, "fragment_smiles": "[*]c1ccccc1"}],
    "site_outputs": [{"atom_index": 1, "num_requested": 12, "num_returned": 2}],
    "results": [
        {
            "generated_index": 0,
            "smiles": "CCN1c2ccc(C(F)(F)F)cc2Sc2cc(C(F)(F)F)ccc21",
            "sa_score": 2.5,
            "logS_mol_L": -6.0,
            "S_mg_mL": 0.001,
            "Sol_Class": "Low",
            "lowest_energy": -12.4,
            "lowest_energy_conformer_id": 0,
            "force_field": "MMFF94s",
            "num_conformers_embedded": 12,
            "atom_symbols": ["C", "N"],
            "coordinates_angstrom": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        },
        {
            "generated_index": 1,
            "smiles": "CCN1c2ccc(OC)cc2Sc2cc(OC)ccc21",
            "sa_score": 4.0,
            "solp_logS": -2.0,
            "lowest_energy": -9.1,
            "lowest_energy_conformer_id": 1,
            "force_field": "MMFF94s",
            "num_conformers_embedded": 12,
            "atom_symbols": ["C", "N"],
            "coordinates_angstrom": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        },
    ],
}


def test_load_external_genmol_candidates_from_workflow_payload(tmp_path: Path) -> None:
    run_dir = tmp_path / "genmol_run"
    run_dir.mkdir()
    payload_path = run_dir / "lowest_energy_conformers.json"
    payload_path.write_text(json.dumps(GENMOL_PAYLOAD), encoding="utf-8")

    rows = load_external_genmol_candidates(run_dir)

    assert len(rows) == 2
    first = rows[0]
    second = rows[1]
    assert first["generation_metadata"]["model_version"] == "v2"
    assert first["site_fragments"][0]["atom_index"] == 1
    assert first["external_synthesizability"] == 7.5 / 9.0
    assert first["external_solubility"] == 0.25
    assert first["external_solubility_units"] == "normalized_from_logS_mol_L"
    assert second["external_synthesizability"] == 6.0 / 9.0
    assert second["external_solubility"] == 0.75


def test_pipeline_uses_genmol_external_scores_without_explicit_flag(tmp_path: Path) -> None:
    payload_path = tmp_path / "lowest_energy_conformers.json"
    payload_path.write_text(json.dumps(GENMOL_PAYLOAD), encoding="utf-8")

    config_path = tmp_path / "genmol.yaml"
    config_path.write_text(
        f"""
project:
  name: genmol-import-test
generation:
  external_genmol_path: {payload_path}
screening:
  shortlist_size: 2
pipeline:
  stages:
    - library_designer
    - standardizer
    - surrogate_screen
    - knowledge_graph
    - ranker
""",
        encoding="utf-8",
    )

    state = run_pipeline(config_path, run_dir=tmp_path / "run")

    assert state.library_raw is not None
    assert len(state.library_raw) == 2
    assert state.predictions is not None
    by_id = {row["id"]: row for row in state.predictions}
    assert by_id["genmol_0001"]["predicted_synthesizability"] == 7.5 / 9.0
    assert by_id["genmol_0001"]["predicted_solubility"] == 0.25
    assert by_id["genmol_0001"]["prediction_provenance"]["synthesizability"]["source_type"] == "external_import"
    assert by_id["genmol_0002"]["predicted_solubility"] == 0.75
    assert state.knowledge_graph_path is not None
    graph = json.loads(state.knowledge_graph_path.read_text())
    assert any(
        node["type"] == "SimulationResult"
        and node["attrs"].get("simulation_type") == "genmol_conformer_generation"
        and node["attrs"].get("status") == "generated"
        for node in graph.get("nodes", [])
    )
    assert any(
        node["type"] == "Measurement"
        and node["attrs"].get("property_name") == "sa_score"
        and node["attrs"].get("provenance", {}).get("source_type") == "genmol_workflow_import"
        for node in graph.get("nodes", [])
    )
    assert any(
        edge["type"] == "GENERATED_BY_BATCH" and edge["source"] == "genmol_0001"
        for edge in graph.get("edges", [])
    )
    assert state.ranked is not None
    assert state.ranked[0]["id"] == "genmol_0002"
    assert any("auto-detected external score import" in log for log in state.logs)
