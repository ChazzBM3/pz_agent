from __future__ import annotations

ENTITY_TYPES = [
    "Molecule",
    "Scaffold",
    "Substituent",
    "Property",
    "Prediction",
    "Validation",
    "DFTJob",
    "SurrogateModel",
    "GenerationBatch",
    "LiteraturePaper",
    "LiteratureClaim",
    "EvidenceHit",
    "MediaArtifact",
    "Run",
]

RELATION_TYPES = [
    "HAS_SCAFFOLD",
    "SUBSTITUTED_AT",
    "HAS_SUBSTITUENT",
    "PREDICTED_PROPERTY",
    "VALIDATED_PROPERTY",
    "SUPPORTED_BY",
    "CONTRADICTED_BY",
    "SELECTED_FOR_DFT",
    "SIMILAR_TO",
    "GENERATED_IN_RUN",
    "GENERATED_BY_BATCH",
    "MENTIONED_IN_SEARCH",
    "HAS_MEDIA_EVIDENCE",
    "HAS_EVIDENCE_HIT",
    "ANALOG_OF",
    "EXACT_MATCH_OF",
]
