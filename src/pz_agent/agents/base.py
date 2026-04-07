from __future__ import annotations

from pz_agent.state import RunState


class BaseAgent:
    name = "base"

    def __init__(self, config: dict):
        self.config = config

    def run(self, state: RunState) -> RunState:
        raise NotImplementedError
