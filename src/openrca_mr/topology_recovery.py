from __future__ import annotations

import hashlib
from collections import defaultdict
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


def mask_topology_relations_by_group(
    case_relations: dict[str, list[CausalEdge]],
    case_groups: dict[str, str],
    ratio: float,
    seed: int = 42,
    eligible_relation_types: frozenset[str] | set[str] | None = None,
) -> dict[str, TopologyMask]:
    """Create one deterministic nested mask per topology group.

    A service relation shared by multiple incidents in the same system receives
    the same masking decision. Ranking unique group-level relations also avoids
    per-case rounding from silently turning a requested 20% mask into 0% or 50%.
    """

    if not 0.0 <= ratio <= 1.0:
        raise ValueError("topology missing ratio must be in [0, 1]")
    if set(case_relations) != set(case_groups):
        raise ValueError("case_relations and case_groups must contain identical case IDs")

    eligible_relation_types = (
        STRUCTURAL_RELATION_TYPES
        if eligible_relation_types is None
        else frozenset(eligible_relation_types)
    )
    unknown_types = eligible_relation_types - STRUCTURAL_RELATION_TYPES
    if unknown_types:
        raise ValueError(f"unknown eligible relation types: {sorted(unknown_types)}")
    if not eligible_relation_types:
        raise ValueError("eligible_relation_types must not be empty")

    group_universe: dict[str, set[CausalEdge]] = defaultdict(set)
    for case_id, relations in case_relations.items():
        group = case_groups[case_id]
        group_universe[group].update(
            edge for edge in relations if edge.relation in eligible_relation_types
        )

    missing_by_group: dict[str, set[CausalEdge]] = {}
    for group, universe in group_universe.items():
        ordered = sorted(
            universe,
            key=lambda edge: _relation_rank(group, seed, edge),
        )
        n_missing = round(len(ordered) * ratio)
        missing_by_group[group] = set(ordered[:n_missing])

    masks: dict[str, TopologyMask] = {}
    for case_id, relations in case_relations.items():
        missing_keys = {edge.key() for edge in missing_by_group[case_groups[case_id]]}
        visible = sorted(
            [edge for edge in relations if edge.key() not in missing_keys],
            key=lambda edge: edge.key(),
        )
        missing = sorted(
            [edge for edge in relations if edge.key() in missing_keys],
            key=lambda edge: edge.key(),
        )
        masks[case_id] = TopologyMask(visible, missing)
    return masks


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
    ).run(observations, visible_relations=visible_relations)

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
