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
import json
import sys
from collections import defaultdict
from pathlib import Path


BASE_PATH = Path(__file__).with_name("evaluate_webqsp_pruning_wikidata.py")
spec = importlib.util.spec_from_file_location("webqsp_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"기존 WebQSP 평가기를 불러올 수 없습니다: {BASE_PATH}")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
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
_DIAG = defaultdict(lambda: {"boundary_checks": 0, "activations": 0, "extra_selected": 0, "margins": []})


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
    d = _DIAG[state.name]
    d["boundary_checks"] += 1
    d["margins"].append(float(margin))

    if margin > tau:
        return ranked[:k]

    d["activations"] += 1
    threshold = score_k - delta
    chosen = [p for p in ranked if base.path_score(p, scores) >= threshold][: state.max_width]
    d["extra_selected"] += max(0, len(chosen) - k)
    return chosen


def _inject_diagnostics() -> None:
    output = None
    for i, arg in enumerate(sys.argv):
        if arg == "--output" and i + 1 < len(sys.argv):
            output = Path(sys.argv[i + 1])
            break
        if arg.startswith("--output="):
            output = Path(arg.split("=", 1)[1])
            break
    if output is None or not output.exists():
        return
    data = json.loads(output.read_text(encoding="utf-8"))
    diagnostics = {}
    for name, raw in _DIAG.items():
        checks = int(raw["boundary_checks"])
        activations = int(raw["activations"])
        margins = list(raw["margins"])
        diagnostics[name] = {
            "boundary_checks": checks,
            "activations": activations,
            "activation_rate": activations / checks if checks else 0.0,
            "extra_selected_total": int(raw["extra_selected"]),
            "extra_selected_per_activation": raw["extra_selected"] / activations if activations else 0.0,
            "mean_boundary_margin": sum(margins) / len(margins) if margins else None,
            "min_boundary_margin": min(margins) if margins else None,
            "max_boundary_margin": max(margins) if margins else None,
        }
    data["conditional_badp_diagnostics"] = diagnostics
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


base.policy_templates = policy_templates
base.select = select


if __name__ == "__main__":
    base.main()
    _inject_diagnostics()
