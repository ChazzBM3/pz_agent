from __future__ import annotations

from urllib.parse import urlparse


EVIDENCE_TIER_WEIGHTS = {
    "tier_A_direct_pt": 1.00,
    "tier_B_broader_pt": 0.80,
    "tier_C_adjacent_scaffold": 0.65,
    "tier_D_quinone_teacher": 0.60,
    "tier_E_simulation": 0.85,
    "tier_F_metadata_weak": 0.30,
}

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.kg.retrieval import attach_critique_placeholders, build_candidate_queries, synthesize_evidence_from_queries
from pz_agent.kg.rag import RetrievalQuery, retrieve_context
from pz_agent.search.backends import get_search_backend
from pz_agent.state import RunState


PROPERTY_KEYWORDS = {
    "solubility": ["solubility", "soluble", "high-concentration", "concentration"],
    "synthesizability": ["synthesis", "synthetic", "synthesizability", "prepared", "route", "derivatization"],
    "instability": ["unstable", "instability", "decomposition", "degrade"],
    "oxidation_potential": ["oxidation potential", "oxidation", "anodic", "ionization potential"],
    "reduction_potential": ["reduction potential", "reduction", "cathodic", "electron affinity"],
    "electrochemistry": ["redox", "electrochemical", "voltammetry", "solvation", "reorganization"],
}


PROPERTY_SIGNAL_MAP = {
    "solubility": "supports_solubility",
    "synthesizability": "supports_synthesizability",
    "oxidation_potential": "supports_oxidation_potential",
    "reduction_potential": "supports_reduction_potential",
    "instability": "warns_instability",
}



def _extract_property_mentions(text: str) -> list[str]:
    hits: list[str] = []
    lowered = text.lower()
    for property_name, keywords in PROPERTY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            hits.append(property_name)
    return hits

REVIEW_HINTS = ("review", "progress", "perspective", "overview")
BACKGROUND_HINTS = ("platform", "editor", "visualization", "analysis platform")

CHEMISTRY_KEYWORDS = {
    "phenothiazine",
    "molecule",
    "molecular",
    "compound",
    "redox",
    "oxidation",
    "reduction",
    "solvation",
    "reorganization",
    "electrochem",
    "electrochemical",
    "voltammetry",
    "battery",
    "electrolyte",
    "synthesis",
    "synthetic",
    "chemistry",
    "journal",
    "doi",
}

TRUSTED_CHEMISTRY_HOSTS = (
    "pubs.acs.org",
    "sciencedirect.com",
    "wiley.com",
    "pubmed.ncbi.nlm.nih.gov",
    "doi.org",
    "chemrxiv.org",
    "pubchem.ncbi.nlm.nih.gov",
    "scifinder",
)

BLOCKED_HOST_FRAGMENTS = (
    "google.",
    "ikea.",
    "babypark.",
    "beliani.",
    "bol.com",
    "beslist.",
    "claude.ai",
    "chatgpt.com",
    "commentcamarche.com",
    "drugs.com",
    "rxlist.com",
    "medicinenet.com",
    "simit",
)

POSITIVE_RELEVANCE_TERMS = (
    "phenothiaz",
    "redox",
    "oxidation",
    "reduction",
    "electrochem",
    "electrochemical",
    "voltammetry",
    "battery",
    "electrolyte",
    "solubility",
    "nonaqueous",
    "flow battery",
)

NEGATIVE_RELEVANCE_TERMS = (
    "antimicrobial",
    "leishmania",
    "liver disease",
    "mycobacterium",
    "dna",
    "oligodeoxynucleotide",
    "bioimaging",
    "hydrogel",
    "chemosensor",
    "enzyme",
    "cyp1a",
    "chagas",
    "photocatal",
    "organophotoredox",
    "semipinacol",
    "dye-sensitized solar cell",
    "nanomedicine",
    "redox polymer",
    "polymer",
    "peptide",
    "lysine",
    "dendrimer",
)


def _infer_evidence_profile(title: str | None, snippet: str | None, url: str | None, match_type: str | None = None) -> dict[str, object]:
    text = " ".join(part for part in [title or "", snippet or "", url or ""] if part).lower()
    if any(token in text for token in ["quinone", "anthraquinone", "benzoquinone", "naphthoquinone"]):
        tier = "tier_D_quinone_teacher"
        source_family = "QN"
    elif any(token in text for token in ["phenoxazine", "phenazine", "triarylamine"]):
        tier = "tier_C_adjacent_scaffold"
        source_family = "adjacent"
    elif any(token in text for token in ["patent", "vendor", "pubchem", "openalex", "supplier"]):
        tier = "tier_F_metadata_weak"
        source_family = "mixed"
    elif any(token in text for token in ["flow battery", "electrolyte", "cycling", "charged-state solubility", "nonaqueous redox flow"]):
        tier = "tier_A_direct_pt"
        source_family = "PT"
    elif "phenothiaz" in text:
        tier = "tier_B_broader_pt"
        source_family = "PT"
    else:
        tier = "tier_F_metadata_weak"
        source_family = "mixed"

    identity_confidence = 1.0 if match_type == "exact" else 0.8 if match_type == "analog" else 0.55
    condition_similarity = 0.9 if any(token in text for token in ["nonaqueous", "electrolyte", "flow battery", "acetonitrile"]) else 0.7
    measurement_quality = 0.85 if any(token in text for token in ["measured", "voltammetry", "electrochemical", "cycling", "solubility"]) else 0.65
    modality_confidence = 0.9
    recency_modifier = 1.0
    source_reliability = 0.9 if url and any(host in (urlparse(url).netloc or "").lower() for host in TRUSTED_CHEMISTRY_HOSTS) else 0.65
    base_weight = EVIDENCE_TIER_WEIGHTS[tier]
    final_weight = base_weight * condition_similarity * identity_confidence * measurement_quality * modality_confidence * recency_modifier * source_reliability

    return {
        "evidence_tier": tier,
        "source_family": source_family,
        "source_type": "paper",
        "modality": "text",
        "extraction_method": "search_parser",
        "condition_similarity": round(condition_similarity, 3),
        "identity_confidence": round(identity_confidence, 3),
        "measurement_quality": round(measurement_quality, 3),
        "modality_confidence": round(modality_confidence, 3),
        "recency_modifier": round(recency_modifier, 3),
        "source_reliability": round(source_reliability, 3),
        "base_evidence_weight": round(base_weight, 3),
        "final_evidence_weight": round(final_weight, 3),
    }



def _classify_match_type(note: dict, title: str | None, snippet: str | None, url: str | None) -> str:
    identity = note.get("identity", {}) or {}
    candidate_id = str(note.get("candidate_id") or "").lower()
    haystack = " ".join(part for part in [title or "", snippet or "", url or ""] if part).lower()

    candidate_core = str(identity.get("core_detected") or identity.get("scaffold") or "").lower()
    if candidate_core == "phenothiazine" and any(core in haystack for core in ["phenoxazine", "thianthrene"]):
        return "unknown"
    if candidate_core == "phenoxazine" and "phenothiazine" in haystack:
        return "unknown"
    if candidate_core == "thianthrene" and "phenothiazine" in haystack:
        return "unknown"

    exact_tokens = [
        candidate_id,
        str(identity.get("name") or "").lower(),
        str(identity.get("canonical_smiles") or "").lower(),
        str(identity.get("iupac_name") or "").lower(),
    ]
    exact_tokens = [token for token in exact_tokens if token and len(token) > 4]
    if any(token and token in haystack for token in exact_tokens):
        return "exact"

    analog_tokens = [
        candidate_core,
        str(identity.get("scaffold") or "").lower(),
        *(str(t).lower() for t in (identity.get("decoration_tokens") or [])),
        *(str(t).replace("frag:", "").lower() for t in (identity.get("substituent_fragments") or [])),
    ]
    analog_tokens = [token for token in analog_tokens if token and len(token) > 2]

    analog_hits = sum(1 for token in analog_tokens if token in haystack)
    if analog_hits >= 2:
        return "analog"
    if candidate_core and candidate_core in haystack and any(term in haystack for term in ["solubility", "redox", "oxidation", "reduction", "electrochemical", "electrolyte", "battery", "voltammetry"]):
        return "analog"
    return "unknown"



def _relevance_score(title: str | None, snippet: str | None, url: str | None) -> float:
    host = (urlparse(url).netloc or "").lower() if url else ""
    text = " ".join(part for part in [title or "", snippet or "", host] if part).lower()
    score = 0.0
    if any(core in text for core in ["phenothiaz", "thianthren", "phenoxazin"]):
        score += 3.0
    for term in POSITIVE_RELEVANCE_TERMS:
        if term in text:
            score += 1.0
    for term in NEGATIVE_RELEVANCE_TERMS:
        if term in text:
            score -= 2.0
    if any(trusted in host for trusted in TRUSTED_CHEMISTRY_HOSTS):
        score += 0.5
    if _is_review_or_background_hit(title, snippet):
        score -= 0.5
    return score



def _is_relevant_chemistry_result(title: str | None, snippet: str | None, url: str | None) -> bool:
    host = (urlparse(url).netloc or "").lower() if url else ""
    if any(fragment in host for fragment in BLOCKED_HOST_FRAGMENTS):
        return False
    text = " ".join(part for part in [title or "", snippet or "", host] if part).lower()
    keyword_hits = sum(1 for keyword in CHEMISTRY_KEYWORDS if keyword in text)
    has_core = any(core in text for core in ["phenothiaz", "thianthren", "phenoxazin"])
    has_property_context = any(token in text for token in ["redox", "oxidation", "reduction", "electrochem", "electrochemical", "solubility", "electrolyte", "battery", "voltammetry"])
    off_target_context = any(token in text for token in ["photocatal", "organophotoredox", "semipinacol", "solar cell", "nanomedicine", "polymer", "peptide", "lysine", "dendrimer"])
    score = _relevance_score(title, snippet, url)
    if off_target_context and not any(token in text for token in ["flow battery", "electrolyte", "solubility"]):
        return False
    if any(trusted in host for trusted in TRUSTED_CHEMISTRY_HOSTS):
        return score >= 4.5 and has_core and has_property_context
    return score >= 5.0 and has_core and has_property_context and keyword_hits >= 3


def _is_review_or_background_hit(title: str | None, snippet: str | None) -> bool:
    text = " ".join(part for part in [title or "", snippet or ""] if part).lower()
    if any(token in text for token in BACKGROUND_HINTS):
        return True
    return any(token in text for token in REVIEW_HINTS)


def _infer_evidence_tier(signals: dict) -> str:
    if int(signals.get("exact_match_hits", 0) or 0) > 0:
        return "candidate"
    if int(signals.get("analog_match_hits", 0) or 0) > 0:
        return "analog"
    if int(signals.get("patent_hit_count", 0) or 0) > 0:
        return "patent"
    if int(signals.get("scholarly_hit_count", 0) or 0) > 0 or int(signals.get("property_aligned_hits", 0) or 0) > 0:
        return "analog"
    if int(signals.get("review_hits", 0) or 0) > 0:
        return "general_review"
    if int(signals.get("broad_scaffold_hits", 0) or 0) > 0:
        return "scaffold"
    return "candidate"


def _apply_multimodal_judgments(note: dict) -> dict:
    signals = dict(note.get("signals", {}))
    multimodal_bundle = note.get("multimodal_rerank") or {}
    judgments = []
    exact_bonus = 0
    analog_bonus = 0
    support_bonus = 0.0
    contradiction_penalty = 0.0
    property_bonus = 0
    human_review_flags = 0

    for bundle in multimodal_bundle.get("bundles") or []:
        judgment = bundle.get("gemma_judgment") or {}
        if not judgment:
            continue
        judgments.append(judgment)
        label = str(judgment.get("match_label") or "unknown").lower()
        relevance = str(judgment.get("property_relevance") or "unknown").lower()
        confidence = str(judgment.get("confidence") or "unknown").lower()
        needs_review = bool(judgment.get("needs_human_review", False))
        if needs_review:
            human_review_flags += 1
        conf_weight = {"high": 1.0, "medium": 0.6, "low": 0.25}.get(confidence, 0.2)
        if label == "exact":
            exact_bonus += 1
            support_bonus += 0.7 * conf_weight
        elif label == "analog":
            analog_bonus += 1
            support_bonus += 0.35 * conf_weight
        elif label in {"unrelated", "negative"}:
            contradiction_penalty += 0.5 * conf_weight
        if relevance not in {"unknown", "none", "irrelevant"}:
            property_bonus += 1
            support_bonus += 0.1 * conf_weight

    signals["exact_match_hits"] = int(signals.get("exact_match_hits", 0) or 0) + exact_bonus
    signals["analog_match_hits"] = int(signals.get("analog_match_hits", 0) or 0) + analog_bonus
    signals["property_aligned_hits"] = int(signals.get("property_aligned_hits", 0) or 0) + property_bonus
    signals["support_score"] = float(signals.get("support_score", 0.0) or 0.0) + support_bonus
    signals["contradiction_score"] = float(signals.get("contradiction_score", 0.0) or 0.0) + contradiction_penalty
    signals["multimodal_review_flags"] = int(signals.get("multimodal_review_flags", 0) or 0) + human_review_flags
    note["signals"] = signals
    note.setdefault("support_mix", {})
    return note


def _summarize_live_signals(note: dict, evidence: list[dict]) -> dict:
    signals = dict(note.get("signals", {}))
    exact_hits = 0
    analog_hits = 0
    support_score = float(signals.get("support_score", 0.0) or 0.0)
    contradiction_score = float(signals.get("contradiction_score", 0.0) or 0.0)
    broad_scaffold_hits = int(signals.get("broad_scaffold_hits", 0) or 0)
    property_aligned_hits = int(signals.get("property_aligned_hits", 0) or 0)
    review_hits = int(signals.get("review_hits", 0) or 0)
    patent_hit_count = int(signals.get("patent_hit_count", 0) or 0)
    scholarly_hit_count = int(signals.get("scholarly_hit_count", 0) or 0)
    property_support = dict(signals.get("property_support") or {})

    for item in evidence:
        title = str(item.get("title") or "")
        snippet = str(item.get("snippet") or "")
        match_type = item.get("match_type")
        text = " ".join([title, snippet]).lower()
        property_mentions = _extract_property_mentions(text)
        property_mentions = [name for name in property_mentions if name != "electrochemistry"]
        has_echem = "electrochemistry" in _extract_property_mentions(text)
        property_aligned = bool(property_mentions or has_echem)
        is_review = _is_review_or_background_hit(title, snippet)

        item["property_mentions"] = property_mentions

        if is_review:
            review_hits += 1

        if match_type == "exact":
            exact_hits += 1
            support_score += 0.8 if property_aligned else 0.25
        elif match_type == "analog":
            analog_hits += 1
            support_score += 0.35 if property_aligned else 0.08
        elif "phenothiazine" in text:
            broad_scaffold_hits += 1
            support_score += 0.01 if is_review else 0.02

        if property_aligned and not is_review:
            property_aligned_hits += 1

        for property_name in property_mentions:
            property_support[property_name] = int(property_support.get(property_name, 0) or 0) + 1
            signal_name = PROPERTY_SIGNAL_MAP.get(property_name)
            if signal_name:
                signals[signal_name] = True
            if property_name == "instability":
                contradiction_score += 0.5
            else:
                support_score += 0.06

    signals.update(
        {
            "exact_match_hits": int(signals.get("exact_match_hits", 0) or 0) + exact_hits,
            "analog_match_hits": int(signals.get("analog_match_hits", 0) or 0) + analog_hits,
            "broad_scaffold_hits": broad_scaffold_hits,
            "property_aligned_hits": property_aligned_hits,
            "review_hits": review_hits,
            "patent_hit_count": patent_hit_count,
            "scholarly_hit_count": scholarly_hit_count,
            "support_score": support_score,
            "contradiction_score": contradiction_score,
            "property_support": property_support,
        }
    )
    signals.setdefault("supports_solubility", False)
    signals.setdefault("supports_synthesizability", False)
    signals.setdefault("supports_oxidation_potential", False)
    signals.setdefault("supports_reduction_potential", False)
    signals.setdefault("warns_instability", False)
    return signals



def _live_search_note(note: dict, backend_name: str, count: int) -> dict:
    backend = get_search_backend(backend_name)
    evidence = []
    seen_urls: set[str] = set()
    media_evidence = []
    for idx, query in enumerate(note.get("queries", [])):
        try:
            hits = backend.search(query, count=count)
        except Exception:
            hits = []
        for hit_idx, hit in enumerate(hits):
            if not _is_relevant_chemistry_result(hit.title, hit.snippet, hit.url):
                continue
            url_key = str(hit.url or hit.title or f"{idx}:{hit_idx}")
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            match_type = _classify_match_type(note, hit.title, hit.snippet, hit.url)
            profile = _infer_evidence_profile(hit.title, hit.snippet, hit.url, match_type=match_type)
            evidence.append(
                {
                    "id": f"evidence::{note['candidate_id']}::{idx}::{hit_idx}",
                    "kind": "web_result",
                    "query": query,
                    "title": hit.title,
                    "url": hit.url,
                    "snippet": hit.snippet,
                    "match_type": match_type,
                    "relevance_score": _relevance_score(hit.title, hit.snippet, hit.url),
                    **profile,
                    "source_tags": {
                        "source_type": profile["source_type"],
                        "source_family": profile["source_family"],
                        "evidence_tier": profile["evidence_tier"],
                        "modality": profile["modality"],
                        "extraction_method": profile["extraction_method"],
                    },
                    "provenance": {
                        "source_type": backend.name,
                        "query": query,
                        "confidence": hit.confidence,
                        "evidence_level": "web_search",
                    },
                }
            )
        media_evidence.append(
            {
                "id": f"media::{note['candidate_id']}::{idx}",
                "kind": "query_trace",
                "query": query,
                "caption": f"Search trace for {query}",
                "source_url": None,
                "image_path": None,
                "media_type": "search_trace",
                "provenance": {
                    "source_type": backend.name,
                    "query": query,
                    "confidence": None,
                },
            }
        )
    evidence.sort(key=lambda item: float(item.get("relevance_score", 0.0)), reverse=True)
    note["evidence"] = evidence
    note["media_evidence"] = media_evidence
    note["signals"] = _summarize_live_signals(note, evidence)
    note["evidence_tier"] = _infer_evidence_tier(note["signals"])
    support_mix = {
        "direct_pt_support": round(sum(float(item.get("final_evidence_weight", 0.0) or 0.0) for item in evidence if item.get("evidence_tier") == "tier_A_direct_pt"), 3),
        "pt_scaffold_support": round(sum(float(item.get("final_evidence_weight", 0.0) or 0.0) for item in evidence if item.get("evidence_tier") == "tier_B_broader_pt"), 3),
        "adjacent_scaffold_support": round(sum(float(item.get("final_evidence_weight", 0.0) or 0.0) for item in evidence if item.get("evidence_tier") == "tier_C_adjacent_scaffold"), 3),
        "quinone_bridge_support": round(sum(float(item.get("final_evidence_weight", 0.0) or 0.0) for item in evidence if item.get("evidence_tier") == "tier_D_quinone_teacher"), 3),
        "simulation_support": round(sum(float(item.get("final_evidence_weight", 0.0) or 0.0) for item in evidence if item.get("evidence_tier") == "tier_E_simulation"), 3),
        "metadata_support": round(sum(float(item.get("final_evidence_weight", 0.0) or 0.0) for item in evidence if item.get("evidence_tier") == "tier_F_metadata_weak"), 3),
        "contradiction_count": 1 if bool(note["signals"].get("warns_instability")) else 0,
        "transferability_score": round(min(1.0, 0.2 + sum(float(item.get("final_evidence_weight", 0.0) or 0.0) for item in evidence) / 5.0), 3),
    }
    note["support_mix"] = support_mix
    note["status"] = "live_web_results" if evidence else "live_web_no_results"
    note["summary"] = f"Live web critique collected {len(evidence)} evidence hits via {backend.name}."
    return note


def _queue_evidence_query_hints(state: RunState) -> tuple[dict[str, list[str]], list[dict]]:
    hints: dict[str, list[str]] = {}
    consumed_actions: list[dict] = []
    for item in state.action_queue or []:
        if item.get("action_type") != "evidence_query":
            continue
        candidate_id = str(item.get("candidate_id") or "")
        payload = item.get("payload") or {}
        belief_status = str(payload.get("belief_status") or "belief").replace("_", " ")
        confidence = payload.get("confidence")
        confidence_text = f" confidence {confidence}" if confidence is not None else ""
        hint = f"phenothiazine derivative {belief_status} literature evidence{confidence_text}".strip()
        hints.setdefault(candidate_id, [])
        if hint not in hints[candidate_id]:
            hints[candidate_id].append(hint)
        consumed_actions.append(item)
    return hints, consumed_actions


class CritiqueAgent(BaseAgent):
    name = "critique"

    def run(self, state: RunState) -> RunState:
        search_fields = list(self.config.get("critique", {}).get("search_fields", []))
        enable_web_search = bool(self.config.get("critique", {}).get("enable_web_search", True))
        max_candidates = int(self.config.get("critique", {}).get("max_candidates", 10))
        queue_hints, consumed_actions = _queue_evidence_query_hints(state)
        critique_notes = attach_critique_placeholders(
            shortlist=state.shortlist or [],
            enable_web_search=enable_web_search,
            max_candidates=max_candidates,
            search_fields=search_fields,
            graph_path=state.knowledge_graph_path,
        )

        if queue_hints:
            augmented_notes = []
            for note, item in zip(critique_notes, (state.shortlist or [])[:max_candidates], strict=False):
                candidate_id = note.get("candidate_id")
                extra_hints = queue_hints.get(candidate_id, [])
                if extra_hints:
                    retrieval_query = RetrievalQuery(
                        candidate_id=item["id"],
                        properties_of_interest=list(search_fields or []),
                    )
                    kg_context = retrieve_context(state.knowledge_graph_path, retrieval_query)
                    merged_hints = list(kg_context.query_hints)
                    for hint in extra_hints:
                        if hint not in merged_hints:
                            merged_hints.append(hint)
                    note = dict(note)
                    note["queries"] = build_candidate_queries(item, search_fields=search_fields, query_hints=merged_hints)
                    note["action_queue_hints"] = extra_hints
                augmented_notes.append(note)
            critique_notes = augmented_notes

        backend_name = str(self.config.get("search", {}).get("backend", "stub"))
        count = int(self.config.get("search", {}).get("count", 5))
        multimodal_map = {item.get("candidate_id"): item for item in (state.multimodal_registry or [])}

        if enable_web_search and backend_name != "stub":
            critique_notes = [_live_search_note(note, backend_name=backend_name, count=count) for note in critique_notes]
            state.log(f"Critique agent collected live web evidence using {backend_name}")
        else:
            critique_notes = synthesize_evidence_from_queries(critique_notes)
            state.log("Critique agent prepared candidate evidence bundles with KG-derived context, targeted queries, and text/image placeholders")

        enriched_notes = []
        for note in critique_notes:
            note = dict(note)
            note["multimodal_rerank"] = multimodal_map.get(note.get("candidate_id"), {"candidate_id": note.get("candidate_id"), "bundles": [], "status": "empty"})
            note = _apply_multimodal_judgments(note)
            note["evidence_tier"] = _infer_evidence_tier(note.get("signals", {}))
            enriched_notes.append(note)

        action_outcomes = []
        for action in consumed_actions:
            candidate_id = action.get("candidate_id")
            matching_note = next((note for note in enriched_notes if note.get("candidate_id") == candidate_id), None)
            evidence_count = len((matching_note or {}).get("evidence") or [])
            action_outcomes.append(
                {
                    "candidate_id": candidate_id,
                    "action_type": action.get("action_type"),
                    "proposal_type": action.get("proposal_type"),
                    "proposal_reason": action.get("proposal_reason"),
                    "priority": action.get("priority"),
                    "critic_reason": action.get("critic_reason"),
                    "status": "consumed",
                    "result": "evidence_found" if evidence_count > 0 else "no_evidence_found",
                    "evidence_count": evidence_count,
                }
            )

        outcome_stats = dict(state.outcome_stats or {})
        by_action_type = dict(outcome_stats.get("by_action_type") or {})
        by_critic_reason = dict(outcome_stats.get("by_critic_reason") or {})
        by_proposal_type = dict(outcome_stats.get("by_proposal_type") or {})
        by_proposal_reason = dict(outcome_stats.get("by_proposal_reason") or {})
        for item in action_outcomes:
            action_type = str(item.get("action_type") or "")
            critic_reason = str(item.get("critic_reason") or "")
            proposal_type = str(item.get("proposal_type") or "")
            proposal_reason = str(item.get("proposal_reason") or "")
            success = 1 if item.get("result") == "evidence_found" else 0
            failure = 0 if success else 1

            type_bucket = dict(by_action_type.get(action_type) or {})
            type_bucket["success"] = int(type_bucket.get("success", 0)) + success
            type_bucket["failure"] = int(type_bucket.get("failure", 0)) + failure
            by_action_type[action_type] = type_bucket

            critic_bucket = dict(by_critic_reason.get(critic_reason) or {})
            critic_bucket["success"] = int(critic_bucket.get("success", 0)) + success
            critic_bucket["failure"] = int(critic_bucket.get("failure", 0)) + failure
            by_critic_reason[critic_reason] = critic_bucket

            proposal_type_bucket = dict(by_proposal_type.get(proposal_type) or {})
            proposal_type_bucket["success"] = int(proposal_type_bucket.get("success", 0)) + success
            proposal_type_bucket["failure"] = int(proposal_type_bucket.get("failure", 0)) + failure
            by_proposal_type[proposal_type] = proposal_type_bucket

            proposal_reason_bucket = dict(by_proposal_reason.get(proposal_reason) or {})
            proposal_reason_bucket["success"] = int(proposal_reason_bucket.get("success", 0)) + success
            proposal_reason_bucket["failure"] = int(proposal_reason_bucket.get("failure", 0)) + failure
            by_proposal_reason[proposal_reason] = proposal_reason_bucket
        outcome_stats["by_action_type"] = by_action_type
        outcome_stats["by_critic_reason"] = by_critic_reason
        outcome_stats["by_proposal_type"] = by_proposal_type
        outcome_stats["by_proposal_reason"] = by_proposal_reason

        state.critique_notes = enriched_notes
        state.action_outcomes = action_outcomes
        state.outcome_stats = outcome_stats
        write_json(state.run_dir / "critique_notes.json", critique_notes)
        write_json(state.run_dir / "action_outcomes.json", action_outcomes)
        write_json(state.run_dir / "outcome_stats.json", outcome_stats)
        return state
