from __future__ import annotations

import importlib.util
from pathlib import Path


BASE = Path(__file__).with_name("evaluate_iterative_pruning_search_incremental.py")
spec = importlib.util.spec_from_file_location("incremental_base", BASE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load {BASE}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


_original_policies = base.policies


def policies():
    out = _original_policies()
    # Classical Rashomon sets are defined in loss space. With DeBERTa support s,
    # use loss L=1-s and retain L <= (1+epsilon)L*. This is equivalent to
    # s >= s* - epsilon(1-s*), making the tolerance scale-aware.
    out["rashomon_relative_loss_0.10"] = base.PolicyState(
        "rashomon_relative_loss_0.10", "relative_loss", 0.10, 20
    )
    out["rashomon_relative_loss_0.25"] = base.PolicyState(
        "rashomon_relative_loss_0.25", "relative_loss", 0.25, 20
    )
    out["rashomon_relative_loss_0.50"] = base.PolicyState(
        "rashomon_relative_loss_0.50", "relative_loss", 0.50, 20
    )
    return out


def select(candidates, state, edge_scores):
    if state.kind != "relative_loss":
        return _original_select(candidates, state, edge_scores)
    ranked = sorted(
        candidates,
        key=lambda p: (-base.path_score(p, edge_scores), base.path_key(p)),
    )
    if not ranked:
        return []
    best = base.path_score(ranked[0], edge_scores)
    best_loss = 1.0 - best
    max_loss = (1.0 + state.value) * best_loss
    threshold = 1.0 - max_loss
    chosen = [p for p in ranked if base.path_score(p, edge_scores) >= threshold]
    if state.max_width is not None:
        chosen = chosen[: state.max_width]
    return chosen


_original_select = base.select
base.policies = policies
base.select = select


if __name__ == "__main__":
    base.main()
