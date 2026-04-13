from __future__ import annotations

from urllib.parse import urlparse

from pz_agent.agents.base import BaseAgent
from pz_agent.agents.document_fetch import DocumentFetchAgent
from pz_agent.agents.figure_corpus import FigureCorpusAgent
from pz_agent.agents.multimodal_rerank import MultimodalRerankAgent
from pz_agent.agents.ocr_caption import OCRCaptionAgent
from pz_agent.agents.page_corpus import PageCorpusAgent
from pz_agent.agents.page_image_retrieval import PageImageRetrievalAgent
from pz_agent.agents.patent_retrieval import PatentRetrievalAgent
from pz_agent.agents.scholarly_retrieval import ScholarlyRetrievalAgent
from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.kg.retrieval import attach_critique_placeholders, synthesize_evidence_from_queries
from pz_agent.search.backends import get_search_backend
from pz_agent.state import RunState


PROPERTY_KEYWORDS = {
    "solubility": ["solubility", "soluble"],
    "synthesizability": ["synthesis", "synthetic", "synthesizability", "prepared", "route"],
    "instability": ["unstable", "instability", "decomposition", "degrade"],
    "electrochemistry": ["redox", "oxidation", "reduction", "electrochemical", "voltammetry", "solvation", "reorganization"],
}

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
)


def _classify_match_type(note: dict, title: str | None, snippet: str | None, url: str | None) -> str:
    identity = note.get("identity", {}) or {}
    candidate_id = str(note.get("candidate_id") or "").lower()
    haystack = " ".join(part for part in [title or "", snippet or "", url or ""] if part).lower()
    exact_tokens = [candidate_id, str(identity.get("name") or "").lower(), str(identity.get("canonical_smiles") or "").lower()]
    exact_tokens = [token for token in exact_tokens if token]
    if any(token and token in haystack for token in exact_tokens):
        return "exact"
    analog_tokens = [str(identity.get("scaffold") or "").lower(), *(str(t).lower() for t in (identity.get("decoration_tokens") or []))]
    analog_tokens = [token for token in analog_tokens if token and len(token) > 1]
    if any(token and token in haystack for token in analog_tokens):
        return "analog"
    return "unknown"



def _relevance_score(title: str | None, snippet: str | None, url: str | None) -> float:
    host = (urlparse(url).netloc or "").lower() if url else ""
    text = " ".join(part for part in [title or "", snippet or "", host] if part).lower()
    score = 0.0
    if "phenothiaz" in text:
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
    has_core = "phenothiaz" in text
    has_property_context = any(token in text for token in ["redox", "oxidation", "reduction", "electrochem", "electrochemical", "solubility", "electrolyte", "battery", "voltammetry"])
    score = _relevance_score(title, snippet, url)
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
    exact_bonus = 0
    analog_bonus = 0
    support_bonus = 0.0
    contradiction_penalty = 0.0
    property_bonus = 0
    human_review_flags = 0
    multimodal_support = 0.0
    multimodal_contradiction = 0.0
    multimodal_score_sum = 0.0
    multimodal_score_count = 0

    for bundle in multimodal_bundle.get("bundles") or []:
        judgment = bundle.get("gemma_judgment") or {}
        if not judgment:
            continue
        label = str(judgment.get("match_label") or "unknown").lower()
        relevance = str(judgment.get("property_relevance") or "unknown").lower()
        confidence = str(judgment.get("confidence") or "unknown").lower()
        needs_review = bool(judgment.get("needs_human_review", False))
        retrieval_score = float(bundle.get("retrieval_score") or 0.0)
        if needs_review:
            human_review_flags += 1
        conf_weight = {"high": 1.0, "medium": 0.6, "low": 0.25}.get(confidence, 0.2)
        weighted_conf = conf_weight * max(0.25, retrieval_score if retrieval_score > 0 else 0.5)
        multimodal_score_sum += retrieval_score
        multimodal_score_count += 1
        if label == "exact":
            exact_bonus += 1
            support_bonus += 0.8 * weighted_conf
            multimodal_support += weighted_conf
        elif label in {"analog", "possible"}:
            analog_bonus += 1 if label == "analog" else 0
            support_bonus += 0.45 * weighted_conf
            multimodal_support += 0.7 * weighted_conf
        elif label in {"unrelated", "negative"}:
            contradiction_penalty += 0.65 * weighted_conf
            multimodal_contradiction += weighted_conf
        if relevance not in {"unknown", "none", "irrelevant"}:
            property_bonus += 1
            support_bonus += 0.12 * weighted_conf

    signals["exact_match_hits"] = int(signals.get("exact_match_hits", 0) or 0) + exact_bonus
    signals["analog_match_hits"] = int(signals.get("analog_match_hits", 0) or 0) + analog_bonus
    signals["property_aligned_hits"] = int(signals.get("property_aligned_hits", 0) or 0) + property_bonus
    signals["support_score"] = float(signals.get("support_score", 0.0) or 0.0) + support_bonus
    signals["contradiction_score"] = float(signals.get("contradiction_score", 0.0) or 0.0) + contradiction_penalty
    signals["multimodal_review_flags"] = int(signals.get("multimodal_review_flags", 0) or 0) + human_review_flags
    signals["multimodal_support_score"] = float(signals.get("multimodal_support_score", 0.0) or 0.0) + multimodal_support
    signals["multimodal_contradiction_score"] = float(signals.get("multimodal_contradiction_score", 0.0) or 0.0) + multimodal_contradiction
    if multimodal_score_count > 0:
        signals["multimodal_mean_retrieval_score"] = multimodal_score_sum / multimodal_score_count
    note["signals"] = signals
    return note


def _summarize_live_signals(note: dict, evidence: list[dict]) -> dict:
    signals = dict(note.get("signals", {}))
    exact_hits = 0
    analog_hits = 0
    support_score = float(signals.get("support_score", 0.0) or 0.0)
    contradiction_score = float(signals.get("contradiction_score", 0.0) or 0.0)
    supports_solubility = bool(signals.get("supports_solubility"))
    supports_synth = bool(signals.get("supports_synthesizability"))
    warns_instability = bool(signals.get("warns_instability"))
    broad_scaffold_hits = int(signals.get("broad_scaffold_hits", 0) or 0)
    property_aligned_hits = int(signals.get("property_aligned_hits", 0) or 0)
    review_hits = int(signals.get("review_hits", 0) or 0)
    patent_hit_count = int(signals.get("patent_hit_count", 0) or 0)
    scholarly_hit_count = int(signals.get("scholarly_hit_count", 0) or 0)

    for item in evidence:
        title = str(item.get("title") or "")
        snippet = str(item.get("snippet") or "")
        match_type = item.get("match_type")
        text = " ".join([title, snippet]).lower()
        has_solubility = any(keyword in text for keyword in PROPERTY_KEYWORDS["solubility"])
        has_synth = any(keyword in text for keyword in PROPERTY_KEYWORDS["synthesizability"])
        has_echem = any(keyword in text for keyword in PROPERTY_KEYWORDS["electrochemistry"])
        property_aligned = has_solubility or has_synth or has_echem
        is_review = _is_review_or_background_hit(title, snippet)

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
        if has_solubility and not is_review:
            supports_solubility = True
            support_score += 0.06
        if has_synth and not is_review:
            supports_synth = True
            support_score += 0.06
        if any(keyword in text for keyword in PROPERTY_KEYWORDS["instability"]):
            warns_instability = True
            contradiction_score += 0.5

    signals.update(
        {
            "supports_solubility": supports_solubility,
            "supports_synthesizability": supports_synth,
            "warns_instability": warns_instability,
            "exact_match_hits": int(signals.get("exact_match_hits", 0) or 0) + exact_hits,
            "analog_match_hits": int(signals.get("analog_match_hits", 0) or 0) + analog_hits,
            "broad_scaffold_hits": broad_scaffold_hits,
            "property_aligned_hits": property_aligned_hits,
            "review_hits": review_hits,
            "patent_hit_count": patent_hit_count,
            "scholarly_hit_count": scholarly_hit_count,
            "support_score": support_score,
            "contradiction_score": contradiction_score,
        }
    )
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
    note["status"] = "live_web_results" if evidence else "live_web_no_results"
    note["summary"] = f"Live web critique collected {len(evidence)} evidence hits via {backend.name}."
    return note


class CritiqueAgent(BaseAgent):
    name = "critique_agent"

    def run(self, state: RunState) -> RunState:
        worker_sequence = [
            PatentRetrievalAgent(config=self.config),
            ScholarlyRetrievalAgent(config=self.config),
            PageCorpusAgent(config=self.config),
            DocumentFetchAgent(config=self.config),
            FigureCorpusAgent(config=self.config),
            OCRCaptionAgent(config=self.config),
            PageImageRetrievalAgent(config=self.config),
            MultimodalRerankAgent(config=self.config),
        ]
        for worker in worker_sequence:
            state = worker.run(state)

        search_fields = list(self.config.get("critique", {}).get("search_fields", []))
        enable_web_search = bool(self.config.get("critique", {}).get("enable_web_search", True))
        critique_notes = attach_critique_placeholders(
            shortlist=state.shortlist or [],
            enable_web_search=enable_web_search,
            max_candidates=int(self.config.get("critique", {}).get("max_candidates", 10)),
            search_fields=search_fields,
            graph_path=state.knowledge_graph_path,
        )

        backend_name = str(self.config.get("search", {}).get("backend", "stub"))
        count = int(self.config.get("search", {}).get("count", 5))
        multimodal_map = {item.get("candidate_id"): item for item in (state.multimodal_registry or [])}

        if enable_web_search and backend_name != "stub":
            critique_notes = [_live_search_note(note, backend_name=backend_name, count=count) for note in critique_notes]
            state.log(f"CritiqueAgent collected live web evidence using {backend_name}")
        else:
            critique_notes = synthesize_evidence_from_queries(critique_notes)
            state.log("CritiqueAgent prepared candidate evidence bundles with KG-derived context and multimodal hooks")

        enriched_notes = []
        belief_registry = []
        simulation_requests = []
        for note in critique_notes:
            note = dict(note)
            note["multimodal_rerank"] = multimodal_map.get(note.get("candidate_id"), {"candidate_id": note.get("candidate_id"), "bundles": [], "status": "empty"})
            note = _apply_multimodal_judgments(note)
            signals = note.get("signals", {}) or {}
            note["evidence_tier"] = _infer_evidence_tier(signals)
            support = float(signals.get("support_score", 0.0) or 0.0)
            contradiction = float(signals.get("contradiction_score", 0.0) or 0.0)
            if contradiction >= 0.8:
                decision = "reject"
                next_tier = None
            elif support >= 0.8:
                decision = "approve"
                next_tier = None
            elif support >= 0.35:
                decision = "simulate-next"
                next_tier = 1 if signals.get("multimodal_support_score", 0.0) else 2
            else:
                decision = "revise"
                next_tier = 1
            note["decision"] = decision
            note["recommended_next_tier"] = next_tier
            note["contradiction_ledger"] = [item for item in (note.get("evidence") or []) if item.get("match_type") in {"negative", "unrelated"}]
            note["evidence_ledger"] = list(note.get("evidence") or [])
            belief_registry.append({
                "candidate_id": note.get("candidate_id"),
                "status": "supported" if decision == "approve" else ("contradicted" if decision == "reject" else "open"),
                "confidence": max(0.1, min(1.0, support - contradiction + 0.5)),
                "evidence_count": len(note.get("evidence_ledger") or []),
                "owner": "CritiqueAgent",
            })
            if decision == "simulate-next":
                simulation_requests.append({
                    "candidate_id": note.get("candidate_id"),
                    "requested_tier": next_tier,
                    "reason": "critique_uncertainty_resolution",
                })
            enriched_notes.append(note)

        state.critique_notes = enriched_notes
        state.belief_registry = belief_registry
        state.simulation_requests = simulation_requests
        write_json(state.run_dir / "critique_notes.json", enriched_notes)
        state.log(f"CritiqueAgent completed macro evidence pass for {len(enriched_notes)} candidates")
        return state
