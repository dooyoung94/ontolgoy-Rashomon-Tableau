"""OpenRCA topology-relation recovery package."""

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
from .topology_recovery import (
    TopologyMask,
    TopologyRecoveryResult,
    mask_topology_relations,
    recover_missing_topology_relations,
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
    "TopologyMask",
    "TopologyRecoveryResult",
    "mask_topology_relations",
    "recover_missing_topology_relations",
    "AbductiveCausalRelationGenerator",
    "IncidentCausalRCA",
    # 이전 코드와의 호환을 위한 이름.
    "AbductiveRelationGenerator",
    "MissingRelationRCA",
]
