from __future__ import annotations

import hashlib
import random

from .models import CausalEdge, RcaCase


def _case_seed(case_id: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{case_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def mask_relations(case: RcaCase, ratio: float, seed: int = 42) -> tuple[RcaCase, list[CausalEdge]]:
    """Remove a controlled fraction of model-visible structural edges."""
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
            metadata={**case.metadata, "mask_ratio": ratio, "mask_seed": seed},
        ),
        masked,
    )
