from __future__ import annotations

from pz_agent.agents.base import BaseAgent
from pz_agent.agents.library_designer import LibraryDesignerAgent
from pz_agent.agents.ranker import RankerAgent
from pz_agent.agents.standardizer import StandardizerAgent
from pz_agent.agents.structure_expansion import StructureExpansionAgent
from pz_agent.agents.surrogate_screen import SurrogateScreenAgent
from pz_agent.analysis.portfolio import assign_portfolio_buckets
from pz_agent.state import RunState



def _build_dossier(candidate: dict, prediction: dict | None, ranked_row: dict | None, portfolio_assignment: dict | None) -> dict:
    identity = candidate.get("identity") or {}
    structure_expansion = candidate.get("structure_expansion") or {}
    portfolio_assignment = portfolio_assignment or {}
    bucket = portfolio_assignment.get("proposal_bucket") or "explore"
    support_uncertainty = float(prediction.get("prediction_uncertainty", 0.25) if prediction else 0.25)
    attachment_sites = candidate.get("sites") or identity.get("attachment_sites") or []
    site_assignments = identity.get("site_assignments") or [
        {
            "site": site,
            "role_label": next((token for token in (identity.get("positional_tokens") or []) if site.lower() in token.lower()), None),
            "substituent_class": next((token for token in (identity.get("decoration_tokens") or [])), None),
        }
        for site in attachment_sites
    ]
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
            "attachment_sites": attachment_sites,
            "substituent_descriptors": identity.get("decoration_tokens") or [],
            "site_role_labels": identity.get("positional_tokens") or [],
            "attachment_summary": identity.get("attachment_summary") or [],
            "substituent_fragments": identity.get("substituent_fragments") or [],
            "site_assignments": site_assignments,
            "substitution_pattern": identity.get("substitution_pattern"),
            "electronic_bias": identity.get("electronic_bias"),
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
            "predicted_priority": ranked_row.get("predicted_priority") if ranked_row else None,
            "sa_score": prediction.get("sa_score") if prediction else None,
            "route_score": prediction.get("route_score") if prediction else None,
            "novelty_ip_score": prediction.get("novelty_ip_score") if prediction else None,
            "uncertainty": support_uncertainty,
        },
        "evidence_hooks": {
            "query_hints": structure_expansion.get("query_hints") or [],
            "nearest_analogs": structure_expansion.get("similarity_hits") or [],
            "bridge_transform_references": ["quinone_to_phenothiazine_transfer"] if bucket == "bridge" else [],
            "likely_failure_modes": ["effect_not_transferred", "solubility_regression"] if bucket == "bridge" else [],
        },
        "portfolio_metadata": {
            "proposal_bucket": bucket,
            "selection_reason": portfolio_assignment.get("selection_reason") or f"macro_generation_{bucket}",
            "budget_fraction": portfolio_assignment.get("budget_fraction"),
            "exploration_score": portfolio_assignment.get("exploration_score", 1.0 if bucket in {"explore", "bridge", "falsify"} else 0.3),
            "exploitation_score": portfolio_assignment.get("exploitation_score", 1.0 if bucket == "exploit" else 0.4),
            "bridge_relevance": portfolio_assignment.get("bridge_relevance", 0.0),
        },
        "bridge_hypothesis": {
            "source_family": "chem_qn::quinone_abstract" if bucket == "bridge" else None,
            "target_family": "chem_pt::phenothiazine",
            "transfer_hypothesis": "quinone-inspired substituent logic may transfer redox-beneficial behavior into the phenothiazine scaffold" if bucket == "bridge" else None,
            "expected_transferred_effect": "redox_tuning" if bucket == "bridge" else None,
            "expected_failure_mode": "effect_not_transferred" if bucket == "bridge" else None,
            "transfer_confidence": portfolio_assignment.get("bridge_relevance", 0.0),
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

        portfolio_assignments = assign_portfolio_buckets(
            [
                {**candidate, "ranked_row": ranked_map.get(candidate.get("id"))}
                for candidate in (state.library_clean or [])
            ],
            budgets=(self.config.get("portfolio") or {}).get("budgets"),
        )
        portfolio_map = {item["candidate_id"]: item for item in portfolio_assignments}

        for candidate in (state.library_clean or []):
            dossier = _build_dossier(candidate, prediction_map.get(candidate.get("id")), ranked_map.get(candidate.get("id")), portfolio_map.get(candidate.get("id")))
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
