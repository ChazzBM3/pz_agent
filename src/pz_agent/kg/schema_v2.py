from __future__ import annotations

from dataclasses import dataclass, field


NODE_TYPES = [
    "Run",
    "GenerationBatch",
    "Molecule",
    "Scaffold",
    "Substituent",
    "AttachmentSite",
    "DecorationPattern",
    "MolecularRepresentation",
    "Property",
    "Condition",
    "Prediction",
    "Measurement",
    "Model",
    "SearchQuery",
    "Paper",
    "Claim",
    "EvidenceHit",
    "EvidenceSnippet",
    "Figure",
    "Hypothesis",
    "BridgeCase",
    "TransformRule",
    "BridgePrinciple",
    "BridgeDimension",
    "FailureModeClass",
    "SynergyPattern",
    "MediaArtifact",
    "Dataset",
    "RankingDecision",
    "ShortlistDecision",
    "DFTJob",
    "ValidationResult",
]


EDGE_TYPES = [
    "GENERATED_IN_RUN",
    "GENERATED_BY_BATCH",
    "HAS_SCAFFOLD",
    "HAS_SUBSTITUENT",
    "ATTACHED_AT",
    "HAS_DECORATION_PATTERN",
    "HAS_REPRESENTATION",
    "HAS_PROPERTY",
    "UNDER_CONDITION",
    "PREDICTED_FOR",
    "PREDICTED_BY",
    "MEASURED_FOR",
    "MENTIONED_IN_SEARCH",
    "HAS_QUERY",
    "SUPPORTED_BY",
    "CONTRADICTED_BY",
    "BRIDGED_FROM",
    "USES_RULE",
    "HAS_BRIDGE_DIMENSION",
    "HAS_EVIDENCE_HIT",
    "HAS_SNIPPET",
    "HAS_FIGURE",
    "HAS_MEDIA_EVIDENCE",
    "ABOUT_MOLECULE",
    "ABOUT_SCAFFOLD",
    "ABOUT_SUBSTITUENT",
    "ABOUT_PATTERN",
    "ABOUT_PROPERTY",
    "RELATES_TO_CONDITION",
    "EXACT_MATCH_OF",
    "ANALOG_OF",
    "SIMILAR_TO",
    "SELECTED_FOR_DFT",
    "RANKED_IN",
    "VALIDATED_BY",
]


@dataclass
class RetrievalQuery:
    candidate_id: str
    properties_of_interest: list[str] = field(default_factory=list)
    conditions_of_interest: list[str] = field(default_factory=list)
    hop_limit: int = 2
    max_claims: int = 20
    max_evidence: int = 20


@dataclass
class RetrievedContext:
    candidate_id: str
    support_score: float = 0.0
    contradiction_score: float = 0.0
    exact_match_hits: int = 0
    analog_match_hits: int = 0
    claim_count: int = 0
    evidence_count: int = 0
    papers_count: int = 0
    measurement_count: int = 0
    property_count: int = 0
    neighborhood_node_count: int = 0
    neighborhood_edge_count: int = 0
    exact_match_claims: list[dict] = field(default_factory=list)
    analog_claims: list[dict] = field(default_factory=list)
    contradictory_claims: list[dict] = field(default_factory=list)
    property_evidence: list[dict] = field(default_factory=list)
    measurement_summary: list[dict] = field(default_factory=list)
    provenance_summary: list[dict] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    query_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "support_score": self.support_score,
            "contradiction_score": self.contradiction_score,
            "exact_match_hits": self.exact_match_hits,
            "analog_match_hits": self.analog_match_hits,
            "claim_count": self.claim_count,
            "evidence_count": self.evidence_count,
            "papers_count": self.papers_count,
            "measurement_count": self.measurement_count,
            "property_count": self.property_count,
            "neighborhood_node_count": self.neighborhood_node_count,
            "neighborhood_edge_count": self.neighborhood_edge_count,
            "exact_match_claims": self.exact_match_claims,
            "analog_claims": self.analog_claims,
            "contradictory_claims": self.contradictory_claims,
            "property_evidence": self.property_evidence,
            "measurement_summary": self.measurement_summary,
            "provenance_summary": self.provenance_summary,
            "open_questions": self.open_questions,
            "query_hints": self.query_hints,
        }
