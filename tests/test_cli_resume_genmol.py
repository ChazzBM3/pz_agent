from __future__ import annotations

import sys
from pathlib import Path

import yaml

from pz_agent import cli


def test_resume_genmol_loop_cli_writes_resume_config_and_runs_pipeline(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "base.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "project": {"name": "resume-test"},
                "generation": {"loop": {"max_rounds": 3}},
                "pipeline": {"stages": ["library_designer", "generation_iteration_loop", "reporter"]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    iteration_run_dir = tmp_path / "run" / "generation_iteration_loop" / "round_02_iteration"
    calls: list[dict[str, object]] = []

    def fake_run_pipeline(*, config_path: str | Path, run_dir: str | Path):
        calls.append({"config_path": Path(config_path), "run_dir": Path(run_dir)})
        return None

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pz-agent",
            "resume-genmol-loop",
            str(config_path),
            "--run-dir",
            str(run_dir),
            "--iteration-run-dir",
            str(iteration_run_dir),
            "--max-rounds",
            "2",
        ],
    )

    cli.main()

    assert calls == [{"config_path": run_dir / "generation_iteration_resume_config.yaml", "run_dir": run_dir}]
    resume_cfg = yaml.safe_load((run_dir / "generation_iteration_resume_config.yaml").read_text())
    assert resume_cfg["generation"]["loop"]["resume_iteration_run_dir"] == str(iteration_run_dir)
    assert resume_cfg["generation"]["loop"]["max_rounds"] == 2
    assert resume_cfg["pipeline"]["stages"] == ["generation_iteration_loop", "reporter"]
