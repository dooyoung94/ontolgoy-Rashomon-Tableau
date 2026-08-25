from __future__ import annotations

"""WN18RR 반복 탐색에서 조건부 BADP를 평가한다.

기존 budgeted evaluator의 candidate generation, DeBERTa scorer, viability 계산 및
평가 프로토콜은 그대로 사용하고 pruning operator만 확장한다.
"""

import importlib.util
from pathlib import Path


BASE_PATH = Path(__file__).with_name("evaluate_iterative_pruning_budgeted.py")
spec = importlib.util.spec_from_file_location("iterative_budgeted_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"기존 반복 평가기를 불러올 수 없습니다: {BASE_PATH}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


CONDITIONAL = {
    "conditional_badp_top3_tau_0.005_delta_0.005": (3, 0.005, 0.005),
    "conditional_badp_top3_tau_0.010_delta_0.005": (3, 0.010, 0.005),
    "conditional_badp_top3_tau_0.020_delta_0.010": (3, 0.020, 0.010),
    "conditional_badp_top5_tau_0.010_delta_0.010": (5, 0.010, 0.010),
    "conditional_badp_top5_tau_0.020_delta_0.010": (5, 0.020, 0.010),
    "conditional_badp_top5_tau_0.050_delta_0.020": (5, 0.050, 0.020),
}

_original_policies = base.policies
_original_select = base.select


def policies():
    out = _original_policies()
    for name, (k, tau, delta) in CONDITIONAL.items():
        out[name] = base.PolicyState(
            name=name,
            family=f"conditional_badp_top{k}",
            kind="conditional_boundary",
            value=delta,
            boundary_k=k,
            max_width=10,
        )
    return out


def select(cands, st, scores):
    if st.kind != "conditional_boundary":
        return _original_select(cands, st, scores)

    ranked = sorted(cands, key=lambda p: (-base.pscore(p, scores), base.pkey(p)))
    if not ranked:
        return []

    k, tau, delta = CONDITIONAL[st.name]
    if len(ranked) <= k:
        return ranked

    score_k = base.pscore(ranked[k - 1], scores)
    score_k1 = base.pscore(ranked[k], scores)
    boundary_margin = score_k - score_k1

    if boundary_margin > tau:
        return ranked[:k]

    threshold = score_k - delta
    return [p for p in ranked if base.pscore(p, scores) >= threshold][: st.max_width]


base.policies = policies
base.select = select


if __name__ == "__main__":
    base.main()
