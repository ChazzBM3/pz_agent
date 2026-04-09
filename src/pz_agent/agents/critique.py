from __future__ import annotations

from urllib.parse import urlparse

from pz_agent.agents.base import BaseAgent
from pz_agent.io import write_json
from pz_agent.kg.retrieval import attach_critique_placeholders, synthesize_evidence_from_queries
from pz_agent.search.backends import get_search_backend
from pz_agent.state import RunState


PROPERTY_KEYWORDS = {
    "solubility": ["solubility", "soluble"],
    "synthesizability": ["synthesis", "synthetic", "synthesizability", "prepared", "route"],
    "instability": ["unstable", "instability", "decomposition", "degrade"],
}

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



def _is_relevant_chemistry_result(title: str | None, snippet: str | None, url: str | None) -> bool:
    host = (urlparse(url).netloc or "").lower() if url else ""
    if any(fragment in host for fragment in BLOCKED_HOST_FRAGMENTS):
        return False
    text = " ".join(part for part in [title or "", snippet or "", host] if part).lower()
    keyword_hits = sum(1 for keyword in CHEMISTRY_KEYWORDS if keyword in text)
    if any(trusted in host for trusted in TRUSTED_CHEMISTRY_HOSTS):
        return True
    return keyword_hits >= 2


def _summarize_live_signals(note: dict, evidence: list[dict]) -> dict:
    signals = dict(note.get("signals", {}))
    exact_hits = 0
    analog_hits = 0
    support_score = float(signals.get("support_score", 0.0) or 0.0)
    contradiction_score = float(signals.get("contradiction_score", 0.0) or 0.0)
    supports_solubility = bool(signals.get("supports_solubility"))
    supports_synth = bool(signals.get("supports_synthesizability"))
    warns_instability = bool(signals.get("warns_instability"))

    for item in evidence:
        match_type = item.get("match_type")
        if match_type == "exact":
            exact_hits += 1
            support_score += 1.0
        elif match_type == "analog":
            analog_hits += 1
            support_score += 0.5

        text = " ".join([str(item.get("title") or ""), str(item.get("snippet") or "")]).lower()
        if any(keyword in text for keyword in PROPERTY_KEYWORDS["solubility"]):
            supports_solubility = True
            support_score += 0.25
        if any(keyword in text for keyword in PROPERTY_KEYWORDS["synthesizability"]):
            supports_synth = True
            support_score += 0.25
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
            "support_score": support_score,
            "contradiction_score": contradiction_score,
        }
    )
    return signals



def _live_search_note(note: dict, backend_name: str, count: int) -> dict:
    backend = get_search_backend(backend_name)
    evidence = []
    media_evidence = []
    for idx, query in enumerate(note.get("queries", [])):
        try:
            hits = backend.search(query, count=count)
        except Exception:
            hits = []
        for hit_idx, hit in enumerate(hits):
            if not _is_relevant_chemistry_result(hit.title, hit.snippet, hit.url):
                continue
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
    note["evidence"] = evidence
    note["media_evidence"] = media_evidence
    note["signals"] = _summarize_live_signals(note, evidence)
    note["status"] = "live_web_results" if evidence else "live_web_no_results"
    note["summary"] = f"Live web critique collected {len(evidence)} evidence hits via {backend.name}."
    return note


class CritiqueAgent(BaseAgent):
    name = "critique"

    def run(self, state: RunState) -> RunState:
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
        if enable_web_search and backend_name != "stub":
            critique_notes = [_live_search_note(note, backend_name=backend_name, count=count) for note in critique_notes]
            state.log(f"Critique agent collected live web evidence using {backend_name}")
        else:
            critique_notes = synthesize_evidence_from_queries(critique_notes)
            state.log("Critique agent prepared candidate evidence bundles with KG-derived context, targeted queries, and text/image placeholders")

        state.critique_notes = critique_notes
        write_json(state.run_dir / "critique_notes.json", critique_notes)
        return state
