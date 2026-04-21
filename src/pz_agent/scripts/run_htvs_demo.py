from __future__ import annotations

import argparse
from pathlib import Path

from pz_agent.agents.simulation_check import SimulationCheckAgent
from pz_agent.agents.simulation_extract import SimulationExtractAgent
from pz_agent.agents.simulation_handoff import SimulationHandoffAgent
from pz_agent.agents.simulation_submit import SimulationSubmitAgent
from pz_agent.config import load_config
from pz_agent.io import ensure_dir, read_json
from pz_agent.state import RunState


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a minimal HTVS adapter demo pipeline")
    parser.add_argument("--config", required=True, help="Path to demo HTVS pipeline config")
    parser.add_argument("--run-dir", required=True, help="Run directory for artifacts")
    parser.add_argument("--shortlist", required=True, help="JSON shortlist payload")
    args = parser.parse_args()

    config = load_config(args.config)
    run_dir = Path(args.run_dir)
    ensure_dir(run_dir)
    shortlist = read_json(Path(args.shortlist))
    if not isinstance(shortlist, list):
        raise ValueError("Shortlist payload must be a JSON list")

    state = RunState(config=config, run_dir=run_dir, shortlist=shortlist)
    state.log("Initialized HTVS adapter demo state")

    for agent_cls in (SimulationHandoffAgent, SimulationSubmitAgent, SimulationCheckAgent, SimulationExtractAgent):
        agent = agent_cls(config=state.config)
        state.log(f"Running stage: {agent.name}")
        state = agent.run(state)

    print(f"HTVS adapter demo complete. Run dir: {state.run_dir}")


if __name__ == "__main__":
    main()
