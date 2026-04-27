from __future__ import annotations

import json
from pathlib import Path

import pytest

from pz_agent.agents.generation_iteration_handoff import GenerationIterationHandoffAgent
from pz_agent.agents.generation_iteration_execute import GenerationIterationExecuteAgent
from pz_agent.agents.generation_iteration_loop import GenerationIterationLoopAgent
from pz_agent.agents.generation_iteration_monitor import GenerationIterationMonitorAgent
from pz_agent.agents.generation_iteration_recycle import GenerationIterationRecycleAgent
from pz_agent.agents.generation_iteration_submit import GenerationIterationSubmitAgent
from pz_agent.agents.graph_expansion import GraphExpansionAgent
from pz_agent.chemistry.genmol_import import load_external_genmol_candidates
from pz_agent.runner import run_pipeline
from pz_agent.state import RunState


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


def test_graph_expansion_selects_promising_genmol_candidate_for_iteration(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "genmol_0002",
                        "type": "Molecule",
                        "attrs": {
                            "id": "genmol_0002",
                            "smiles": "CCN1c2ccc(OC)cc2Sc2cc(OC)ccc21",
                            "generation_engine": "genmol_external",
                            "stable_identity_key": "stable::genmol_0002",
                        },
                    },
                    {
                        "id": "generation_batch::0",
                        "type": "GenerationBatch",
                        "attrs": {
                            "engine": "genmol_external",
                            "source_path": "/tmp/genmol/lowest_energy_conformers.json",
                            "count": 2,
                            "metadata": {
                                "mode": "genmol_generation",
                                "objective": "improve soluble PT candidates",
                                "bridge_dimensions": ["solubilizing_handle"],
                            },
                        },
                    },
                    {
                        "id": "sim::genmol_0002",
                        "type": "SimulationResult",
                        "attrs": {
                            "candidate_id": "genmol_0002",
                            "simulation_type": "genmol_conformer_generation",
                            "engine": "genmol_external",
                            "status": "generated",
                        },
                    },
                    {
                        "id": "measurement::sa",
                        "type": "Measurement",
                        "attrs": {
                            "record_id": "genmol_0002",
                            "property_name": "sa_score",
                            "value": 2.7,
                            "source_group": "genmol_external",
                            "provenance": {"source_type": "genmol_workflow_import"},
                        },
                    },
                    {
                        "id": "measurement::logs",
                        "type": "Measurement",
                        "attrs": {
                            "record_id": "genmol_0002",
                            "property_name": "logS_mol_L",
                            "value": -2.3,
                            "source_group": "genmol_external",
                            "provenance": {"source_type": "genmol_workflow_import"},
                        },
                    },
                    {
                        "id": "bridge_case::genmol_0002",
                        "type": "BridgeCase",
                        "attrs": {
                            "target_candidate_id": "genmol_0002",
                            "transferability_score": 0.88,
                            "bridge_principle_refs": ["solubilizing_handle"],
                            "next_action": "generation_prior",
                        },
                    },
                ],
                "edges": [
                    {"source": "genmol_0002", "target": "generation_batch::0", "type": "GENERATED_BY_BATCH"},
                    {"source": "sim::genmol_0002", "target": "genmol_0002", "type": "SIMULATED_FOR"},
                    {"source": "measurement::sa", "target": "genmol_0002", "type": "MEASURED_FOR"},
                    {"source": "measurement::logs", "target": "genmol_0002", "type": "MEASURED_FOR"},
                    {"source": "bridge_case::genmol_0002", "target": "genmol_0002", "type": "ABOUT_MOLECULE"},
                ],
            }
        ),
        encoding="utf-8",
    )

    state = RunState(config={}, run_dir=tmp_path, knowledge_graph_path=graph_path)
    state = GraphExpansionAgent(config={}).run(state)

    assert state.expansion_registry is not None
    assert any(item.get("proposal_type") == "generation_iteration_candidate" for item in state.expansion_registry)
    assert state.action_queue is not None
    regen = next(item for item in state.action_queue if item.get("action_type") == "generation_iteration")
    assert regen["candidate_id"] == "genmol_0002"
    assert regen["payload"]["protocol"]["engine"] == "genmol_external"
    assert regen["payload"]["protocol"]["metadata"]["mode"] == "genmol_generation"
    assert regen["payload"]["selection_basis"]["transferability_score"] == 0.88


def test_generation_iteration_handoff_emits_manifest(tmp_path: Path) -> None:
    state = RunState(
        config={
            "generation": {
                "num_generations": 64,
                "num_conformers": 32,
                "iteration_top_k": 3,
                "prompts": {"objective": "improve PT solubility while preserving redox window"},
            }
        },
        run_dir=tmp_path,
        action_queue=[
            {
                "candidate_id": "genmol_0002",
                "priority": 0.82,
                "source": "graph_expansion",
                "proposal_type": "generation_iteration_candidate",
                "proposal_reason": "promising_genmol_iteration_seed",
                "critic_reason": "high_transfer_genmol_iteration_seed",
                "action_type": "generation_iteration",
                "payload": {
                    "candidate": {
                        "id": "genmol_0002",
                        "smiles": "CCN1c2ccc(OC)cc2Sc2cc(OC)ccc21",
                        "stable_identity_key": "stable::genmol_0002",
                    },
                    "protocol": {
                        "engine": "genmol_external",
                        "source_path": "/tmp/genmol/lowest_energy_conformers.json",
                        "count": 2,
                        "metadata": {
                            "mode": "genmol_generation",
                            "objective": "improve soluble PT candidates",
                            "num_generations_requested": 120,
                            "num_conformers_per_molecule": 24,
                            "bridge_dimensions": ["solubilizing_handle"],
                            "generation_priors": {"pt_direct": 0.4, "bridge_driven": 0.4, "simulation_driven": 0.2},
                        },
                    },
                    "bridge_case_id": "bridge_case::genmol_0002",
                    "bridge_principles": ["solubilizing_handle"],
                    "generation_batch_ids": ["generation_batch::0"],
                    "history": {"genmol_result_count": 1},
                    "selection_basis": {
                        "transferability_score": 0.88,
                        "support_score": 1.4,
                        "measurement_summary": {"property_count": 2},
                    },
                },
            }
        ],
    )

    state = GenerationIterationHandoffAgent(config=state.config).run(state)

    assert state.generation_iteration_manifest is not None
    assert state.generation_iteration_manifest["contract_version"] == "genmol.iteration_request.v1"
    assert state.generation_iteration_manifest["queue_size"] == 1
    queued = state.generation_iteration_manifest["queue"][0]
    assert queued["generation_request"]["num_generations"] == 120
    assert queued["generation_request"]["num_conformers"] == 24
    assert queued["generation_request"]["bridge_dimensions"] == ["solubilizing_handle"]
    assert queued["selection_basis"]["transferability_score"] == 0.88
    assert (tmp_path / "generation_iteration_manifest.json").exists()
    input_records = json.loads((tmp_path / "genmol_iteration_input.json").read_text())
    assert input_records[0]["id"] == "genmol_0002"
    assert input_records[0]["smiles"] == "CCN1c2ccc(OC)cc2Sc2cc(OC)ccc21"


def test_generation_iteration_submit_emits_launch_manifest(tmp_path: Path) -> None:
    state = RunState(
        config={
            "generation": {
                "submit": {
                    "atomistic_root": "~/AtomisticSkills",
                    "conda_env": "genmol-agent",
                    "runs_root": "research/iter_runs",
                    "launcher_mode": "serial_manifest",
                }
            }
        },
        run_dir=tmp_path,
        generation_iteration_queue=[
            {
                "candidate_id": "genmol_0002",
                "smiles": "CCN1c2ccc(OC)cc2Sc2cc(OC)ccc21",
                "priority": 0.82,
                "generation_request": {
                    "num_generations": 120,
                    "num_conformers": 24,
                    "engine": "genmol_external",
                },
                "selection_basis": {"transferability_score": 0.88},
            }
        ],
        generation_iteration_manifest={"queue_size": 1},
    )

    state = GenerationIterationSubmitAgent(config=state.config).run(state)

    assert state.generation_iteration_submissions is not None
    assert len(state.generation_iteration_submissions) == 1
    submission = state.generation_iteration_submissions[0]
    assert submission["status"] == "prepared"
    assert "--num-generations 120" in submission["command"]
    assert "--num-conformers 24" in submission["command"]
    assert "--device cuda" in submission["command"]
    assert submission["device"] == "cuda"
    launch_manifest = json.loads((tmp_path / "generation_iteration_launch_manifest.json").read_text())
    assert launch_manifest["contract_version"] == "genmol.iteration_launch.v1"
    assert launch_manifest["submission_count"] == 1
    assert launch_manifest["submissions"][0]["candidate_id"] == "genmol_0002"
    launcher_script = (tmp_path / "launch_genmol_iteration.sh").read_text()
    assert "generate_functionalized_lowest_conformers.py" in launcher_script
    assert "genmol_0002" in launcher_script


def test_generation_iteration_execute_can_autolaunch_with_subprocess_run(tmp_path: Path, monkeypatch) -> None:
    command_log: list[str] = []

    def fake_run(command, shell, text, capture_output):
        assert shell is True
        assert text is True
        assert capture_output is True
        command_log.append(command)
        return __import__("subprocess").CompletedProcess(command, 0, stdout="launched", stderr="")

    monkeypatch.setattr("pz_agent.agents.generation_iteration_execute.subprocess.run", fake_run)

    state = RunState(
        config={
            "generation": {
                "submit": {
                    "execute_launch": True,
                    "launch_mode": "subprocess_run",
                }
            }
        },
        run_dir=tmp_path,
        generation_iteration_submissions=[
            {
                "candidate_id": "genmol_0002",
                "launcher_mode": "serial_manifest",
                "command": "echo launch genmol_0002",
            }
        ],
    )

    state = GenerationIterationExecuteAgent(config=state.config).run(state)

    assert command_log == ["echo launch genmol_0002"]
    assert state.generation_iteration_execution is not None
    assert state.generation_iteration_execution[0]["status"] == "launched"
    assert state.generation_iteration_execution[0]["executed"] is True
    execution = json.loads((tmp_path / "generation_iteration_execution.json").read_text())
    assert execution[0]["candidate_id"] == "genmol_0002"


def test_generation_iteration_execute_can_autolaunch_in_background(tmp_path: Path, monkeypatch) -> None:
    popen_calls: list[dict] = []

    class FakePopen:
        def __init__(self, args, stdout=None, stderr=None, stdin=None, start_new_session=None, env=None):
            popen_calls.append(
                {
                    "args": args,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdin": stdin,
                    "start_new_session": start_new_session,
                    "env_has_path": isinstance(env, dict) and "PATH" in env,
                }
            )
            self.pid = 424242

    monkeypatch.setattr("pz_agent.agents.generation_iteration_execute.subprocess.Popen", FakePopen)

    state = RunState(
        config={
            "generation": {
                "submit": {
                    "execute_launch": True,
                    "launch_mode": "nohup_background",
                }
            }
        },
        run_dir=tmp_path,
        generation_iteration_submissions=[
            {
                "candidate_id": "genmol_0003",
                "launcher_mode": "serial_manifest",
                "command": "echo launch genmol_0003",
            }
        ],
    )

    state = GenerationIterationExecuteAgent(config=state.config).run(state)

    assert len(popen_calls) == 1
    assert popen_calls[0]["args"][0:2] == ["bash", "-lc"]
    assert popen_calls[0]["start_new_session"] is True
    assert state.generation_iteration_execution is not None
    assert state.generation_iteration_execution[0]["status"] == "launched"
    assert state.generation_iteration_execution[0]["background_pid"] == 424242
    assert state.generation_iteration_execution[0]["background_command"] == "echo launch genmol_0003"


def test_generation_iteration_execute_skips_when_disabled(tmp_path: Path) -> None:
    state = RunState(
        config={"generation": {"submit": {"execute_launch": False}}},
        run_dir=tmp_path,
        generation_iteration_submissions=[
            {
                "candidate_id": "genmol_0002",
                "launcher_mode": "serial_manifest",
                "command": "echo launch genmol_0002",
            }
        ],
    )

    state = GenerationIterationExecuteAgent(config=state.config).run(state)

    assert state.generation_iteration_execution is not None
    assert state.generation_iteration_execution[0]["status"] == "skipped"
    assert state.generation_iteration_execution[0]["reason"] == "execute_launch_disabled"


def test_generation_iteration_monitor_collects_completed_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "research" / "iter_runs" / "01_genmol_0002"
    output_dir.mkdir(parents=True)
    payload = {
        "metadata": {"model_version": "v2", "num_generations_requested": 12, "num_conformers_per_molecule": 8},
        "results": [
            {
                "generated_index": 0,
                "smiles": "CCN1c2ccc(OC)cc2Sc2cc(OC)ccc21",
                "sa_score": 2.7,
                "solp_logS": -2.1,
                "lowest_energy": -9.0,
            }
        ],
    }
    (output_dir / "lowest_energy_conformers.json").write_text(json.dumps(payload), encoding="utf-8")
    log_path = output_dir.with_suffix(".log")
    log_path.write_text("done\n", encoding="utf-8")

    state = RunState(
        config={},
        run_dir=tmp_path,
        generation_iteration_submissions=[
            {
                "candidate_id": "genmol_0002",
                "output_dir": str(output_dir),
                "log_path": str(log_path),
            }
        ],
    )

    state = GenerationIterationMonitorAgent(config=state.config).run(state)

    assert state.generation_iteration_monitor is not None
    assert state.generation_iteration_monitor[0]["status"] == "finished"
    assert state.generation_iteration_monitor[0]["generated_count"] == 1
    assert state.generation_iteration_reingest_manifest is not None
    assert state.generation_iteration_reingest_manifest["completed_submission_count"] == 1
    completed_candidates = json.loads((tmp_path / "generation_iteration_completed_candidates.json").read_text())
    assert completed_candidates[0]["seed"] == "genmol_0002"
    assert completed_candidates[0]["smiles"] == "CCN1c2ccc(OC)cc2Sc2cc(OC)ccc21"


def test_generation_iteration_submit_treats_yaml_null_remote_host_as_local(tmp_path: Path) -> None:
    state = RunState(
        config={
            "generation": {
                "submit": {"remote_host": None, "runs_root": "research/genmol_iteration_runs"},
            }
        },
        run_dir=tmp_path,
        generation_iteration_queue=[
            {
                "candidate_id": "dry_seed",
                "smiles": "CCO",
                "generation_request": {"num_generations": 1, "num_conformers": 1, "device": "cpu"},
            }
        ],
    )

    state = GenerationIterationSubmitAgent(config=state.config).run(state)

    assert state.generation_iteration_submissions is not None
    submission = state.generation_iteration_submissions[0]
    assert submission["remote_host"] is None
    assert submission["remote_workdir"] is None
    assert str(tmp_path) in submission["output_dir"]


def test_generation_iteration_monitor_collects_partial_generated_smiles_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "research" / "iter_runs" / "01_genmol_partial"
    partial_dir = output_dir / "genmol_generation" / "site_000"
    partial_dir.mkdir(parents=True)
    payload = {
        "mode": "fragment",
        "fragment_task": "scaffold_decoration",
        "fragment": "*c1ccc2c(c1)Sc1ccccc1S2",
        "model_version": "v2",
        "num_samples_requested": 1,
        "samples": ["ON=C(O)C1(c2ccc(F)cc2)CC(c2ccc3c(c2)Sc2ccccc2S3)N=C1O"],
        "metrics": {"num_generated": 1},
    }
    (partial_dir / "generated_smiles.json").write_text(json.dumps(payload), encoding="utf-8")
    log_path = output_dir.with_suffix(".log")
    log_path.write_text("still running\n", encoding="utf-8")

    state = RunState(
        config={},
        run_dir=tmp_path,
        generation_iteration_submissions=[
            {
                "candidate_id": "genmol_partial",
                "output_dir": str(output_dir),
                "log_path": str(log_path),
            }
        ],
    )

    state = GenerationIterationMonitorAgent(config=state.config).run(state)

    assert state.generation_iteration_monitor is not None
    assert state.generation_iteration_monitor[0]["status"] == "running"
    assert state.generation_iteration_monitor[0]["generated_count"] == 1
    assert state.generation_iteration_monitor[0]["partial_output_count"] == 1
    assert state.generation_iteration_reingest_manifest is not None
    assert state.generation_iteration_reingest_manifest["completed_submission_count"] == 0
    assert state.generation_iteration_reingest_manifest["waiting_submission_count"] == 1
    assert state.generation_iteration_reingest_manifest["awaiting_remote_outputs"] is True
    assert state.generation_iteration_reingest_manifest["status_counts"] == {"running": 1}
    completed_candidates = json.loads((tmp_path / "generation_iteration_completed_candidates.json").read_text())
    assert completed_candidates[0]["seed"] == "genmol_partial"
    assert completed_candidates[0]["smiles"] == "ON=C(O)C1(c2ccc(F)cc2)CC(c2ccc3c(c2)Sc2ccccc2S3)N=C1O"


def test_generation_iteration_monitor_marks_submitted_runs_as_awaiting_remote_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "research" / "iter_runs" / "01_genmol_submitted"
    log_path = output_dir.with_suffix(".log")
    state = RunState(
        config={},
        run_dir=tmp_path,
        generation_iteration_submissions=[
            {
                "candidate_id": "genmol_submitted",
                "output_dir": str(output_dir),
                "log_path": str(log_path),
            }
        ],
    )

    state = GenerationIterationMonitorAgent(config=state.config).run(state)

    assert state.generation_iteration_monitor is not None
    assert state.generation_iteration_monitor[0]["status"] == "submitted"
    assert state.generation_iteration_reingest_manifest is not None
    assert state.generation_iteration_reingest_manifest["completed_submission_count"] == 0
    assert state.generation_iteration_reingest_manifest["waiting_submission_count"] == 1
    assert state.generation_iteration_reingest_manifest["status_counts"] == {"submitted": 1}
    assert state.generation_iteration_reingest_manifest["awaiting_remote_outputs"] is True


def test_generation_iteration_recycle_skips_when_remote_outputs_are_still_pending(tmp_path: Path) -> None:
    aggregate_path = tmp_path / "generation_iteration_completed_candidates.json"
    aggregate_path.write_text("[]", encoding="utf-8")
    state = RunState(
        config={"generation": {"submit": {"remote_host": "grimm"}}},
        run_dir=tmp_path,
        generation_iteration_reingest_manifest={
            "aggregate_candidates_path": str(aggregate_path),
            "completed_submission_count": 0,
            "waiting_submission_count": 1,
            "awaiting_remote_outputs": True,
        },
    )

    state = GenerationIterationRecycleAgent(config=state.config).run(state)

    assert not (tmp_path / "generation_iteration_next_run.yaml").exists()
    assert any("no completed GenMol outputs" in message for message in state.logs)


def test_generation_iteration_loop_waits_for_submitted_or_running_remote_outputs(tmp_path: Path, monkeypatch) -> None:
    class FakeIterationAgent:
        def __init__(self, config):
            self.config = config

        def run(self, state: RunState) -> RunState:
            if state.generation_iteration_reingest_manifest is None:
                aggregate_path = state.run_dir / "generation_iteration_completed_candidates.json"
                aggregate_path.write_text("[]", encoding="utf-8")
                state.generation_iteration_reingest_manifest = {
                    "aggregate_candidates_path": str(aggregate_path),
                    "completed_submission_count": 0,
                    "waiting_submission_count": 2,
                    "status_counts": {"submitted": 1, "running": 1},
                    "awaiting_remote_outputs": True,
                }
                state.generation_iteration_monitor = [{"status": "submitted"}, {"status": "running"}]
            return state

    monkeypatch.setattr(
        "pz_agent.agents.generation_iteration_loop.AGENT_MAP",
        {
            "generation_iteration_handoff": FakeIterationAgent,
            "generation_iteration_submit": FakeIterationAgent,
            "generation_iteration_execute": FakeIterationAgent,
            "generation_iteration_monitor": FakeIterationAgent,
            "generation_iteration_recycle": FakeIterationAgent,
        },
    )

    state = RunState(
        config={"generation": {"loop": {"max_rounds": 3, "iteration_stages": ["generation_iteration_monitor"]}}},
        run_dir=tmp_path,
        ranked=[{"id": "seed_top", "smiles": "seed", "predicted_solubility": 0.50, "predicted_synthesizability": 0.50}],
    )

    state = GenerationIterationLoopAgent(config=state.config).run(state)

    assert state.generation_iteration_loop_summary is not None
    assert state.generation_iteration_loop_summary["completed_rounds"] == 0
    assert state.generation_iteration_loop_summary["stop_reason"] == "awaiting_remote_outputs"
    assert state.generation_iteration_loop_summary["awaiting_remote_outputs"] is True
    assert state.generation_iteration_loop_summary["waiting_submission_count"] == 2
    assert state.generation_iteration_loop_summary["waiting_statuses"] == ["running", "submitted"]
    waiting_round = state.generation_iteration_loop_summary["rounds"][0]
    assert waiting_round["stop_reason"] == "awaiting_remote_outputs"
    assert waiting_round["resume_iteration_run_dir"].endswith("generation_iteration_loop/round_01_iteration")


def test_generation_iteration_loop_can_resume_from_recorded_iteration_run_dir(tmp_path: Path, monkeypatch) -> None:
    resume_dir = tmp_path / "generation_iteration_loop" / "round_01_iteration"
    resume_dir.mkdir(parents=True)
    submissions_path = resume_dir / "generation_iteration_submissions.json"
    submissions_path.write_text(
        json.dumps([
            {
                "candidate_id": "resumed_seed",
                "output_dir": str(resume_dir / "remote_output"),
                "log_path": str(resume_dir / "remote_output.log"),
            }
        ]),
        encoding="utf-8",
    )
    round_counter = {"analysis": 0}

    class FakeMonitorAgent:
        def __init__(self, config):
            self.config = config

        def run(self, state: RunState) -> RunState:
            assert state.generation_iteration_submissions is not None
            assert state.generation_iteration_submissions[0]["candidate_id"] == "resumed_seed"
            aggregate_path = state.run_dir / "generation_iteration_completed_candidates.json"
            aggregate_path.write_text(json.dumps([{"smiles": "CCO"}]), encoding="utf-8")
            state.generation_iteration_reingest_manifest = {
                "aggregate_candidates_path": str(aggregate_path),
                "completed_submission_count": 1,
                "waiting_submission_count": 0,
                "status_counts": {"finished": 1},
            }
            state.generation_iteration_monitor = [{"status": "finished"}]
            return state

    class FakeRecycleAgent:
        def __init__(self, config):
            self.config = config

        def run(self, state: RunState) -> RunState:
            return state

    class FakeAnalysisAgent:
        def __init__(self, config):
            self.config = config

        def run(self, state: RunState) -> RunState:
            round_counter["analysis"] += 1
            state.ranked = [{"id": "resumed_top", "smiles": "CCO", "predicted_solubility": 0.60, "predicted_synthesizability": 0.70}]
            state.action_queue = []
            return state

    monkeypatch.setattr(
        "pz_agent.agents.generation_iteration_loop.AGENT_MAP",
        {
            "generation_iteration_monitor": FakeMonitorAgent,
            "generation_iteration_recycle": FakeRecycleAgent,
            "library_designer": FakeAnalysisAgent,
            "standardizer": FakeAnalysisAgent,
            "surrogate_screen": FakeAnalysisAgent,
            "knowledge_graph": FakeAnalysisAgent,
            "ranker": FakeAnalysisAgent,
            "graph_expansion": FakeAnalysisAgent,
        },
    )

    state = RunState(
        config={
            "generation": {
                "loop": {
                    "max_rounds": 1,
                    "resume_iteration_run_dir": str(resume_dir),
                    "analysis_stages": ["ranker"],
                }
            }
        },
        run_dir=tmp_path,
        ranked=[{"id": "seed_top", "smiles": "seed", "predicted_solubility": 0.50, "predicted_synthesizability": 0.50}],
    )

    state = GenerationIterationLoopAgent(config=state.config).run(state)

    assert round_counter["analysis"] == 1
    assert state.generation_iteration_loop_summary is not None
    assert state.generation_iteration_loop_summary["stop_reason"] == "max_rounds_reached"
    assert state.generation_iteration_loop_summary["rounds"][0]["resume_mode"] is True
    assert state.generation_iteration_loop_summary["rounds"][0]["iteration_run_dir"] == str(resume_dir)
    assert state.ranked[0]["id"] == "resumed_top"


def test_generation_iteration_loop_does_not_stop_just_because_action_queue_is_empty(tmp_path: Path, monkeypatch) -> None:
    round_counter = {"value": 0}

    class FakeIterationAgent:
        def __init__(self, config):
            self.config = config

        def run(self, state: RunState) -> RunState:
            if state.generation_iteration_reingest_manifest is None:
                round_counter["value"] += 1
                aggregate_path = state.run_dir / f"completed_{round_counter['value']}.json"
                aggregate_path.write_text(json.dumps([{"smiles": f"C{round_counter['value']}"}]), encoding="utf-8")
                state.generation_iteration_reingest_manifest = {
                    "aggregate_candidates_path": str(aggregate_path),
                    "completed_submission_count": 1,
                }
                state.generation_iteration_monitor = [{"status": "finished"}]
            return state

    class FakeAnalysisAgent:
        def __init__(self, config):
            self.config = config

        def run(self, state: RunState) -> RunState:
            metrics = {
                1: {"id": "round1_top", "smiles": "C1", "predicted_solubility": 0.62, "predicted_synthesizability": 0.61, "predicted_priority": 0.70},
                2: {"id": "round2_top", "smiles": "C2", "predicted_solubility": 0.74, "predicted_synthesizability": 0.73, "predicted_priority": 0.82},
            }
            state.ranked = [metrics[round_counter["value"]]]
            state.action_queue = []
            return state

    monkeypatch.setattr(
        "pz_agent.agents.generation_iteration_loop.AGENT_MAP",
        {
            "generation_iteration_handoff": FakeIterationAgent,
            "generation_iteration_submit": FakeIterationAgent,
            "generation_iteration_execute": FakeIterationAgent,
            "generation_iteration_monitor": FakeIterationAgent,
            "generation_iteration_recycle": FakeIterationAgent,
            "library_designer": FakeAnalysisAgent,
            "standardizer": FakeAnalysisAgent,
            "surrogate_screen": FakeAnalysisAgent,
            "knowledge_graph": FakeAnalysisAgent,
            "ranker": FakeAnalysisAgent,
            "graph_expansion": FakeAnalysisAgent,
        },
    )

    state = RunState(
        config={
            "generation": {
                "loop": {
                    "max_rounds": 2,
                    "convergence_tolerance": {"solubility": 0.01, "synthesizability": 0.01},
                    "taper_min_improvement": {"solubility": 0.005, "synthesizability": 0.005},
                }
            }
        },
        run_dir=tmp_path,
        ranked=[{"id": "seed_top", "smiles": "seed", "predicted_solubility": 0.50, "predicted_synthesizability": 0.50, "predicted_priority": 0.60}],
        action_queue=[],
    )

    state = GenerationIterationLoopAgent(config=state.config).run(state)

    assert state.generation_iteration_loop_summary is not None
    assert state.generation_iteration_loop_summary["completed_rounds"] == 2
    assert state.generation_iteration_loop_summary["stop_reason"] == "max_rounds_reached"
    assert state.ranked[0]["id"] == "round2_top"
    assert all((round_item.get("stop_reason") is None) for round_item in state.generation_iteration_loop_summary["rounds"])


def test_generation_iteration_recycle_writes_next_run_config(tmp_path: Path) -> None:
    aggregate_path = tmp_path / "generation_iteration_completed_candidates.json"
    aggregate_path.write_text(json.dumps([{"smiles": "CCN1c2ccc(OC)cc2Sc2cc(OC)ccc21"}]), encoding="utf-8")
    state = RunState(
        config={
            "generation": {
                "submit": {"remote_host": "grimm"},
                "recycle": {
                    "next_stages": ["library_designer", "standardizer", "surrogate_screen", "knowledge_graph", "ranker"],
                },
            },
            "screening": {"shortlist_size": 1},
            "pipeline": {"stages": ["library_designer"]},
        },
        run_dir=tmp_path,
        generation_iteration_reingest_manifest={
            "aggregate_candidates_path": str(aggregate_path),
            "completed_submission_count": 1,
        },
    )

    state = GenerationIterationRecycleAgent(config=state.config).run(state)

    next_cfg = (tmp_path / "generation_iteration_next_run.yaml").read_text()
    recycle_manifest = json.loads((tmp_path / "generation_iteration_recycle_manifest.json").read_text())
    assert "external_genmol_path" in next_cfg
    assert str(aggregate_path) in next_cfg
    assert recycle_manifest["completed_submission_count"] == 1


def test_generation_iteration_loop_stops_when_both_metrics_worsen(tmp_path: Path, monkeypatch) -> None:
    round_counter = {"value": 0}

    class FakeIterationAgent:
        def __init__(self, config):
            self.config = config

        def run(self, state: RunState) -> RunState:
            if state.generation_iteration_reingest_manifest is None:
                round_counter["value"] += 1
                aggregate_path = state.run_dir / "completed.json"
                aggregate_path.write_text(json.dumps([{"smiles": f"C{round_counter['value']}"}]), encoding="utf-8")
                state.generation_iteration_reingest_manifest = {
                    "aggregate_candidates_path": str(aggregate_path),
                    "completed_submission_count": 1,
                }
                state.generation_iteration_monitor = [{"status": "finished"}]
            return state

    class FakeAnalysisAgent:
        def __init__(self, config):
            self.config = config

        def run(self, state: RunState) -> RunState:
            metrics = {
                1: {"id": "round1_top", "smiles": "C1", "predicted_solubility": 0.72, "predicted_synthesizability": 0.71, "predicted_priority": 0.80},
                2: {"id": "round2_top", "smiles": "C2", "predicted_solubility": 0.70, "predicted_synthesizability": 0.69, "predicted_priority": 0.78},
            }
            state.ranked = [metrics[round_counter["value"]]]
            state.action_queue = [{"action_type": "generation_iteration", "candidate_id": metrics[round_counter['value']]['id']}]
            return state

    monkeypatch.setattr(
        "pz_agent.agents.generation_iteration_loop.AGENT_MAP",
        {
            "generation_iteration_handoff": FakeIterationAgent,
            "generation_iteration_submit": FakeIterationAgent,
            "generation_iteration_execute": FakeIterationAgent,
            "generation_iteration_monitor": FakeIterationAgent,
            "generation_iteration_recycle": FakeIterationAgent,
            "library_designer": FakeAnalysisAgent,
            "standardizer": FakeAnalysisAgent,
            "surrogate_screen": FakeAnalysisAgent,
            "knowledge_graph": FakeAnalysisAgent,
            "ranker": FakeAnalysisAgent,
            "graph_expansion": FakeAnalysisAgent,
        },
    )

    state = RunState(
        config={
            "generation": {
                "loop": {
                    "max_rounds": 4,
                    "convergence_tolerance": {"solubility": 0.01, "synthesizability": 0.01},
                    "taper_min_improvement": {"solubility": 0.005, "synthesizability": 0.005},
                }
            }
        },
        run_dir=tmp_path,
        ranked=[{"id": "seed_top", "smiles": "seed", "predicted_solubility": 0.50, "predicted_synthesizability": 0.50, "predicted_priority": 0.60}],
        action_queue=[{"action_type": "generation_iteration", "candidate_id": "seed_top"}],
    )

    state = GenerationIterationLoopAgent(config=state.config).run(state)

    assert state.generation_iteration_loop_summary is not None
    assert state.generation_iteration_loop_summary["completed_rounds"] == 2
    assert state.generation_iteration_loop_summary["stop_reason"] == "both_metrics_worsened"
    assert state.ranked[0]["id"] == "round2_top"
    summary_payload = json.loads((tmp_path / "generation_iteration_loop_summary.json").read_text())
    assert summary_payload["rounds"][0]["stop_reason"] is None
    assert summary_payload["rounds"][1]["delta"]["solubility"] == pytest.approx(-0.02)
    assert summary_payload["rounds"][1]["delta"]["synthesizability"] == pytest.approx(-0.02)
    assert summary_payload["rounds"][1]["stop_reason"] == "both_metrics_worsened"
