from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


def load_records(cache_dir: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for path in sorted(cache_dir.glob("*.jsonl")):
        if path.name.endswith(".failures.jsonl"):
            continue
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if rows:
            out[path.stem] = rows
    return out


def exact_mcnemar_p(n01: int, n10: int) -> float:
    n = n01 + n10
    if n == 0:
        return 1.0
    k = min(n01, n10)
    cumulative = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * cumulative)


def bootstrap_delta(a: list[int], b: list[int], samples: int = 10000, seed: int = 42) -> dict:
    if len(a) != len(b) or not a:
        return {"delta_pp": 0.0, "ci95_low_pp": 0.0, "ci95_high_pp": 0.0}
    rng = random.Random(seed)
    n = len(a)
    observed = 100.0 * (sum(b) - sum(a)) / n
    deltas = []
    for _ in range(samples):
        idx = [rng.randrange(n) for _ in range(n)]
        deltas.append(100.0 * (sum(b[i] for i in idx) - sum(a[i] for i in idx)) / n)
    deltas.sort()
    lo = deltas[int(0.025 * (samples - 1))]
    hi = deltas[int(0.975 * (samples - 1))]
    return {"delta_pp": observed, "ci95_low_pp": lo, "ci95_high_pp": hi}


def _eligible(row: dict, baseline: str, treatment: str) -> bool:
    cond = row.get("conditions", {})
    if baseline not in cond or treatment not in cond:
        return False
    if "compute_matched_direct" not in {baseline, treatment}:
        return True

    # Fixed-call rows already record the two-stage compute budget in cost metadata.
    # The old analyzer incorrectly looked for conditions[*].budget_reached, a field
    # that run_magic_peer_matrix.py never emitted, excluding every matched pair.
    matched_cost = row.get("cost", {}).get("compute_matched_direct", {})
    return bool(matched_cost.get("fixed_two_stage")) and int(matched_cost.get("logical_llm_calls", 0)) >= 2


def paired_condition(rows: list[dict], baseline: str, treatment: str) -> dict | None:
    pairs = []
    excluded_budget_mismatch = 0
    for row in rows:
        cond = row.get("conditions", {})
        if baseline not in cond or treatment not in cond:
            continue
        if not _eligible(row, baseline, treatment):
            excluded_budget_mismatch += 1
            continue
        pairs.append((int(bool(cond[baseline].get("conflict_detected"))), int(bool(cond[treatment].get("conflict_detected")))))
    if not pairs:
        return None
    a = [x for x, _ in pairs]
    b = [y for _, y in pairs]
    n01 = sum(x == 0 and y == 1 for x, y in pairs)
    n10 = sum(x == 1 and y == 0 for x, y in pairs)
    return {
        "n": len(pairs),
        "excluded_budget_mismatch": excluded_budget_mismatch,
        "baseline_rate": sum(a) / len(a),
        "treatment_rate": sum(b) / len(b),
        "discordant_baseline0_treatment1": n01,
        "discordant_baseline1_treatment0": n10,
        "mcnemar_exact_p": exact_mcnemar_p(n01, n10),
        "bootstrap": bootstrap_delta(a, b),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="results/magic_peer_matrix")
    ap.add_argument("--out", default="results/magic_peer_matrix_paired_stats.json")
    args = ap.parse_args()

    model_rows = load_records(Path(args.cache_dir))
    comparisons = {
        "llm_vs_direct": ("direct", "rashomon_worlds_llm_scorer"),
        "llm_vs_compute_matched": ("compute_matched_direct", "rashomon_worlds_llm_scorer"),
        "deberta_vs_direct": ("direct", "rashomon_worlds_deberta_scorer"),
        "deberta_vs_llm": ("rashomon_worlds_llm_scorer", "rashomon_worlds_deberta_scorer"),
    }
    result = {
        "metric": "MAGIC conflict identification on released conflict rows (paired recall diagnostic)",
        "compute_matched_policy": (
            "Compute-matched pairs are eligible when the row cost metadata confirms the fixed two-stage baseline "
            "(fixed_two_stage=true and logical_llm_calls>=2)."
        ),
        "models": {},
    }
    for model, rows in model_rows.items():
        result["models"][model] = {
            name: paired_condition(rows, base, treat)
            for name, (base, treat) in comparisons.items()
        }

    aggregate = {}
    for name, (base, treat) in comparisons.items():
        pooled = []
        for rows in model_rows.values():
            pooled.extend(rows)
        aggregate[name] = paired_condition(pooled, base, treat)
    result["aggregate_descriptive"] = aggregate
    result["interpretation"] = (
        "Primary evidence is the per-model paired effect and confidence interval. "
        "Do not treat pooled examples across different model families as one independent statistical sample."
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
