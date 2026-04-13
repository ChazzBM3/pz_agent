from __future__ import annotations

CHEMISTRY_NAMESPACES = ("chem_pt::", "chem_qn::", "bridge::")
EVIDENCE_NAMESPACES = ("evidence::",)
BELIEF_NAMESPACES = ("belief::", "run::")


KG_V3_LAYERS = {
    "chemistry": {
        "namespaces": CHEMISTRY_NAMESPACES,
        "objects": [
            "Molecule",
            "Scaffold",
            "AttachmentSite",
            "Substituent",
            "DecorationPattern",
            "RedoxState",
            "TransformRule",
            "FailureMode",
            "Mechanism",
        ],
    },
    "evidence": {
        "namespaces": EVIDENCE_NAMESPACES,
        "objects": [
            "Paper",
            "Patent",
            "SearchQuery",
            "EvidenceHit",
            "Claim",
            "Measurement",
            "Condition",
            "Figure",
            "Page",
            "Caption",
            "Dataset",
        ],
    },
    "belief_campaign": {
        "namespaces": BELIEF_NAMESPACES,
        "objects": [
            "Hypothesis",
            "SynergyPattern",
            "Prediction",
            "RankingDecision",
            "ShortlistDecision",
            "SimulationRequest",
            "SimulationResult",
            "DFTJob",
            "ValidationResult",
        ],
    },
}
