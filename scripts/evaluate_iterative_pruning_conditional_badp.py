from __future__ import annotations

"""WN18RR 반복 탐색에서 조건부 BADP를 평가한다.

기존 budgeted evaluator의 candidate generation, DeBERTa scorer, viability 계산 및
평가 프로토콜은 그대로 사용하고 pruning operator만 확장한다.
"""

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path


BASE_PATH = Path(__file__).with_name("evaluate_iterative_pruning_budgeted.py")
spec = importlib.util.spec_from_file_location("iterative_budgeted_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"기존 반복 평가기를 불러올 수 없습니다: {BASE_PATH}")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
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
_DIAG = defaultdict(lambda: {"boundary_checks": 0, "activations": 0, "extra_selected": 0, "margins": []})


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
    d = _DIAG[st.name]
    d["boundary_checks"] += 1
    d["margins"].append(float(boundary_margin))

    if boundary_margin > tau:
        return ranked[:k]

    d["activations"] += 1
    threshold = score_k - delta
    chosen = [p for p in ranked if base.pscore(p, scores) >= threshold][: st.max_width]
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


base.policies = policies
base.select = select


if __name__ == "__main__":
    base.main()
    _inject_diagnostics()
