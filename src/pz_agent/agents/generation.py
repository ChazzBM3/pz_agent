from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.agents.library_designer import LibraryDesignerAgent
from pz_agent.agents.ranker import RankerAgent
from pz_agent.agents.standardizer import StandardizerAgent
from pz_agent.agents.structure_expansion import StructureExpansionAgent
from pz_agent.agents.surrogate_screen import SurrogateScreenAgent
from pz_agent.state import RunState


DEFAULT_BUCKETS = ("exploit", "explore", "bridge", "falsify")



def _portfolio_bucket(index: int) -> str:
    return DEFAULT_BUCKETS[index % len(DEFAULT_BUCKETS)]



def _build_dossier(candidate: dict, prediction: dict | None, ranked_row: dict | None, index: int) -> dict:
    identity = candidate.get("identity") or {}
    structure_expansion = candidate.get("structure_expansion") or {}
    bucket = _portfolio_bucket(index)
    support_uncertainty = float(prediction.get("prediction_uncertainty", 0.25) if prediction else 0.25)
    dossier = {
        "candidate_id": candidate.get("id"),
        "identity": {
            "canonical_smiles": candidate.get("smiles") or identity.get("canonical_smiles"),
            "inchikey": identity.get("inchikey"),
            "source": candidate.get("generation_engine") or "generation_agent",
            "generation_batch": 0,
            "family_tag": identity.get("scaffold") or "phenothiazine",
        },
        "scaffold_metadata": {
            "scaffold_family": identity.get("scaffold") or "phenothiazine",
            "attachment_sites": candidate.get("sites") or identity.get("attachment_sites") or [],
            "substituent_descriptors": identity.get("decoration_tokens") or [],
            "site_role_labels": identity.get("positional_tokens") or [],
        },
        "hypothesis": {
            "text": f"{candidate.get('id')} may improve phenothiazine screening objectives through its current substitution pattern.",
            "status": "open",
            "confidence": max(0.2, 1.0 - support_uncertainty),
        },
        "properties": {
            "predicted_oxidation_potential": prediction.get("predicted_oxidation_potential") if prediction else None,
            "predicted_reduction_potential": prediction.get("predicted_reduction_potential") if prediction else None,
            "predicted_solubility": prediction.get("predicted_solubility") if prediction else None,
            "predicted_synthesizability": prediction.get("predicted_synthesizability") if prediction else None,
            "uncertainty": support_uncertainty,
        },
        "evidence_hooks": {
            "query_hints": structure_expansion.get("query_hints") or [],
            "nearest_analogs": structure_expansion.get("similarity_hits") or [],
            "bridge_transform_references": [],
            "likely_failure_modes": [],
        },
        "portfolio_metadata": {
            "proposal_bucket": bucket,
            "selection_reason": f"macro_generation_{bucket}",
            "exploration_score": 1.0 if bucket in {"explore", "bridge", "falsify"} else 0.3,
            "exploitation_score": 1.0 if bucket == "exploit" else 0.4,
        },
        "ranking_snapshot": ranked_row or {},
    }
    return dossier


class GenerationAgent(BaseAgent):
    name = "generation_agent"

    def run(self, state: RunState) -> RunState:
        worker_sequence = [
            LibraryDesignerAgent(config=self.config),
            StandardizerAgent(config=self.config),
            StructureExpansionAgent(config=self.config),
            SurrogateScreenAgent(config=self.config),
            RankerAgent(config=self.config),
        ]

        for worker in worker_sequence:
            state = worker.run(state)

        prediction_map = {item.get("id"): item for item in (state.predictions or [])}
        ranked_map = {item.get("id"): item for item in (state.ranked or [])}
        dossiers = []
        hypotheses = []
        portfolio = []
        ranking_registry = []

        for idx, candidate in enumerate(state.library_clean or []):
            dossier = _build_dossier(candidate, prediction_map.get(candidate.get("id")), ranked_map.get(candidate.get("id")), idx)
            dossiers.append(dossier)
            hypotheses.append({"candidate_id": dossier["candidate_id"], **dossier["hypothesis"]})
            portfolio.append({"candidate_id": dossier["candidate_id"], **dossier["portfolio_metadata"]})
            ranking_registry.append({"candidate_id": dossier["candidate_id"], "ranking_snapshot": dossier["ranking_snapshot"]})

        state.dossier_registry = dossiers
        state.hypothesis_registry = hypotheses
        state.portfolio_registry = portfolio
        state.ranking_registry = ranking_registry
        state.log(f"GenerationAgent assembled {len(dossiers)} candidate dossiers across macro proposal buckets")
        return state
