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
    "LiteraturePaper",
    "LiteratureClaim",
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
    "MENTIONED_IN_SEARCH",
]
