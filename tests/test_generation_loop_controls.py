from pz_agent.generation_loop_controls import build_loop_controls


def test_build_loop_controls_uses_config_defaults() -> None:
    controls = build_loop_controls(
        config={
            "screening": {"primary_objectives": ["solubility"]},
            "generation": {
                "loop": {
                    "convergence_tolerance": {"solubility": 0.02, "synthesizability": 0.01},
                    "taper_min_improvement": {"solubility": 0.01, "synthesizability": 0.005},
                }
            },
        }
    )

    assert controls == {
        "primary_objectives": ["solubility"],
        "convergence_tolerance": {"solubility": 0.02, "synthesizability": 0.01},
        "taper_min_improvement": {"solubility": 0.01, "synthesizability": 0.005},
    }


def test_build_loop_controls_normalizes_overrides() -> None:
    controls = build_loop_controls(
        config={"screening": {"primary_objectives": ["synthesizability", "solubility"]}},
        primary_objectives=["solubility", "solubility", "bogus"],
        convergence_tolerance={"solubility": "0.03"},
        taper_min_improvement={"synthesizability": 0.02},
    )

    assert controls == {
        "primary_objectives": ["solubility"],
        "convergence_tolerance": {"solubility": 0.03, "synthesizability": 0.01},
        "taper_min_improvement": {"solubility": 0.0, "synthesizability": 0.02},
    }
