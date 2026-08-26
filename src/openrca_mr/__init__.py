"""OpenRCA structural-relation recovery and causal-process reasoning package."""

from .abduction import AbductiveCausalRelationGenerator, AbductiveRelationGenerator
from .models import (
    CausalEdge,
    Evidence,
    Hypothesis,
    RcaCase,
    RelationObservation,
    StructuralHypothesis,
)
from .pipeline import IncidentCausalRCA, MissingRelationRCA
from .structural import (
    AbductiveStructuralRelationGenerator,
    StructuralRelationRecovery,
    collect_structural_observations,
    extract_structural_relations,
    propagation_service_edges,
    recover_structural_relations,
)

__all__ = [
    "CausalEdge",
    "Evidence",
    "Hypothesis",
    "RcaCase",
    "RelationObservation",
    "StructuralHypothesis",
    "AbductiveStructuralRelationGenerator",
    "StructuralRelationRecovery",
    "collect_structural_observations",
    "recover_structural_relations",
    "extract_structural_relations",
    "propagation_service_edges",
    "AbductiveCausalRelationGenerator",
    "IncidentCausalRCA",
    # Backward-compatible historical names.
    "AbductiveRelationGenerator",
    "MissingRelationRCA",
]
