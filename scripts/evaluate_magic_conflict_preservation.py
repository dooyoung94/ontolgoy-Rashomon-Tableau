from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import median


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relevance(path_score: dict) -> float:
    """Side-agnostic semantic decisiveness.

    Support and contradiction are both informative for preservation. Neutral / unresolved
    evidence is not. Since the NLI scores are normalized, 1 - unresolved is exactly
    support + contradiction and does not privilege either side.
    """
    return 1.0 - float(path_score["unresolved"])


def rank(paths: list[dict]) -> list[dict]:
    return sorted(
        paths,
        key=lambda x: (
            -relevance(x),
            -max(float(x["support"]), float(x["contradiction"])),
            json.dumps(x.get("path", []), ensure_ascii=False),
        ),
    )


def select(paths: list[dict], policy: dict) -> list[dict]:
    ranked = rank(paths)
    if not ranked:
        return []
    kind = policy["type"]
    if kind == "topk":
        return ranked[: int(policy["k"])]
    if kind == "rashomon_additive":
        best = relevance(ranked[0])
        eps = float(policy["epsilon"])
        return [x for x in ranked if relevance(x) >= best - eps]
    if kind == "rashomon_relative_loss":
        # Loss L=1-relevance=unresolved. Classical-style relative near-optimality:
        # L <= (1+epsilon)L*. This is a scale-aware ablation, not assumed superior.
        best_loss = 1.0 - relevance(ranked[0])
        max_loss = (1.0 + float(policy["epsilon"])) * best_loss
        return [x for x in ranked if (1.0 - relevance(x)) <= max_loss]
    if kind == "all":
        return ranked
    raise ValueError(f"unknown policy: {policy}")


def contradiction_dominant(x: dict) -> bool:
    c = float(x["contradiction"])
    return c > max(float(x["support"]), float(x["unresolved"]))


def support_dominant(x: dict) -> bool:
    s = float(x["support"])
    return s > max(float(x["contradiction"]), float(x["unresolved"]))


def evaluate_policy(queries: list[dict], policy: dict) -> dict:
    candidate_queries = [q for q in queries if q["path_scores"]]
    recoverable = [q for q in candidate_queries if any(bool(x.get("gold_path")) for x in q["path_scores"])]
    branching = [q for q in recoverable if len(q["path_scores"]) >= 2]

    def summarize_subset(rows: list[dict]) -> dict:
        if not rows:
            return {
                "n": 0,
                "gold_conflict_path_survival": 0.0,
                "conflict_information_loss": 0.0,
                "avg_selected_paths": 0.0,
                "median_selected_paths": 0.0,
                "max_selected_paths": 0,
            }
        survived = 0
        widths: list[int] = []
        for q in rows:
            chosen = select(q["path_scores"], policy)
            survived += int(any(bool(x.get("gold_path")) for x in chosen))
            widths.append(len(chosen))
        survival = survived / len(rows)
        return {
            "n": len(rows),
            "gold_conflict_path_survival": survival,
            "conflict_information_loss": 1.0 - survival,
            "avg_selected_paths": sum(widths) / len(widths),
            "median_selected_paths": float(median(widths)),
            "max_selected_paths": max(widths),
        }

    # Secondary diagnostic only: these sides are defined by DeBERTa itself, not MAGIC gold.
    bipolar_recoverable = [
        q
        for q in candidate_queries
        if any(support_dominant(x) for x in q["path_scores"])
        and any(contradiction_dominant(x) for x in q["path_scores"])
    ]
    bipolar_retained = 0
    for q in bipolar_recoverable:
        chosen = select(q["path_scores"], policy)
        bipolar_retained += int(
            any(support_dominant(x) for x in chosen)
            and any(contradiction_dominant(x) for x in chosen)
        )

    model_conflict = 0
    widths_all = []
    for q in candidate_queries:
        chosen = select(q["path_scores"], policy)
        widths_all.append(len(chosen))
        model_conflict += int(any(contradiction_dominant(x) for x in chosen))

    return {
        "definition": policy,
        "recoverable_queries": summarize_subset(recoverable),
        "branching_recoverable_queries": summarize_subset(branching),
        "candidate_query_model_conflict_recall": (
            model_conflict / len(candidate_queries) if candidate_queries else 0.0
        ),
        "candidate_query_avg_selected_paths": (
            sum(widths_all) / len(widths_all) if widths_all else 0.0
        ),
        "deberta_defined_bipolar": {
            "n": len(bipolar_recoverable),
            "dual_side_retention": (
                bipolar_retained / len(bipolar_recoverable) if bipolar_recoverable else 0.0
            ),
            "warning": "Secondary diagnostic only: support/contradiction side labels here are defined by the same DeBERTa scorer and are not external gold.",
        },
    }


def row_exact_preservation(rows: list[dict], policy: dict) -> dict:
    eligible = []
    for row in rows:
        queries = row.get("queries", [])
        if queries and all(
            q.get("path_scores")
            and any(bool(x.get("gold_path")) for x in q["path_scores"])
            for q in queries
        ):
            eligible.append(row)
    exact = 0
    for row in eligible:
        ok = True
        for q in row["queries"]:
            chosen = select(q["path_scores"], policy)
            if not any(bool(x.get("gold_path")) for x in chosen):
                ok = False
                break
        exact += int(ok)
    return {
        "eligible_rows": len(eligible),
        "structured_row_exact_conflict_evidence_preservation": exact / len(eligible) if eligible else 0.0,
    }


def stratum_metrics(queries: list[dict], policy: dict) -> dict:
    recoverable = [
        q
        for q in queries
        if q.get("path_scores")
        and any(bool(x.get("gold_path")) for x in q["path_scores"])
    ]
    out = {}
    for threshold in (2, 3, 4, 5):
        subset = [q for q in recoverable if len(q["path_scores"]) >= threshold]
        if not subset:
            continue
        survived = 0
        widths = []
        for q in subset:
            chosen = select(q["path_scores"], policy)
            survived += int(any(bool(x.get("gold_path")) for x in chosen))
            widths.append(len(chosen))
        out[f"paths_ge_{threshold}"] = {
            "n": len(subset),
            "gold_conflict_path_survival": survived / len(subset),
            "conflict_information_loss": 1.0 - survived / len(subset),
            "avg_selected_paths": sum(widths) / len(widths),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="results/magic_conflict_preservation_ablation.json")
    args = ap.parse_args()

    data = load(Path(args.input))
    rows = data["rows"]
    queries = [q for row in rows for q in row.get("queries", [])]
    candidate_queries = [q for q in queries if q.get("path_scores")]
    recoverable = [
        q for q in candidate_queries if any(bool(x.get("gold_path")) for x in q["path_scores"])
    ]

    policies = {
        "top1": {"type": "topk", "k": 1},
        "top3_tog_style": {"type": "topk", "k": 3},
        "top5": {"type": "topk", "k": 5},
        "rashomon_add_eps_0.03": {"type": "rashomon_additive", "epsilon": 0.03},
        "rashomon_add_eps_0.05": {"type": "rashomon_additive", "epsilon": 0.05},
        "rashomon_add_eps_0.10": {"type": "rashomon_additive", "epsilon": 0.10},
        "rashomon_relative_loss_0.25": {"type": "rashomon_relative_loss", "epsilon": 0.25},
        "rashomon_relative_loss_0.50": {"type": "rashomon_relative_loss", "epsilon": 0.50},
        "no_pruning": {"type": "all"},
    }

    results = {}
    for name, policy in policies.items():
        metrics = evaluate_policy(queries, policy)
        metrics["row_exact"] = row_exact_preservation(rows, policy)
        metrics["by_candidate_branching"] = stratum_metrics(queries, policy)
        results[name] = metrics

    top3 = results["top3_tog_style"]["recoverable_queries"]
    rash05 = results["rashomon_add_eps_0.05"]["recoverable_queries"]
    top5 = results["top5"]["recoverable_queries"]
    rash10 = results["rashomon_add_eps_0.10"]["recoverable_queries"]

    summary = {
        "protocol": {
            "benchmark": data.get("benchmark"),
            "source_method": data.get("method"),
            "deberta_model": data.get("deberta_model"),
            "source_rows": len(rows),
            "source_queries": len(queries),
            "candidate_queries": len(candidate_queries),
            "gold_conflict_path_recoverable_queries": len(recoverable),
            "gold_conflict_path_recoverability_ceiling": len(recoverable) / len(queries) if queries else 0.0,
            "gold_definition": "MAGIC perturb_triplet provenance; gold_path was attached only after DeBERTa scoring in the source run.",
            "selection_score": "semantic relevance = support + contradiction = 1 - unresolved; side-agnostic and label-blind",
            "task": "Given the fixed support claim original_triplet, measure whether pruning preserves at least one externally-gold contradictory multi-hop evidence path.",
            "scope_warning": "This is a conflict-evidence preservation ablation on frozen candidate paths/scores. It does not claim final conflict resolution or a full ToG reproduction.",
        },
        "source_deberta_result": data.get("overall", {}),
        "policies": results,
        "comparisons": {
            "rashomon_0.05_vs_top3": {
                "survival_gain_pp": 100.0 * (
                    rash05["gold_conflict_path_survival"] - top3["gold_conflict_path_survival"]
                ),
                "avg_selected_delta": rash05["avg_selected_paths"] - top3["avg_selected_paths"],
            },
            "rashomon_0.10_vs_top5": {
                "survival_gain_pp": 100.0 * (
                    rash10["gold_conflict_path_survival"] - top5["gold_conflict_path_survival"]
                ),
                "avg_selected_delta": rash10["avg_selected_paths"] - top5["avg_selected_paths"],
            },
        },
        "interpretation": {
            "primary_question": "Does pruning destroy externally-gold conflict evidence that was recoverable before pruning?",
            "positive_evidence": "Any survival below no-pruning is directly attributable to the pruning operator because candidate paths and DeBERTa scores are frozen.",
            "rashomon_status": "Report as an ablation, not assumed superior. The benchmark decides whether near-optimal retention improves the preservation-cost trade-off.",
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    compact = {
        "protocol": summary["protocol"],
        "policies": {
            k: {
                "recoverable": v["recoverable_queries"],
                "branching": v["branching_recoverable_queries"],
                "row_exact": v["row_exact"],
            }
            for k, v in results.items()
        },
        "comparisons": summary["comparisons"],
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()
