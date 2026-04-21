from __future__ import annotations

from pz_agent.simulation.backends.atomisticskills import AtomisticSkillsBackend
from pz_agent.simulation.backends.htvs import HtvsBackend


def get_simulation_backend(name: str):
    normalized = (name or "").strip().lower()
    if normalized in {"atomisticskills", "atomisticskills_orca", "orca_slurm", "orca_remote"}:
        return AtomisticSkillsBackend()
    if normalized in {"htvs", "htvs_orca", "htvs_supercloud"}:
        return HtvsBackend()
    raise ValueError(f"Unsupported simulation backend: {name}")
