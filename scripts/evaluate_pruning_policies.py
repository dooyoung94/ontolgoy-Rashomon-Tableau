from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def load_result(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ranked_relations(record: dict) -> list[str]:
    scores = {r: v["support"] for r, v in record["scores"].items()}
    return sorted(scores, key=lambda r: (-scores[r], r))


def select(record: dict, policy: dict) -> list[str]:
    scores = {r: v["support"] for r, v in record["scores"].items()}
    ranked = ranked_relations(record)
    kind = policy["type"]
    if kind == "topk":
        return ranked[: policy["k"]]
    if kind == "threshold":
        return [r for r in ranked if scores[r] >= policy["tau"]]
    if kind == "rashomon":
        best = max(scores.values())
        epsilon = policy["epsilon"]
        return [r for r in ranked if scores[r] >= best - epsilon]
    if kind == "all":
        return ranked
    raise ValueError(f"unknown policy: {kind}")


def evaluate(records: list[dict], policy: dict) -> dict:
    sizes: list[int] = []
    survival: list[bool] = []
    by_hop: dict[str, dict[str, float]] = {}

    for record in records:
        active = select(record, policy)
        ok = record["gold_relation"] in active
        sizes.append(len(active))
        survival.append(ok)
        hop = str(record["hop_count"])
        bucket = by_hop.setdefault(hop, {"n": 0, "survive": 0, "size": 0})
        bucket["n"] += 1
        bucket["survive"] += int(ok)
        bucket["size"] += len(active)

    n = len(records)
    survived = sum(survival)
    return {
        "definition": policy,
        "gold_survival": survived / n,
        "pruning_regret": 1.0 - survived / n,
        "avg_active_hypotheses": sum(sizes) / n,
        "median_active_hypotheses": statistics.median(sizes),
        "max_active_hypotheses": max(sizes),
        "by_hop": {
            hop: {
                "n": int(bucket["n"]),
                "gold_survival": bucket["survive"] / bucket["n"],
                "avg_active_hypotheses": bucket["size"] / bucket["n"],
            }
            for hop, bucket in sorted(by_hop.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Executed DeBERTa result JSON containing records/scores")
    parser.add_argument("--output", default="results/wn18rr_pruning_policy_ablation_50.json")
    args = parser.parse_args()

    source = load_result(Path(args.input))
    records = source["records"]
    policies = {
        "top1": {"type": "topk", "k": 1},
        "top3_tog_style": {"type": "topk", "k": 3},
        "top5": {"type": "topk", "k": 5},
        "threshold_0.7": {"type": "threshold", "tau": 0.7},
        "threshold_0.5": {"type": "threshold", "tau": 0.5},
        "rashomon_eps_0.01": {"type": "rashomon", "epsilon": 0.01},
        "rashomon_eps_0.03": {"type": "rashomon", "epsilon": 0.03},
        "rashomon_eps_0.05": {"type": "rashomon", "epsilon": 0.05},
        "rashomon_eps_0.10": {"type": "rashomon", "epsilon": 0.10},
        "no_pruning": {"type": "all"},
    }

    results = {name: evaluate(records, policy) for name, policy in policies.items()}
    output = {
        "protocol": {
            "dataset": source.get("protocol", {}).get("dataset", "WN18RR"),
            "n": len(records),
            "scorer": source.get("protocol", {}).get("scorer"),
            "candidate_relations": source.get("protocol", {}).get("candidate_relations"),
            "scope": "relation-hypothesis pruning diagnostic on frozen executed scores; not yet iterative ToG path-search",
            "gold_policy": "evaluation only; not used in selection",
        },
        "policies": results,
        "comparisons": {
            "rashomon_eps_0.05_vs_top3": {
                "survival_gain_pp": 100 * (results["rashomon_eps_0.05"]["gold_survival"] - results["top3_tog_style"]["gold_survival"]),
                "avg_hypothesis_delta": results["rashomon_eps_0.05"]["avg_active_hypotheses"] - results["top3_tog_style"]["avg_active_hypotheses"],
            },
            "rashomon_eps_0.05_vs_top5": {
                "survival_gain_pp": 100 * (results["rashomon_eps_0.05"]["gold_survival"] - results["top5"]["gold_survival"]),
                "avg_hypothesis_delta": results["rashomon_eps_0.05"]["avg_active_hypotheses"] - results["top5"]["avg_active_hypotheses"],
            },
            "rashomon_eps_0.10_vs_top5": {
                "survival_gain_pp": 100 * (results["rashomon_eps_0.10"]["gold_survival"] - results["top5"]["gold_survival"]),
                "avg_hypothesis_delta": results["rashomon_eps_0.10"]["avg_active_hypotheses"] - results["top5"]["avg_active_hypotheses"],
            },
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
