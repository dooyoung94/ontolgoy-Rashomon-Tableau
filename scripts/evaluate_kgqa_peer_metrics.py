from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from statistics import mean


def norm(x: str) -> str:
    x = x.strip().lower()
    x = re.sub(r"\s+", " ", x)
    x = re.sub(r"^[\s\"'`]+|[\s\"'`]+$", "", x)
    return x


def as_set(v) -> set[str]:
    if v is None:
        return set()
    if isinstance(v, str):
        return {norm(v)} if norm(v) else set()
    return {norm(str(x)) for x in v if norm(str(x))}


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0


def evaluate(rows: list[dict]) -> dict:
    ems = []
    hit1s = []
    macro_f1s = []
    tp = fp = fn = 0
    evidence_tp = evidence_fp = evidence_fn = 0
    widths = []
    expanded = []
    calls = []
    tokens = []
    latencies = []
    regrets = []

    for row in rows:
        gold = as_set(row.get("gold_answers", []))
        pred = as_set(row.get("predicted_answers", []))
        ems.append(float(pred == gold))
        p = safe_div(len(pred & gold), len(pred))
        r = safe_div(len(pred & gold), len(gold))
        macro_f1s.append(f1(p, r))
        first = norm(str(row.get("top1_answer", "")))
        if not first and row.get("predicted_answers"):
            first = norm(str(row["predicted_answers"][0]))
        hit1s.append(float(first in gold if first else False))
        tp += len(pred & gold)
        fp += len(pred - gold)
        fn += len(gold - pred)

        ge = as_set(row.get("gold_evidence", []))
        pe = as_set(row.get("retained_evidence", []))
        evidence_tp += len(ge & pe)
        evidence_fp += len(pe - ge)
        evidence_fn += len(ge - pe)

        if row.get("avg_active_width") is not None:
            widths.append(float(row["avg_active_width"]))
        if row.get("expanded_candidates") is not None:
            expanded.append(float(row["expanded_candidates"]))
        if row.get("llm_calls") is not None:
            calls.append(float(row["llm_calls"]))
        if row.get("context_tokens") is not None:
            tokens.append(float(row["context_tokens"]))
        if row.get("latency_ms") is not None:
            latencies.append(float(row["latency_ms"]))
        if row.get("pruning_regret") is not None:
            regrets.append(float(bool(row["pruning_regret"])))

    micro_p = safe_div(tp, tp + fp)
    micro_r = safe_div(tp, tp + fn)
    ev_p = safe_div(evidence_tp, evidence_tp + evidence_fp)
    ev_r = safe_div(evidence_tp, evidence_tp + evidence_fn)
    return {
        "n": len(rows),
        "answer_set_exact_match": mean(ems) if ems else 0.0,
        "macro_answer_f1": mean(macro_f1s) if macro_f1s else 0.0,
        "micro_answer_precision": micro_p,
        "micro_answer_recall": micro_r,
        "micro_answer_f1": f1(micro_p, micro_r),
        "hit_at_1": mean(hit1s) if hit1s else 0.0,
        "evidence_precision": ev_p,
        "evidence_recall": ev_r,
        "evidence_f1": f1(ev_p, ev_r),
        "query_pruning_regret_rate": mean(regrets) if regrets else None,
        "avg_active_width": mean(widths) if widths else None,
        "avg_expanded_candidates": mean(expanded) if expanded else None,
        "avg_llm_calls": mean(calls) if calls else None,
        "avg_context_tokens": mean(tokens) if tokens else None,
        "avg_latency_ms": mean(latencies) if latencies else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Normalize KGQA outputs to the common peer-comparison metrics used in PEER_COMPARISON.md")
    ap.add_argument("--input", required=True, help="JSONL rows with gold_answers and predicted_answers")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--method", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    rows = [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip()]
    out = {
        "protocol": {
            "dataset": args.dataset,
            "method": args.method,
            "answer_normalization": "lowercase + trim + whitespace collapse + quote trim",
            "required_fields": ["gold_answers", "predicted_answers"],
            "optional_fields": [
                "top1_answer", "gold_evidence", "retained_evidence", "pruning_regret",
                "avg_active_width", "expanded_candidates", "llm_calls", "context_tokens", "latency_ms"
            ],
            "warning": "Use the same answer alias/entity normalization across every reproduced system. Paper-reported Accuracy/EM/Hit@1 values remain contextual references until reproduced through this evaluator."
        },
        "metrics": evaluate(rows),
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
