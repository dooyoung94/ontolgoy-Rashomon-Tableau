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


def _case_seed(case_id: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{case_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _pair(edge: CausalEdge) -> tuple[str, str]:
    return normalize_service(edge.source), normalize_service(edge.target)


def mask_relation_types(case: RcaCase, ratio: float, seed: int = 42) -> tuple[RcaCase, list[CausalEdge]]:
    """Mask relation semantics while preserving every observed endpoint pair.

    This is the main controlled incomplete-ontology track. The full relation
    label for an observed dependency is defined from PAVE causal supervision:
    an observed pair that occurs in the gold propagation graph is causal;
    otherwise it is a non-causal dependency. A fraction of those labels is
    hidden from the model, while source/target connectivity remains visible.

    Gold-derived labels are used only to construct this controlled masking
    benchmark. The model sees only unmasked labels and ``REL_MASKED`` atoms.
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
                "mask_ratio": ratio,
                "mask_seed": seed,
            },
        ),
        masked_truth,
    )


def mask_relations(case: RcaCase, ratio: float, seed: int = 42) -> tuple[RcaCase, list[CausalEdge]]:
    """Legacy edge-removal stress test; not the main relation-masking track."""
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
            metadata={**case.metadata, "mask_mode": "edge", "mask_ratio": ratio, "mask_seed": seed},
        ),
        masked,
    )
