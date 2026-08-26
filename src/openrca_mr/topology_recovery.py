from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .models import CausalEdge, RelationObservation, StructuralHypothesis, STRUCTURAL_RELATION_TYPES
from .structural import StructuralRelationRecovery


@dataclass(frozen=True)
class TopologyMask:
    """A complete topology split into visible and intentionally missing relations."""

    visible_relations: list[CausalEdge]
    missing_relations: list[CausalEdge]


@dataclass
class TopologyRecoveryResult:
    """Result of filling relations that are absent from an existing topology."""

    visible_relations: list[CausalEdge]
    added_relations: list[CausalEdge]
    recovered_topology: list[CausalEdge]
    hypotheses: list[StructuralHypothesis]


def _relation_rank(case_id: str, seed: int, edge: CausalEdge) -> bytes:
    payload = f"{seed}:{case_id}:{edge.source}|{edge.relation}|{edge.target}"
    return hashlib.sha256(payload.encode("utf-8")).digest()


def mask_topology_relations(
    case_id: str,
    full_relations: list[CausalEdge],
    ratio: float,
    seed: int = 42,
) -> TopologyMask:
    """Remove relations from topology while leaving collector observations untouched.

    This models the target operational problem: objects and runtime data are
    collectible, but part of the topology relation map is absent. The removed
    relation is not replaced by a special marker because a real incomplete
    topology simply has no such relation.
    """

    if not 0.0 <= ratio <= 1.0:
        raise ValueError("topology missing ratio must be in [0, 1]")

    eligible = [
        edge for edge in full_relations if edge.relation in STRUCTURAL_RELATION_TYPES
    ]
    ordered = sorted(eligible, key=lambda edge: _relation_rank(case_id, seed, edge))
    n_missing = round(len(ordered) * ratio)
    missing_keys = {edge.key() for edge in ordered[:n_missing]}

    visible = sorted(
        [edge for edge in full_relations if edge.key() not in missing_keys],
        key=lambda edge: edge.key(),
    )
    missing = sorted(
        [edge for edge in full_relations if edge.key() in missing_keys],
        key=lambda edge: edge.key(),
    )
    return TopologyMask(visible_relations=visible, missing_relations=missing)


def recover_missing_topology_relations(
    visible_relations: list[CausalEdge],
    observations: list[RelationObservation],
    semantic_scorer=None,
    global_inference=None,
    relation_threshold: float = 0.5,
) -> TopologyRecoveryResult:
    """Infer relations absent from topology using unchanged collector evidence.

    Existing topology relations are preserved. The structural inference pipeline
    proposes relations from collector evidence; only relations not already in the
    visible topology are treated as additions.
    """

    inference = StructuralRelationRecovery(
        semantic_scorer=semantic_scorer,
        global_inference=global_inference,
        relation_threshold=relation_threshold,
    ).run(observations)

    visible_keys = {edge.key() for edge in visible_relations}
    added = sorted(
        [edge for edge in inference.relations if edge.key() not in visible_keys],
        key=lambda edge: edge.key(),
    )
    recovered = sorted(
        {edge for edge in visible_relations + added},
        key=lambda edge: edge.key(),
    )
    return TopologyRecoveryResult(
        visible_relations=list(visible_relations),
        added_relations=added,
        recovered_topology=recovered,
        hypotheses=inference.hypotheses,
    )
