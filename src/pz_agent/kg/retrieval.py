from __future__ import annotations

from pathlib import Path
import re

from pz_agent.kg.rag import retrieve_context, summarize_property_coverage
from pz_agent.kg.schema_v2 import RetrievalQuery


SCHOLARLY_SITE_HINT = "(site:pubs.acs.org OR site:sciencedirect.com OR site:wiley.com OR site:pubmed.ncbi.nlm.nih.gov OR site:doi.org)"


def _looks_like_registry_id(token: str | None) -> bool:
    if not token:
        return False
    return bool(re.fullmatch(r"[A-Z0-9]{5,}", token.strip()))


def _clean_token(token: str | None) -> str:
    if not token:
        return ""
    return re.sub(r"\s+", " ", str(token)).strip()


def _literature_scaffold_name(identity: dict) -> str:
    core_detected = _clean_token(identity.get("core_detected"))
    if core_detected in {"phenothiazine", "thianthrene", "phenoxazine"}:
        return core_detected
    scaffold = _clean_token(identity.get("scaffold"))
    if scaffold and any(ch.isdigit() for ch in scaffold):
        return "phenothiazine"
    return scaffold or "phenothiazine"



def _token_to_literature_term(token: str) -> str:
    mapping = {
        "O": "methoxy OR alkoxy",
        "N": "amino OR dialkylamino",
        "S": "thioether OR sulfur-substituted",
        "F": "fluoro",
        "Cl": "chloro",
        "Br": "bromo",
        "I": "iodo",
        "C#N": "cyano",
        "C(=O)": "carbonyl OR acyl",
        "CF3": "trifluoromethyl",
    }
    return mapping.get(token, token)



def _position_token_to_literature_term(token: str) -> str:
    token = _clean_token(token)
    match = re.fullmatch(r"position\s+(\d+)\s+(.+)", token, flags=re.IGNORECASE)
    if not match:
        return token
    locant, group = match.groups()
    return f"{locant} {_token_to_literature_term(group)}"



def _dedupe_words_preserve_order(text: str) -> str:
    words = []
    seen = set()
    for word in _clean_token(text).split():
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        words.append(word)
    return " ".join(words)



def _build_motif_bits(
    normalized_decoration_summary: str,
    substitution_pattern: str,
    bias_phrase: str,
    decoration_tokens: list[str],
    substituent_fragments: list[str],
    positional_tokens: list[str],
) -> list[str]:
    bits: list[str] = []
    if normalized_decoration_summary and normalized_decoration_summary != "none_detected":
        bits.append(_dedupe_words_preserve_order(normalized_decoration_summary))
    if substitution_pattern:
        bits.append(substitution_pattern.replace('_', ' '))
    if bias_phrase:
        bits.append(_dedupe_words_preserve_order(bias_phrase))
    if decoration_tokens:
        bits.append(_dedupe_words_preserve_order(" ".join(decoration_tokens[:1])))
    if substituent_fragments:
        cleaned_fragment = _dedupe_words_preserve_order(" ".join(substituent_fragments[:1]).replace("substituted ", ""))
        if cleaned_fragment:
            bits.append(cleaned_fragment)
    if positional_tokens:
        bits.append(_dedupe_words_preserve_order(" ".join(positional_tokens[:1])))
    deduped: list[str] = []
    seen = set()
    for bit in bits:
        key = bit.lower()
        if not bit or key in seen:
            continue
        seen.add(key)
        deduped.append(bit)
    return deduped



def _iupac_query_bits(iupac_name: str) -> list[str]:
    text = iupac_name.lower()

    bis_match = re.search(r"(\d+(?:,\d+)*)-bis\(([^)]+)\)", text)
    if bis_match:
        locants, group = bis_match.groups()
        return [f"{locants} {group}"]

    simple_parenthetical = re.search(r"(?:^|\]|-)(\d+(?:,\d+)*)-\((trifluoromethyl|methoxy|ethoxy|cyano|amino)\)", text)
    if simple_parenthetical:
        locants, group = simple_parenthetical.groups()
        return [f"{locants} {group}"]

    plain_match = re.search(r"(\d+(?:,\d+)*)-(dimethyl|difluoro|dichloro|dibromo|diiodo|methoxy|ethoxy|fluoro|chloro|bromo|iodo|cyano|amino)", text)
    if plain_match:
        locants, group = plain_match.groups()
        if not (group == 'ethyl' and locants == '10'):
            return [f"{locants} {group}"]

    if "trifluoromethyl" in text:
        return ["trifluoromethyl"]
    return []



def build_candidate_queries(
    candidate: dict,
    search_fields: list[str] | None = None,
    query_hints: list[str] | None = None,
) -> list[str]:
    fields = search_fields or ["phenothiazine", "solubility", "synthesizability", "derivative"]
    identity = candidate.get("identity", {})
    scaffold = _literature_scaffold_name(identity)
    decoration_summary = _clean_token(identity.get("decoration_summary"))
    electronic_bias = _clean_token(identity.get("electronic_bias"))
    attachment_text = _clean_token(" ".join(identity.get("attachment_summary") or []))
    substitution_pattern = _clean_token(identity.get("substitution_pattern"))
    visual_bundle = candidate.get("visual_bundle") or {}
    visual_identity = visual_bundle.get("visual_identity") or {}
    visual_retrieval_phrases = [
        _clean_token(phrase)
        for phrase in (visual_identity.get("retrieval_phrases") or [])
        if _clean_token(phrase)
    ]
    positional_tokens = [
        _position_token_to_literature_term(token)
        for token in (identity.get("positional_tokens") or [])
        if _clean_token(token)
    ]
    raw_decoration_tokens = [_clean_token(token) for token in (identity.get("decoration_tokens") or []) if _clean_token(token)]
    decoration_tokens = [_token_to_literature_term(token) for token in raw_decoration_tokens[:3]]
    substituent_fragments = [
        _clean_token(fragment.replace("frag:", "substituted "))
        for fragment in (identity.get("substituent_fragments") or [])
        if _clean_token(fragment)
    ]
    candidate_name = _clean_token(identity.get("name"))
    iupac_name = _clean_token(identity.get("iupac_name"))
    molecular_formula = _clean_token(identity.get("molecular_formula"))
    candidate_id = _clean_token(candidate.get("id"))

    public_name = candidate_name if candidate_name and not _looks_like_registry_id(candidate_name) else ""
    public_id = candidate_id if candidate_id and not _looks_like_registry_id(candidate_id) else ""
    public_token_text = " ".join(token for token in [public_name, public_id] if token)
    core_detected = _clean_token(identity.get("core_detected")) or scaffold
    nomenclature_token = ""
    if iupac_name:
        iupac_lower = iupac_name.lower()
        if any(core in iupac_lower for core in [core_detected.lower(), "phenothiaz", "thianthren", "phenoxazin"]):
            nomenclature_token = iupac_name
    iupac_bits = _iupac_query_bits(nomenclature_token) if nomenclature_token else []

    property_terms = []
    for field in fields:
        field = _clean_token(field).replace("_", " ")
        if field and field not in property_terms:
            property_terms.append(field)
    broad_property_clause = " OR ".join(property_terms) if property_terms else "oxidation potential OR reduction potential"
    scholarly_property_clause = " OR ".join(term for term in property_terms if "phenothiazine" not in term.lower()) or broad_property_clause

    bias_phrase = {
        "electron_donating_skew": "electron donating substituents",
        "electron_withdrawing_skew": "electron withdrawing substituents",
        "mixed": "mixed donor acceptor substituents",
    }.get(electronic_bias, electronic_bias)

    normalized_decoration_summary = decoration_summary.replace("+", " ") if decoration_summary else ""
    motif_bits = _build_motif_bits(
        normalized_decoration_summary=normalized_decoration_summary,
        substitution_pattern=substitution_pattern,
        bias_phrase=bias_phrase,
        decoration_tokens=decoration_tokens,
        substituent_fragments=substituent_fragments,
        positional_tokens=positional_tokens,
    )
    motif_clause = " ".join(motif_bits)

    queries = []
    if nomenclature_token:
        queries.append(f'"{nomenclature_token}" redox solubility synthesis')
        if iupac_bits:
            queries.append(f'"{scaffold}" "{' '.join(iupac_bits)}" redox solubility')
    if motif_clause:
        queries.append(f'"{scaffold}" {motif_clause} ({broad_property_clause})')
        queries.append(f'{SCHOLARLY_SITE_HINT} "{scaffold}" {motif_clause}')
    if decoration_tokens:
        token_clause = " ".join(decoration_tokens[:2])
        queries.append(f'"{scaffold}" {token_clause} redox solubility synthesis')
    for phrase in visual_retrieval_phrases[:2]:
        cleaned_phrase = phrase.replace(scaffold, "").strip()
        if cleaned_phrase:
            queries.append(f'"{scaffold}" {cleaned_phrase} redox solubility synthesis')
    queries.extend(
        [
            f'"{scaffold}" derivative synthesis redox',
            f'"{scaffold}" ({broad_property_clause}) chemistry',
            f'{SCHOLARLY_SITE_HINT} "{scaffold}" ({scholarly_property_clause})',
        ]
    )
    if molecular_formula and len(molecular_formula) <= 20:
        queries.append(f'"{scaffold}" "{molecular_formula}" redox')
    if public_token_text:
        queries.append(f'"{public_token_text}" "{scaffold}" chemistry')

    for hint in query_hints or []:
        cleaned_hint = _clean_token(hint).replace("_", " ")
        if not cleaned_hint:
            continue
        if _looks_like_registry_id(cleaned_hint.split()[0]):
            continue
        if cleaned_hint not in queries:
            queries.append(cleaned_hint)

    deduped = []
    seen = set()
    for query in queries:
        if query not in seen:
            deduped.append(query)
            seen.add(query)
    return deduped[:4]


def attach_critique_placeholders(
    shortlist: list[dict],
    enable_web_search: bool,
    max_candidates: int,
    search_fields: list[str] | None = None,
    graph_path: Path | None = None,
) -> list[dict]:
    notes: list[dict] = []
    for item in shortlist[:max_candidates]:
        retrieval_query = RetrievalQuery(
            candidate_id=item["id"],
            properties_of_interest=list(search_fields or []),
        )
        kg_context = retrieve_context(graph_path, retrieval_query)
        property_coverage = summarize_property_coverage(graph_path, item["id"])
        structure_expansion = item.get("structure_expansion") or {}
        patent_retrieval = item.get("patent_retrieval") or {}
        scholarly_retrieval = item.get("scholarly_retrieval") or {}
        exact_match_hits = len(structure_expansion.get("exact_matches") or [])
        analog_match_hits = len(structure_expansion.get("similarity_matches") or []) + len(structure_expansion.get("substructure_matches") or [])
        patent_hit_count = sum(len(bundle.get("hits") or []) for bundle in (patent_retrieval.get("surechembl") or [])) + sum(len(bundle.get("hits") or []) for bundle in (patent_retrieval.get("patcid") or []))
        scholarly_hit_count = sum(len(bundle.get("hits") or []) for bundle in (scholarly_retrieval.get("openalex") or []))
        notes.append(
            {
                "candidate_id": item["id"],
                "identity": item.get("identity", {}),
                "web_search_enabled": enable_web_search,
                "status": "pending_web_search" if enable_web_search else "disabled",
                "queries": build_candidate_queries(item, search_fields=search_fields, query_hints=kg_context.query_hints),
                "summary": "Awaiting web evidence collection for top candidate.",
                "evidence": [],
                "media_evidence": [],
                "kg_context": kg_context.to_dict(),
                "measurement_context": property_coverage,
                "structure_expansion": structure_expansion,
                "patent_retrieval": patent_retrieval,
                "scholarly_retrieval": scholarly_retrieval,
                "signals": {
                    "supports_solubility": None,
                    "supports_synthesizability": None,
                    "warns_instability": None,
                    "exact_match_hits": kg_context.exact_match_hits + exact_match_hits,
                    "analog_match_hits": kg_context.analog_match_hits + analog_match_hits,
                    "patent_hit_count": patent_hit_count,
                    "scholarly_hit_count": scholarly_hit_count,
                    "support_score": kg_context.support_score + (1.0 * exact_match_hits) + (0.25 * analog_match_hits) + (0.1 * patent_hit_count) + (0.05 * scholarly_hit_count),
                    "contradiction_score": kg_context.contradiction_score,
                    "measurement_count": int(property_coverage.get("measurement_count", 0)),
                    "property_count": int(property_coverage.get("property_count", 0)),
                },
            }
        )
    return notes


def synthesize_evidence_from_queries(notes: list[dict]) -> list[dict]:
    for note in notes:
        evidence = []
        media_evidence = []

        structure_expansion = note.get("structure_expansion") or {}
        patent_retrieval = note.get("patent_retrieval") or {}
        scholarly_retrieval = note.get("scholarly_retrieval") or {}

        for idx, match in enumerate(structure_expansion.get("exact_matches") or []):
            evidence.append(
                {
                    "id": f"pubchem_exact::{note['candidate_id']}::{idx}",
                    "kind": "pubchem_exact_match",
                    "query": structure_expansion.get("query_smiles"),
                    "title": match.get("title") or f"PubChem exact match {match.get('cid')}",
                    "url": match.get("pubchem_url"),
                    "snippet": f"Exact PubChem identity hit for CID {match.get('cid')} ({match.get('molecular_formula') or 'formula unavailable'}).",
                    "match_type": "exact",
                    "provenance": {
                        "source_type": "pubchem",
                        "query": structure_expansion.get("query_smiles"),
                        "confidence": 1.0,
                        "evidence_level": "exact_structure",
                    },
                }
            )

        for idx, match in enumerate((structure_expansion.get("similarity_matches") or []) + (structure_expansion.get("substructure_matches") or [])):
            evidence.append(
                {
                    "id": f"pubchem_analog::{note['candidate_id']}::{idx}",
                    "kind": "pubchem_analog_match",
                    "query": structure_expansion.get("query_smiles"),
                    "title": match.get("title") or f"PubChem analog match {match.get('cid')}",
                    "url": match.get("pubchem_url"),
                    "snippet": f"Analog PubChem structure hit for CID {match.get('cid')} ({match.get('molecular_formula') or 'formula unavailable'}).",
                    "match_type": "analog",
                    "provenance": {
                        "source_type": "pubchem",
                        "query": structure_expansion.get("query_smiles"),
                        "confidence": 0.6,
                        "evidence_level": "analog_structure",
                    },
                }
            )

        for source_name in ["surechembl", "patcid"]:
            for idx, bundle in enumerate(patent_retrieval.get(source_name) or []):
                for hit_idx, hit in enumerate(bundle.get("hits") or []):
                    evidence.append(
                        {
                            "id": f"{source_name}::{note['candidate_id']}::{idx}::{hit_idx}",
                            "kind": "patent_result",
                            "query": bundle.get("query"),
                            "title": hit.get("title") or hit.get("doc_id") or hit.get("patent_id") or "Patent hit",
                            "url": hit.get("url"),
                            "snippet": hit.get("snippet") or "Patent-side retrieval hit.",
                            "match_type": hit.get("match_type") or "analog",
                            "provenance": {
                                "source_type": source_name,
                                "query": bundle.get("query"),
                                "confidence": hit.get("confidence"),
                                "evidence_level": "patent_retrieval",
                            },
                        }
                    )

        for idx, bundle in enumerate(scholarly_retrieval.get("openalex") or []):
            for hit_idx, hit in enumerate(bundle.get("hits") or []):
                evidence.append(
                    {
                        "id": f"openalex::{note['candidate_id']}::{idx}::{hit_idx}",
                        "kind": "scholarly_result",
                        "query": bundle.get("query"),
                        "title": hit.get("title"),
                        "url": hit.get("url"),
                        "snippet": hit.get("snippet"),
                        "match_type": hit.get("match_type") or "unknown",
                        "provenance": {
                            "source_type": "openalex",
                            "query": bundle.get("query"),
                            "confidence": hit.get("confidence"),
                            "evidence_level": "scholarly_retrieval",
                        },
                    }
                )

        for idx, query in enumerate(note.get("queries", [])):
            evidence.append(
                {
                    "id": f"evidence::{note['candidate_id']}::{idx}",
                    "kind": "web_result_stub",
                    "query": query,
                    "title": f"Stub literature hit for {note['candidate_id']}",
                    "url": None,
                    "snippet": "Replace with actual title/url/snippet from web_search tool integration.",
                    "match_type": "unknown",
                    "provenance": {
                        "source_type": "web_search",
                        "query": query,
                        "confidence": None,
                        "evidence_level": "unknown",
                    },
                }
            )
            media_evidence.append(
                {
                    "id": f"media::{note['candidate_id']}::{idx}",
                    "kind": "plot_or_figure_stub",
                    "query": query,
                    "caption": "Stub figure/plot reference for this evidence item.",
                    "source_url": None,
                    "image_path": None,
                    "media_type": "plot",
                    "provenance": {
                        "source_type": "literature_figure_or_generated_plot",
                        "query": query,
                        "confidence": None,
                    },
                }
            )
        note["evidence"] = evidence
        note["media_evidence"] = media_evidence
        kg_context = note.get("kg_context", {})
        measurement_context = note.get("measurement_context", {})
        open_questions = kg_context.get("open_questions", [])
        note["summary"] = "Structured critique bundle includes KG-derived context, text-evidence stubs, media stubs, and graph-ready provenance."
        if measurement_context.get("measurement_count", 0):
            note["summary"] += f" Measured properties available: {measurement_context.get('property_count', 0)} across {measurement_context.get('measurement_count', 0)} records."
        if open_questions:
            note["summary"] += " Open questions: " + " | ".join(open_questions[:3])
        if note.get("web_search_enabled"):
            note["status"] = "ready_for_live_web_ingestion"
        note["signals"] = {
            "supports_solubility": None,
            "supports_synthesizability": None,
            "warns_instability": None,
            "exact_match_hits": int(note.get("signals", {}).get("exact_match_hits", 0)),
            "analog_match_hits": int(note.get("signals", {}).get("analog_match_hits", 0)),
            "patent_hit_count": int(note.get("signals", {}).get("patent_hit_count", 0)),
            "scholarly_hit_count": int(note.get("signals", {}).get("scholarly_hit_count", 0)),
            "support_score": float(note.get("signals", {}).get("support_score", 0.0)),
            "contradiction_score": float(note.get("signals", {}).get("contradiction_score", 0.0)),
            "measurement_count": int(note.get("signals", {}).get("measurement_count", 0)),
            "property_count": int(note.get("signals", {}).get("property_count", 0)),
        }
    return notes
