from __future__ import annotations

import random

from .models import CausalEdge, RcaCase


def mask_relations(case: RcaCase, ratio: float, seed: int = 42) -> tuple[RcaCase, list[CausalEdge]]:
    """Remove a controlled fraction of known causal edges from the model input.

    Gold labels remain untouched and are returned only for evaluator-side use.
    This function must never be called before train/dev/test splitting with a
    seed selected from test performance.
    """

    if not 0.0 <= ratio <= 1.0:
        raise ValueError("ratio must be in [0, 1]")
    rng = random.Random(seed)
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
            metadata={**case.metadata, "mask_ratio": ratio, "mask_seed": seed},
        ),
        masked,
    )
