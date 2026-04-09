from __future__ import annotations

from pathlib import Path

from pz_agent.agents.critique import (
    CritiqueAgent,
    _classify_match_type,
    _is_relevant_chemistry_result,
    _summarize_live_signals,
)
from pz_agent.kg.retrieval import build_candidate_queries
from pz_agent.search.backends import OpenAlexSearchBackend, _openalex_abstract_to_text
from pz_agent.state import RunState


def test_critique_agent_uses_live_search_backend(tmp_path: Path) -> None:
    state = RunState(
        config={
            "critique": {
                "enable_web_search": True,
                "max_candidates": 1,
                "search_fields": ["phenothiazine", "solubility"],
            },
            "search": {
                "backend": "stub",
                "count": 2,
            },
            "screening": {"shortlist_size": 1},
        },
        run_dir=tmp_path,
    )
    state.shortlist = [
        {
            "id": "cand_1",
            "identity": {"name": "cand_1", "scaffold": "phenothiazine"},
        }
    ]

    agent = CritiqueAgent(config=state.config)
    updated = agent.run(state)

    assert updated.critique_notes is not None
    note = updated.critique_notes[0]
    assert note["status"] in {"ready_for_live_web_ingestion", "disabled"}


def test_critique_agent_falls_back_to_placeholder_for_stub_backend(tmp_path: Path) -> None:
    state = RunState(
        config={
            "critique": {
                "enable_web_search": True,
                "max_candidates": 1,
                "search_fields": ["phenothiazine"],
            },
            "search": {
                "backend": "stub",
                "count": 2,
            },
            "screening": {"shortlist_size": 1},
        },
        run_dir=tmp_path,
    )
    state.shortlist = [{"id": "cand_2", "identity": {}}]

    agent = CritiqueAgent(config=state.config)
    updated = agent.run(state)

    note = updated.critique_notes[0]
    assert note["evidence"]
    assert note["evidence"][0]["kind"] == "web_result_stub"


def test_classify_match_type_detects_exact_and_analog() -> None:
    note = {
        "candidate_id": "cand_1",
        "identity": {
            "name": "cand_1",
            "scaffold": "phenothiazine",
            "decoration_tokens": ["O", "N"],
        },
    }

    assert _classify_match_type(note, "cand_1 phenothiazine result", None, None) == "exact"
    assert _classify_match_type(note, "phenothiazine derivative study", None, None) == "analog"
    assert _classify_match_type(note, "unrelated benzene result", None, None) == "unknown"


def test_is_relevant_chemistry_result_filters_obvious_junk() -> None:
    assert _is_relevant_chemistry_result(
        "Phenothiazine redox properties in solution",
        "Electrochemical oxidation and reduction measurements for a phenothiazine compound.",
        "https://pubs.acs.org/doi/10.1021/example",
    ) is True
    assert _is_relevant_chemistry_result(
        "Google",
        "Search the world's information",
        "https://www.google.com/",
    ) is False
    assert _is_relevant_chemistry_result(
        "Dérivé VP sur carte grise",
        "Forum automobile unrelated to chemistry",
        "https://droit-finances.commentcamarche.com/forum/affich-7774901",
    ) is False


def test_build_candidate_queries_avoids_opaque_ids_and_keeps_broad_queries() -> None:
    queries = build_candidate_queries(
        {
            "id": "05MNXL",
            "identity": {
                "name": "05MNXL",
                "scaffold": "phenothiazine",
                "decoration_summary": "methoxy substitution",
            },
        },
        search_fields=["phenothiazine", "oxidation_potential", "reduction_potential"],
        query_hints=["05MNXL measured properties available", "phenothiazine analog redox literature"],
    )

    assert all("05MNXL" not in query for query in queries)
    assert any('"phenothiazine"' in query and "chemistry" in query for query in queries)
    assert any("site:pubs.acs.org" in query for query in queries)
    assert any("methoxy substitution" in query for query in queries)


def test_openalex_abstract_to_text_reconstructs_text() -> None:
    text = _openalex_abstract_to_text({"Phenothiazine": [0], "redox": [1], "study": [2]})
    assert text == "Phenothiazine redox study"


def test_openalex_backend_parses_results(monkeypatch) -> None:
    payload = {
        "results": [
            {
                "display_name": "Phenothiazine redox properties",
                "doi": "https://doi.org/10.1000/example",
                "id": "https://openalex.org/W123",
                "publication_year": 2024,
                "primary_location": {"landing_page_url": "https://doi.org/10.1000/example"},
                "abstract_inverted_index": {"Phenothiazine": [0], "redox": [1], "properties": [2]},
            }
        ]
    }

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            import json
            return json.dumps(payload).encode("utf-8")

    def _fake_urlopen(url, timeout=20):
        assert "api.openalex.org/works?search=" in url
        return _FakeResponse()

    monkeypatch.setattr("pz_agent.search.backends.urlopen", _fake_urlopen)
    hits = OpenAlexSearchBackend().search("phenothiazine redox", count=3)
    assert len(hits) == 1
    assert hits[0].title == "Phenothiazine redox properties"
    assert hits[0].url == "https://doi.org/10.1000/example"
    assert "Phenothiazine redox properties" in hits[0].snippet


def test_summarize_live_signals_detects_property_support_and_warnings() -> None:
    note = {"signals": {"support_score": 0.0, "contradiction_score": 0.0}}
    evidence = [
        {
            "title": "Phenothiazine solubility and synthesis route study",
            "snippet": "This soluble analog was prepared through a short synthesis.",
            "match_type": "analog",
        },
        {
            "title": "Phenothiazine instability report",
            "snippet": "The compound shows decomposition under air.",
            "match_type": "exact",
        },
        {
            "title": "Phenothiazine review",
            "snippet": "General phenothiazine background without measured property discussion.",
            "match_type": "unknown",
        },
    ]

    signals = _summarize_live_signals(note, evidence)

    assert signals["supports_solubility"] is True
    assert signals["supports_synthesizability"] is True
    assert signals["warns_instability"] is True
    assert signals["exact_match_hits"] >= 1
    assert signals["analog_match_hits"] >= 1
    assert signals["broad_scaffold_hits"] >= 1
    assert signals["property_aligned_hits"] >= 1
    assert signals["support_score"] < 2.0
