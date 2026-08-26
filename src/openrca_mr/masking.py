from __future__ import annotations

import hashlib
import random

from .metrics import normalize_service
from .models import (
    CausalEdge,
    RcaCase,
    REL_CAUSAL,
    REL_MASKED,
    REL_NON_CAUSAL,
)
from .structural import mask_structural_relation_types


def _case_seed(case_id: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{case_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _pair(edge: CausalEdge) -> tuple[str, str]:
    return normalize_service(edge.source), normalize_service(edge.target)


def mask_relation_types(
    case: RcaCase,
    ratio: float,
    seed: int = 42,
) -> tuple[RcaCase, list[CausalEdge]]:
    """Mask Stage-2 incident causal semantics on observed service pairs.

    This function intentionally does *not* mask operational relation types such
    as CALLS, DEPLOYED_ON, or USES_DATABASE. The endpoint pair stays visible and
    only the incident-specific label ``causal_propagates_to`` versus
    ``non_causal_dependency`` is hidden.

    The historical function name is retained because existing 20/500-case
    experiment artifacts and workflows call it directly.
    """
    if not 0.0 <= ratio <= 1.0:
        raise ValueError("ratio must be in [0, 1]")

    gold_pairs = {_pair(edge) for edge in case.gold_edges}
    fully_labeled = [
        CausalEdge(
            edge.source,
            REL_CAUSAL if _pair(edge) in gold_pairs else REL_NON_CAUSAL,
            edge.target,
        )
        for edge in case.known_edges
    ]

    rng = random.Random(_case_seed(case.case_id, seed))
    n_mask = round(len(fully_labeled) * ratio)
    indices = set(rng.sample(range(len(fully_labeled)), n_mask)) if n_mask else set()

    visible_edges: list[CausalEdge] = []
    masked_truth: list[CausalEdge] = []
    for idx, edge in enumerate(fully_labeled):
        if idx in indices:
            masked_truth.append(edge)
            visible_edges.append(CausalEdge(edge.source, REL_MASKED, edge.target))
        else:
            visible_edges.append(edge)

    return (
        RcaCase(
            case_id=case.case_id,
            symptom_nodes=list(case.symptom_nodes),
            known_edges=visible_edges,
            evidence=list(case.evidence),
            gold_root_causes=list(case.gold_root_causes),
            gold_edges=list(case.gold_edges),
            gold_paths=[list(path) for path in case.gold_paths],
            gold_alarm_nodes=list(case.gold_alarm_nodes),
            metadata={
                **case.metadata,
                "mask_mode": "relation",
                "relation_layer": "incident_causal",
                "mask_ratio": ratio,
                "mask_seed": seed,
            },
            structural_relations=list(case.structural_relations),
            relation_observations=list(case.relation_observations),
        ),
        masked_truth,
    )


# Explicit alias used by new code/documentation; old callers remain compatible.
mask_causal_relation_types = mask_relation_types


def mask_relations(
    case: RcaCase,
    ratio: float,
    seed: int = 42,
) -> tuple[RcaCase, list[CausalEdge]]:
    """Legacy Stage-2 edge-removal stress test; not the main masking protocol."""
    if not 0.0 <= ratio <= 1.0:
        raise ValueError("ratio must be in [0, 1]")
    rng = random.Random(_case_seed(case.case_id, seed))
    edges = list(case.known_edges)
    n_mask = round(len(edges) * ratio)
    indices = set(rng.sample(range(len(edges)), n_mask)) if n_mask else set()
    masked = [edge for idx, edge in enumerate(edges) if idx in indices]
    kept = [edge for idx, edge in enumerate(edges) if idx not in indices]
    return (
        RcaCase(
            case_id=case.case_id,
            symptom_nodes=list(case.symptom_nodes),
            known_edges=kept,
            evidence=list(case.evidence),
            gold_root_causes=list(case.gold_root_causes),
            gold_edges=list(case.gold_edges),
            gold_paths=[list(path) for path in case.gold_paths],
            gold_alarm_nodes=list(case.gold_alarm_nodes),
            metadata={
                **case.metadata,
                "mask_mode": "edge",
                "relation_layer": "incident_causal",
                "mask_ratio": ratio,
                "mask_seed": seed,
            },
            structural_relations=list(case.structural_relations),
            relation_observations=list(case.relation_observations),
        ),
        masked,
    )
