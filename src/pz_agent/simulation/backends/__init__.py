from __future__ import annotations

from pz_agent.simulation.backends.atomisticskills import AtomisticSkillsBackend


def get_simulation_backend(name: str):
    normalized = (name or "").strip().lower()
    if normalized in {"atomisticskills", "atomisticskills_orca", "orca_slurm", "orca_remote"}:
        return AtomisticSkillsBackend()
    raise ValueError(f"Unsupported simulation backend: {name}")
