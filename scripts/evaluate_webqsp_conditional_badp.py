from __future__ import annotations

"""WebQSP 조건부 BADP 평가기.

기존 ``evaluate_webqsp_pruning_wikidata.py``의 후보 생성·DeBERTa 점수화·평가
파이프라인은 그대로 두고, 가지치기 연산자만 조건부 BADP로 확장한다.

조건부 BADP:
    margin_K = s_(K) - s_(K+1)
    if margin_K <= tau:
        keep {p: s(p) >= s_(K) - delta}
    else:
        keep Top-K

즉 tau는 발동 조건, delta는 발동 후 추가 보존 폭이다.
"""

import importlib.util
from pathlib import Path


BASE_PATH = Path(__file__).with_name("evaluate_webqsp_pruning_wikidata.py")
spec = importlib.util.spec_from_file_location("webqsp_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"기존 WebQSP 평가기를 불러올 수 없습니다: {BASE_PATH}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


CONDITIONAL = {
    "conditional_badp_top3_tau_0.005_delta_0.005": (3, 0.005, 0.005),
    "conditional_badp_top3_tau_0.010_delta_0.005": (3, 0.010, 0.005),
    "conditional_badp_top3_tau_0.020_delta_0.010": (3, 0.020, 0.010),
    "conditional_badp_top5_tau_0.010_delta_0.010": (5, 0.010, 0.010),
    "conditional_badp_top5_tau_0.020_delta_0.010": (5, 0.020, 0.010),
}

_original_policy_templates = base.policy_templates
_original_select = base.select


def policy_templates():
    out = _original_policy_templates()
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


def select(paths, state, scores):
    if state.kind != "conditional_boundary":
        return _original_select(paths, state, scores)

    ranked = sorted(paths, key=lambda p: (-base.path_score(p, scores), base.path_key(p)))
    if not ranked:
        return []

    k, tau, delta = CONDITIONAL[state.name]
    if len(ranked) <= k:
        return ranked

    score_k = base.path_score(ranked[k - 1], scores)
    score_k1 = base.path_score(ranked[k], scores)
    margin = score_k - score_k1

    # 경계가 충분히 분리되면 기존 Top-K를 그대로 사용한다.
    if margin > tau:
        return ranked[:k]

    # 경계가 불확실할 때만 K번째 점수 주변을 제한적으로 추가 보존한다.
    threshold = score_k - delta
    return [p for p in ranked if base.path_score(p, scores) >= threshold][: state.max_width]


base.policy_templates = policy_templates
base.select = select


if __name__ == "__main__":
    base.main()
