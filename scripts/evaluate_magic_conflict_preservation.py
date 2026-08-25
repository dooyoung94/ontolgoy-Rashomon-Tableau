from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median, quantiles


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relevance(x: dict) -> float:
    # Side-agnostic semantic decisiveness: support + contradiction = 1 - unresolved.
    return 1.0 - float(x["unresolved"])


def rank_paths(paths: list[dict]) -> list[dict]:
    return sorted(
        paths,
        key=lambda x: (
            -relevance(x),
            -max(float(x["support"]), float(x["contradiction"])),
            json.dumps(x.get("path", []), ensure_ascii=False),
        ),
    )


def select(paths: list[dict], policy: dict) -> list[dict]:
    ranked = rank_paths(paths)
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
        best_loss = 1.0 - relevance(ranked[0])
        max_loss = (1.0 + float(policy["epsilon"])) * best_loss
        return [x for x in ranked if (1.0 - relevance(x)) <= max_loss]
    if kind == "boundary":
        k = int(policy["k"])
        eps = float(policy["epsilon"])
        if len(ranked) <= k:
            return ranked
        cutoff = relevance(ranked[k - 1])
        # Keep Top-K plus candidates that are epsilon-indistinguishable from the K-th boundary.
        return [x for x in ranked if relevance(x) >= cutoff - eps]
    if kind == "all":
        return ranked
    raise ValueError(f"unknown policy: {policy}")


def gold_count(paths: list[dict]) -> int:
    return sum(bool(x.get("gold_path")) for x in paths)


def summarize(rows: list[dict], policy: dict) -> dict:
    if not rows:
        return {
            "n": 0,
            "query_gold_survival": 0.0,
            "conflict_information_loss": 0.0,
            "avg_selected_paths": 0.0,
            "retained_gold_precision_micro": 0.0,
            "retained_gold_recall_micro": 0.0,
            "retained_gold_f1_micro": 0.0,
            "invalid_retention_rate_micro": 0.0,
        }
    query_hits = 0
    retained = 0
    retained_gold = 0
    available_gold = 0
    widths = []
    query_precisions = []
    for q in rows:
        chosen = select(q["path_scores"], policy)
        g = gold_count(chosen)
        gt = gold_count(q["path_scores"])
        query_hits += int(g > 0)
        retained += len(chosen)
        retained_gold += g
        available_gold += gt
        widths.append(len(chosen))
        query_precisions.append(g / len(chosen) if chosen else 0.0)
    precision = retained_gold / retained if retained else 0.0
    recall = retained_gold / available_gold if available_gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    survival = query_hits / len(rows)
    return {
        "n": len(rows),
        "query_gold_survival": survival,
        "conflict_information_loss": 1.0 - survival,
        "avg_selected_paths": sum(widths) / len(widths),
        "median_selected_paths": float(median(widths)),
        "max_selected_paths": max(widths),
        "retained_gold_paths": retained_gold,
        "available_gold_paths": available_gold,
        "retained_paths_total": retained,
        "retained_gold_precision_micro": precision,
        "retained_gold_recall_micro": recall,
        "retained_gold_f1_micro": f1,
        "invalid_retention_rate_micro": 1.0 - precision,
        "avg_query_gold_precision": sum(query_precisions) / len(query_precisions),
    }


def support_dominant(x: dict) -> bool:
    s = float(x["support"])
    return s > max(float(x["contradiction"]), float(x["unresolved"]))


def contradiction_dominant(x: dict) -> bool:
    c = float(x["contradiction"])
    return c > max(float(x["support"]), float(x["unresolved"]))


def row_exact(rows: list[dict], policy: dict) -> dict:
    eligible = [
        row for row in rows
        if row.get("queries") and all(
            q.get("path_scores") and gold_count(q["path_scores"]) > 0
            for q in row["queries"]
        )
    ]
    exact = 0
    for row in eligible:
        exact += int(all(gold_count(select(q["path_scores"], policy)) > 0 for q in row["queries"]))
    return {
        "eligible_rows": len(eligible),
        "structured_row_exact_conflict_evidence_preservation": exact / len(eligible) if eligible else 0.0,
    }


def candidate_count_strata(recoverable: list[dict], policies: dict[str, dict]) -> dict:
    bins = {
        "paths_eq_1": lambda n: n == 1,
        "paths_eq_2": lambda n: n == 2,
        "paths_eq_3": lambda n: n == 3,
        "paths_eq_4": lambda n: n == 4,
        "paths_ge_5": lambda n: n >= 5,
    }
    out = {}
    for label, pred in bins.items():
        subset = [q for q in recoverable if pred(len(q["path_scores"]))]
        out[label] = {
            "n": len(subset),
            "avg_candidate_paths": (
                sum(len(q["path_scores"]) for q in subset) / len(subset) if subset else 0.0
            ),
            "policies": {name: summarize(subset, policy) for name, policy in policies.items()},
        }
    return out


def cumulative_branching_strata(recoverable: list[dict], policies: dict[str, dict]) -> dict:
    out = {}
    for threshold in (2, 3, 4, 5):
        subset = [q for q in recoverable if len(q["path_scores"]) >= threshold]
        out[f"paths_ge_{threshold}"] = {
            "n": len(subset),
            "policies": {name: summarize(subset, p) for name, p in policies.items()},
        }
    return out


def margin(q: dict) -> float | None:
    scores = sorted((relevance(x) for x in q["path_scores"]), reverse=True)
    return scores[0] - scores[1] if len(scores) >= 2 else None


def ambiguity_quartiles(recoverable: list[dict], policies: dict[str, dict]) -> dict:
    branching = [q for q in recoverable if len(q["path_scores"]) >= 2]
    margins = [margin(q) for q in branching]
    if len(margins) < 4:
        return {}
    q1, q2, q3 = quantiles(margins, n=4, method="inclusive")
    bins = [
        ("Q1_most_ambiguous", lambda x: x <= q1),
        ("Q2", lambda x: q1 < x <= q2),
        ("Q3", lambda x: q2 < x <= q3),
        ("Q4_least_ambiguous", lambda x: x > q3),
    ]
    out = {"margin_boundaries": {"q1": q1, "q2": q2, "q3": q3}, "bins": {}}
    for label, pred in bins:
        subset = [q for q in branching if pred(float(margin(q)))]
        vals = [float(margin(q)) for q in subset]
        out["bins"][label] = {
            "n": len(subset),
            "median_top2_margin": median(vals) if vals else None,
            "avg_candidate_paths": (
                sum(len(q["path_scores"]) for q in subset) / len(subset) if subset else 0.0
            ),
            "policies": {name: summarize(subset, p) for name, p in policies.items()},
        }
    out["warning"] = (
        "Top-2 score margin is a descriptive ambiguity proxy. Candidate branching and margin are correlated; "
        "this analysis does not establish an independent causal effect of score ambiguity."
    )
    return out


def exact_sign_test(a_wins: int, b_wins: int) -> float:
    n = a_wins + b_wins
    if n == 0:
        return 1.0
    k = min(a_wins, b_wins)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def paired_comparison(rows: list[dict], policy_a: dict, policy_b: dict) -> dict:
    a_only = b_only = both = neither = 0
    for q in rows:
        a = gold_count(select(q["path_scores"], policy_a)) > 0
        b = gold_count(select(q["path_scores"], policy_b)) > 0
        if a and b:
            both += 1
        elif a:
            a_only += 1
        elif b:
            b_only += 1
        else:
            neither += 1
    return {
        "n": len(rows),
        "a_only_wins": a_only,
        "b_only_wins": b_only,
        "both_survive": both,
        "neither_survives": neither,
        "exact_two_sided_sign_p": exact_sign_test(a_only, b_only),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="results/magic_conflict_preservation_ablation.json")
    args = ap.parse_args()

    data = load(Path(args.input))
    rows = data["rows"]
    queries = [q for row in rows for q in row.get("queries", [])]
    candidate_queries = [q for q in queries if q.get("path_scores")]
    recoverable = [q for q in candidate_queries if gold_count(q["path_scores"]) > 0]

    policies = {
        "top1": {"type": "topk", "k": 1},
        "top3_tog_style": {"type": "topk", "k": 3},
        "top5": {"type": "topk", "k": 5},
        "rashomon_add_eps_0.05": {"type": "rashomon_additive", "epsilon": 0.05},
        "rashomon_add_eps_0.10": {"type": "rashomon_additive", "epsilon": 0.10},
        "rashomon_relative_loss_0.25": {"type": "rashomon_relative_loss", "epsilon": 0.25},
        "boundary_top3_eps_0.01": {"type": "boundary", "k": 3, "epsilon": 0.01},
        "boundary_top5_eps_0.01": {"type": "boundary", "k": 5, "epsilon": 0.01},
        "no_pruning": {"type": "all"},
    }

    policy_results = {}
    for name, policy in policies.items():
        bipolar = [
            q for q in candidate_queries
            if any(support_dominant(x) for x in q["path_scores"])
            and any(contradiction_dominant(x) for x in q["path_scores"])
        ]
        retained_bipolar = sum(
            int(
                any(support_dominant(x) for x in select(q["path_scores"], policy))
                and any(contradiction_dominant(x) for x in select(q["path_scores"], policy))
            )
            for q in bipolar
        )
        policy_results[name] = {
            "definition": policy,
            "recoverable_queries": summarize(recoverable, policy),
            "row_exact": row_exact(rows, policy),
            "deberta_defined_bipolar": {
                "n": len(bipolar),
                "dual_side_retention": retained_bipolar / len(bipolar) if bipolar else 0.0,
                "warning": "Secondary only: both side labels are defined by DeBERTa, not external gold.",
            },
        }

    ge5 = [q for q in recoverable if len(q["path_scores"]) >= 5]
    ge4 = [q for q in recoverable if len(q["path_scores"]) >= 4]

    result = {
        "protocol": {
            "benchmark": data.get("benchmark"),
            "source_method": data.get("method"),
            "deberta_model": data.get("deberta_model"),
            "source_rows": len(rows),
            "source_queries": len(queries),
            "candidate_queries": len(candidate_queries),
            "gold_conflict_path_recoverable_queries": len(recoverable),
            "gold_conflict_path_recoverability_ceiling": len(recoverable) / len(queries) if queries else 0.0,
            "gold_definition": "MAGIC perturb_triplet provenance; gold_path is external to the DeBERTa scorer and attached after scoring.",
            "selection_score": "support + contradiction = 1 - unresolved; side-agnostic semantic decisiveness",
            "validity_definition": "A retained path is externally valid for this task iff it covers the paired MAGIC perturb path (gold_path=true).",
            "scope_warning": "Frozen candidate-path preservation diagnostic; not final truth resolution and not a full ToG reproduction.",
        },
        "source_deberta_result": data.get("overall", {}),
        "policies": policy_results,
        "candidate_count_strata": candidate_count_strata(recoverable, policies),
        "cumulative_branching_strata": cumulative_branching_strata(recoverable, policies),
        "score_ambiguity_quartiles": ambiguity_quartiles(recoverable, policies),
        "paired_tests": {
            "ge5_rashomon_0.10_vs_top5": paired_comparison(
                ge5, policies["rashomon_add_eps_0.10"], policies["top5"]
            ),
            "ge4_rashomon_0.05_vs_top3": paired_comparison(
                ge4, policies["rashomon_add_eps_0.05"], policies["top3_tog_style"]
            ),
            "all_boundary_top3_0.01_vs_top3": paired_comparison(
                recoverable, policies["boundary_top3_eps_0.01"], policies["top3_tog_style"]
            ),
            "ge5_boundary_top5_0.01_vs_top5": paired_comparison(
                ge5, policies["boundary_top5_eps_0.01"], policies["top5"]
            ),
        },
        "interpretation_rules": {
            "preservation": "Use query_gold_survival / conflict_information_loss.",
            "retained_value_validity": "Use external-gold retained precision/recall/F1 and invalid_retention_rate; do not infer validity only from set size.",
            "ambiguity": "Treat top-2 margin as descriptive until separated from branching in a larger controlled experiment.",
            "boundary_policy": "Exploratory extension targeting near-ties at the actual Top-K pruning boundary; report separately from classical Rashomon-inspired best-relative retention.",
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    compact = {
        "protocol": result["protocol"],
        "overall": {k: v["recoverable_queries"] for k, v in policy_results.items()},
        "paths_ge_5": result["cumulative_branching_strata"]["paths_ge_5"],
        "paired_tests": result["paired_tests"],
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()
