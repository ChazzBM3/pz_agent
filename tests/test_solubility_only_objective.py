from pz_agent.analysis.pareto import compute_placeholder_pareto
from pz_agent.agents.graph_expansion import GraphExpansionAgent
from pz_agent.agents.generation_iteration_loop import GenerationIterationLoopAgent
from pz_agent.state import RunState


def test_compute_placeholder_pareto_supports_solubility_only_primary_objective() -> None:
    ranked = compute_placeholder_pareto(
        [
            {"id": "cand-a", "predicted_synthesizability": 0.95, "predicted_solubility": 0.40},
            {"id": "cand-b", "predicted_synthesizability": 0.20, "predicted_solubility": 0.80},
        ],
        primary_objectives=["solubility"],
    )

    assert ranked[0]["id"] == "cand-b"
    assert ranked[0]["ranking_rationale"]["primary_objectives"] == ["solubility"]
    assert ranked[0]["ranking_rationale"]["weights"] == {"solubility": 1.0}
    assert ranked[0]["predicted_synthesizability"] == 0.20


def test_generation_iteration_loop_uses_primary_objectives_for_stop_checks() -> None:
    delta = {"solubility": -0.02, "synthesizability": 0.30}
    tolerance = {"solubility": 0.005, "synthesizability": 0.005}

    assert GenerationIterationLoopAgent._all_primary_metrics_worsened(delta, tolerance, ["solubility"]) is True
    assert GenerationIterationLoopAgent._all_primary_metrics_worsened(delta, tolerance, ["solubility", "synthesizability"]) is False
    assert GenerationIterationLoopAgent._is_converged({"solubility": 0.003}, tolerance, ["solubility"]) is True


def test_generation_iteration_loop_resolves_controls_from_agent_payload() -> None:
    config = {
        "screening": {"primary_objectives": ["synthesizability", "solubility"]},
        "generation": {
            "loop": {
                "convergence_tolerance": {"solubility": 0.01, "synthesizability": 0.01},
                "taper_min_improvement": {"solubility": 0.005, "synthesizability": 0.005},
            }
        },
    }
    action_queue = [
        {
            "action_type": "generation_iteration",
            "candidate_id": "cand-1",
            "priority": 0.9,
            "payload": {
                "loop_controls": {
                    "primary_objectives": ["solubility"],
                    "convergence_tolerance": {"solubility": 0.02},
                    "taper_min_improvement": {"solubility": 0.01},
                }
            },
        }
    ]

    controls = GenerationIterationLoopAgent._resolve_loop_controls(config, action_queue)

    assert controls["source"] == "agent_payload"
    assert controls["candidate_id"] == "cand-1"
    assert controls["primary_objectives"] == ["solubility"]
    assert controls["convergence_tolerance"] == {"solubility": 0.02, "synthesizability": 0.01}
    assert controls["taper_min_improvement"] == {"solubility": 0.01, "synthesizability": 0.005}


def test_graph_expansion_emits_canonical_loop_controls_for_generation_actions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "pz_agent.agents.graph_expansion.summarize_generation_iteration_candidate",
        lambda *args, **kwargs: {
            "eligible": True,
            "priority": 0.81,
            "protocol": {},
            "candidate": {"smiles": "C1", "stable_identity_key": "cand-1"},
            "bridge_case_id": "bridge-1",
            "bridge_principles": ["solubilizing_handle"],
            "generation_batch_ids": ["batch-1"],
            "history": {},
            "transferability_score": 0.8,
            "support_score": 0.7,
            "contradiction_score": 0.0,
            "measurement_summary": {},
            "measurement_values": {},
        },
    )
    graph = {
        "nodes": [
            {"id": "cand-1", "type": "Candidate", "attrs": {"smiles": "C1", "stable_identity_key": "cand-1"}},
            {"id": "batch-1", "type": "GenerationBatch", "attrs": {"engine": "genmol_external", "metadata": {"mode": "genmol_conformer_generation"}}},
            {"id": "bridge-1", "type": "BridgeCase", "attrs": {"target_candidate_id": "cand-1", "transferability_score": 0.8, "next_action": "generation_prior", "bridge_principle_refs": ["solubilizing_handle"]}},
            {"id": "belief-1", "type": "BeliefState", "attrs": {"candidate_id": "cand-1", "status": "proposed", "confidence": 0.4}},
        ],
        "edges": [
            {"source": "cand-1", "target": "batch-1", "type": "GENERATED_BY_BATCH"},
        ],
    }
    graph_path = tmp_path / "kg.json"
    graph_path.write_text(__import__("json").dumps(graph), encoding="utf-8")

    state = RunState(
        config={
            "screening": {"primary_objectives": ["solubility"]},
            "generation": {"loop": {"convergence_tolerance": {"solubility": 0.02}, "taper_min_improvement": {"solubility": 0.01}}},
        },
        run_dir=tmp_path,
        knowledge_graph_path=graph_path,
    )

    updated = GraphExpansionAgent(config=state.config).run(state)

    generation_actions = [item for item in (updated.action_queue or []) if item.get("action_type") == "generation_iteration"]
    assert generation_actions
    assert generation_actions[0]["payload"]["loop_controls"] == {
        "primary_objectives": ["solubility"],
        "convergence_tolerance": {"solubility": 0.02, "synthesizability": 0.01},
        "taper_min_improvement": {"solubility": 0.01, "synthesizability": 0.0},
    }
