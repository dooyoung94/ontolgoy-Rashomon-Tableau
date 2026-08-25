from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from rashomon_tableau.deberta_world_scorer import DebertaWorldScorer
from rashomon_tableau.kg_multihop_benchmark import (
    KGTriple,
    candidate_relation_text,
    load_text_mappings,
    path_evidence_text,
    read_triples,
)

PathT = tuple[KGTriple, ...]
EdgeKey = tuple[str, str, str]


@dataclass
class PolicyState:
    name: str
    family: str
    kind: str
    value: float
    boundary_k: int | None = None
    safety_cap: int | None = 20
    active: list[PathT] = field(default_factory=list)
    success: bool = False
    success_depth: int | None = None
    expanded: int = 0
    selected: int = 0
    depth_steps: int = 0
    regret_events: int = 0
    had_regret: bool = False
    viable_candidates: int = 0
    viable_selected: int = 0
    pre_viable_by_depth: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    post_viable_by_depth: dict[int, int] = field(default_factory=lambda: defaultdict(int))


def load_examples(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def edge_key(edge: KGTriple) -> EdgeKey:
    return (edge.head, edge.relation, edge.tail)


def path_key(path: PathT) -> tuple[EdgeKey, ...]:
    return tuple(edge_key(e) for e in path)


def build_adjacency(train: list[KGTriple]) -> dict[str, list[KGTriple]]:
    out: dict[str, list[KGTriple]] = defaultdict(list)
    for triple in train:
        out[triple.head].append(triple)
    for node in out:
        out[node].sort(key=lambda e: (e.relation, e.tail))
    return out


def path_nodes(path: PathT, start: str) -> set[str]:
    nodes = {start}
    for edge in path:
        nodes.add(edge.tail)
    return nodes


def expand(active: list[PathT], start: str, adjacency: dict[str, list[KGTriple]]) -> list[PathT]:
    unique: dict[tuple[EdgeKey, ...], PathT] = {}
    for path in active:
        node = start if not path else path[-1].tail
        visited = path_nodes(path, start)
        for edge in adjacency.get(node, []):
            if edge.tail in visited:
                continue
            new_path = (*path, edge)
            unique[path_key(new_path)] = new_path
    return [unique[k] for k in sorted(unique)]


def can_reach(path: PathT, start: str, goal: str, remaining: int, adjacency: dict[str, list[KGTriple]]) -> bool:
    node = start if not path else path[-1].tail
    if node == goal:
        return True
    if remaining <= 0:
        return False
    visited = path_nodes(path, start)
    q = deque([(node, 0, visited)])
    while q:
        current, used, seen = q.popleft()
        if used >= remaining:
            continue
        for edge in adjacency.get(current, []):
            nxt = edge.tail
            if nxt in seen:
                continue
            if nxt == goal:
                return True
            q.append((nxt, used + 1, seen | {nxt}))
    return False


def score_new_edges(
    scorer: DebertaWorldScorer,
    paths: list[PathT],
    query: str,
    mappings,
    cache: dict[EdgeKey, float],
    batch_size: int,
) -> int:
    missing: dict[EdgeKey, KGTriple] = {}
    for path in paths:
        if not path:
            continue
        edge = path[-1]
        key = edge_key(edge)
        if key not in cache:
            missing[key] = edge
    if not missing:
        return 0
    edges = [missing[k] for k in sorted(missing)]
    scores = scorer.score_many(
        [query] * len(edges),
        [path_evidence_text([e], mappings) for e in edges],
        batch_size=batch_size,
    )
    for edge, score in zip(edges, scores):
        cache[edge_key(edge)] = score.support
    return len(edges)


def path_score(path: PathT, edge_scores: dict[EdgeKey, float]) -> float:
    if not path:
        return 0.0
    vals = [edge_scores[edge_key(e)] for e in path]
    return sum(vals) / len(vals)


def policy_templates() -> dict[str, PolicyState]:
    out: dict[str, PolicyState] = {
        "top3_tog_style": PolicyState("top3_tog_style", "fixed_topk", "topk", 3, safety_cap=3),
        "top5": PolicyState("top5", "fixed_topk", "topk", 5, safety_cap=5),
    }
    for eps in (0.01, 0.03, 0.05, 0.10):
        key = f"global_rashomon_eps_{eps:.2f}"
        out[key] = PolicyState(key, "global_rashomon", "global", eps, safety_cap=20)
    for eps in (0.10, 0.25, 0.50):
        key = f"relative_loss_eps_{eps:.2f}"
        out[key] = PolicyState(key, "relative_loss", "relative_loss", eps, safety_cap=20)
    for k in (3, 5):
        for delta in (0.001, 0.005, 0.010, 0.020, 0.050):
            key = f"boundary_top{k}_delta_{delta:.3f}"
            out[key] = PolicyState(
                key,
                f"boundary_top{k}",
                "boundary",
                delta,
                boundary_k=k,
                safety_cap=20,
            )
    out["no_pruning"] = PolicyState("no_pruning", "ceiling", "all", 0.0, safety_cap=None)
    return out


def select(candidates: list[PathT], state: PolicyState, edge_scores: dict[EdgeKey, float]) -> list[PathT]:
    ranked = sorted(candidates, key=lambda p: (-path_score(p, edge_scores), path_key(p)))
    if not ranked:
        return []
    if state.kind == "topk":
        return ranked[: int(state.value)]
    if state.kind == "all":
        return ranked
    if state.kind == "global":
        best = path_score(ranked[0], edge_scores)
        chosen = [p for p in ranked if path_score(p, edge_scores) >= best - state.value]
    elif state.kind == "relative_loss":
        best = path_score(ranked[0], edge_scores)
        best_loss = 1.0 - best
        threshold = 1.0 - (1.0 + state.value) * best_loss
        chosen = [p for p in ranked if path_score(p, edge_scores) >= threshold]
    elif state.kind == "boundary":
        k = int(state.boundary_k or 1)
        if len(ranked) <= k:
            chosen = ranked
        else:
            cutoff = path_score(ranked[k - 1], edge_scores)
            chosen = [p for p in ranked if path_score(p, edge_scores) >= cutoff - state.value]
    else:
        raise ValueError(f"unknown policy kind: {state.kind}")
    if state.safety_cap is not None:
        chosen = chosen[: state.safety_cap]
    return chosen


def safe_f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def budget_match(summary: dict[str, dict], anchor: str, family: str) -> dict:
    target_width = summary[anchor]["avg_active_width"]
    candidates = [
        (name, row)
        for name, row in summary.items()
        if row["family"] == family
    ]
    if not candidates:
        return {}
    name, row = min(
        candidates,
        key=lambda item: (
            abs(item[1]["avg_active_width"] - target_width),
            abs(item[1]["avg_expanded_candidates"] - summary[anchor]["avg_expanded_candidates"]),
            item[0],
        ),
    )
    width_gap = row["avg_active_width"] - target_width
    width_gap_pct = 100.0 * width_gap / target_width if target_width else 0.0
    return {
        "anchor": anchor,
        "matched_policy": name,
        "anchor_avg_width": target_width,
        "matched_avg_width": row["avg_active_width"],
        "width_gap": width_gap,
        "width_gap_pct": width_gap_pct,
        "anchor_avg_expanded": summary[anchor]["avg_expanded_candidates"],
        "matched_avg_expanded": row["avg_expanded_candidates"],
        "search_success_gain_pp": 100.0 * (row["search_success_rate"] - summary[anchor]["search_success_rate"]),
        "pruning_regret_delta_pp": 100.0 * (row["query_pruning_regret_rate"] - summary[anchor]["query_pruning_regret_rate"]),
        "viability_precision_delta_pp": 100.0 * (
            row["retained_viability_precision_micro"] - summary[anchor]["retained_viability_precision_micro"]
        ),
        "viability_recall_delta_pp": 100.0 * (
            row["viable_candidate_recall_micro"] - summary[anchor]["viable_candidate_recall_micro"]
        ),
        "validity_f1_delta_pp": 100.0 * (
            row["retained_viability_f1_micro"] - summary[anchor]["retained_viability_f1_micro"]
        ),
        "exploratory_warning": "Parameter is selected post-hoc by nearest average width on this evaluation set. Final paper must tune on development data and freeze before test evaluation.",
    }


def pareto_front(summary: dict[str, dict]) -> list[dict]:
    rows = []
    for name, x in summary.items():
        if name == "no_pruning":
            continue
        rows.append((name, x["avg_expanded_candidates"], x["search_success_rate"]))
    front = []
    for name, cost, success in rows:
        dominated = any(
            other_cost <= cost
            and other_success >= success
            and (other_cost < cost or other_success > success)
            for other_name, other_cost, other_success in rows
            if other_name != name
        )
        if not dominated:
            front.append({"policy": name, "avg_expanded_candidates": cost, "search_success_rate": success})
    return sorted(front, key=lambda x: (x["avg_expanded_candidates"], -x["search_success_rate"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="data/kg_benchmarks/WN18RR")
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--min-hops", type=int, default=2)
    ap.add_argument("--max-hops", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--device", default=None)
    ap.add_argument("--output", default="results/wn18rr_iterative_pruning_budgeted.json")
    args = ap.parse_args()

    root = Path(args.dataset_dir)
    rows = load_examples(Path(args.benchmark))
    if args.limit > 0:
        rows = rows[: args.limit]
    train = read_triples(root / "train.tsv")
    adjacency = build_adjacency(train)
    mappings = load_text_mappings(root / "entity2text.txt", root / "relation2text.txt")
    scorer = DebertaWorldScorer(device=args.device)

    template = policy_templates()
    totals = {
        name: {
            "family": state.family,
            "successes": 0,
            "regret_queries": 0,
            "regret_events": 0,
            "expanded": 0,
            "selected": 0,
            "depth_steps": 0,
            "viable_candidates": 0,
            "viable_selected": 0,
            "success_depth_sum": 0,
            "success_depth_n": 0,
            "by_hop": defaultdict(lambda: {"n": 0, "successes": 0}),
            "pre": defaultdict(int),
            "post": defaultdict(int),
        }
        for name, state in template.items()
    }
    records = []
    total_unique_edges_scored = 0

    for idx, row in enumerate(rows):
        start, goal = row["head"], row["tail"]
        ref_hop = int(row["hop_count"])
        query = candidate_relation_text(start, row["gold_relation"], goal, mappings)
        states = policy_templates()
        for state in states.values():
            state.active = [tuple()]
        edge_scores: dict[EdgeKey, float] = {}
        depth_detail: dict[str, dict] = {}

        for depth in range(1, args.max_hops + 1):
            candidate_sets: dict[str, list[PathT]] = {}
            union: dict[tuple[EdgeKey, ...], PathT] = {}
            for name, state in states.items():
                if state.success or not state.active:
                    continue
                cands = expand(state.active, start, adjacency)
                if depth < args.min_hops:
                    cands = [p for p in cands if p[-1].tail != goal]
                candidate_sets[name] = cands
                for p in cands:
                    union[path_key(p)] = p
            if not candidate_sets:
                break

            unique_paths = [union[k] for k in sorted(union)]
            total_unique_edges_scored += score_new_edges(
                scorer, unique_paths, query, mappings, edge_scores, max(1, args.batch_size)
            )

            for name, cands in candidate_sets.items():
                state = states[name]
                state.expanded += len(cands)
                state.depth_steps += 1
                remaining = args.max_hops - depth
                viable_cands = [p for p in cands if can_reach(p, start, goal, remaining, adjacency)]
                state.viable_candidates += len(viable_cands)
                pre_viable = bool(viable_cands)
                if pre_viable:
                    state.pre_viable_by_depth[depth] += 1

                selected = select(cands, state, edge_scores) if cands else []
                state.selected += len(selected)
                viable_selected = [p for p in selected if can_reach(p, start, goal, remaining, adjacency)]
                state.viable_selected += len(viable_selected)
                post_viable = bool(viable_selected)
                if post_viable:
                    state.post_viable_by_depth[depth] += 1
                if pre_viable and not post_viable:
                    state.regret_events += 1
                    state.had_regret = True

                reached = [p for p in selected if p[-1].tail == goal and depth >= args.min_hops]
                if reached:
                    state.success = True
                    state.success_depth = depth
                    state.active = []
                else:
                    state.active = selected

                depth_detail.setdefault(str(depth), {})[name] = {
                    "candidate_count": len(cands),
                    "selected_count": len(selected),
                    "viable_candidate_count": len(viable_cands),
                    "viable_selected_count": len(viable_selected),
                    "pre_viable": pre_viable,
                    "post_viable": post_viable,
                    "reached_target": bool(reached),
                    "best_path_score": max((path_score(p, edge_scores) for p in cands), default=0.0),
                }

        rec = {
            "example_id": row["example_id"],
            "head": start,
            "relation": row["gold_relation"],
            "tail": goal,
            "reference_hop": ref_hop,
            "unique_edges_scored": len(edge_scores),
            "policies": {},
            "depths": depth_detail,
        }
        for name, state in states.items():
            t = totals[name]
            t["by_hop"][ref_hop]["n"] += 1
            if state.success:
                t["successes"] += 1
                t["by_hop"][ref_hop]["successes"] += 1
                t["success_depth_sum"] += int(state.success_depth)
                t["success_depth_n"] += 1
            if state.had_regret:
                t["regret_queries"] += 1
            t["regret_events"] += state.regret_events
            t["expanded"] += state.expanded
            t["selected"] += state.selected
            t["depth_steps"] += state.depth_steps
            t["viable_candidates"] += state.viable_candidates
            t["viable_selected"] += state.viable_selected
            for d, v in state.pre_viable_by_depth.items():
                t["pre"][d] += v
            for d, v in state.post_viable_by_depth.items():
                t["post"][d] += v
            rec["policies"][name] = {
                "success": state.success,
                "success_depth": state.success_depth,
                "expanded_candidates": state.expanded,
                "avg_active_width": state.selected / state.depth_steps if state.depth_steps else 0.0,
                "pruning_regret_events": state.regret_events,
                "viable_candidates": state.viable_candidates,
                "viable_selected": state.viable_selected,
            }
        records.append(rec)
        print(f"completed {idx+1}/{len(rows)}; unique edges scored={len(edge_scores)}")

    n = len(rows)
    summary: dict[str, dict] = {}
    for name, t in totals.items():
        by_hop = {
            str(h): {"n": b["n"], "success_rate": b["successes"] / b["n"] if b["n"] else 0.0}
            for h, b in sorted(t["by_hop"].items())
        }
        depth_survival = {}
        for d in sorted(set(t["pre"]) | set(t["post"])):
            pre, post = t["pre"].get(d, 0), t["post"].get(d, 0)
            depth_survival[str(d)] = {
                "pre_viable_cases": pre,
                "post_viable_cases": post,
                "viable_prefix_survival": post / pre if pre else 0.0,
            }
        precision = t["viable_selected"] / t["selected"] if t["selected"] else 0.0
        recall = t["viable_selected"] / t["viable_candidates"] if t["viable_candidates"] else 0.0
        summary[name] = {
            "family": t["family"],
            "search_success_rate": t["successes"] / n if n else 0.0,
            "query_pruning_regret_rate": t["regret_queries"] / n if n else 0.0,
            "pruning_regret_events": t["regret_events"],
            "avg_expanded_candidates": t["expanded"] / n if n else 0.0,
            "avg_active_width": t["selected"] / t["depth_steps"] if t["depth_steps"] else 0.0,
            "retained_viability_precision_micro": precision,
            "viable_candidate_recall_micro": recall,
            "retained_viability_f1_micro": safe_f1(precision, recall),
            "viable_selected_paths": t["viable_selected"],
            "selected_paths": t["selected"],
            "available_viable_candidate_paths": t["viable_candidates"],
            "avg_success_depth": t["success_depth_sum"] / t["success_depth_n"] if t["success_depth_n"] else None,
            "viable_prefix_survival_by_depth": depth_survival,
            "by_reference_hop": by_hop,
        }

    matched = {
        "top3": {
            "global_rashomon": budget_match(summary, "top3_tog_style", "global_rashomon"),
            "relative_loss": budget_match(summary, "top3_tog_style", "relative_loss"),
            "boundary_aware": budget_match(summary, "top3_tog_style", "boundary_top3"),
        },
        "top5": {
            "global_rashomon": budget_match(summary, "top5", "global_rashomon"),
            "relative_loss": budget_match(summary, "top5", "relative_loss"),
            "boundary_aware": budget_match(summary, "top5", "boundary_top5"),
        },
    }

    output = {
        "protocol": {
            "dataset": root.name,
            "n": n,
            "task": "iterative 2-4 hop evidence-path search for held-out query claim (h,r,t)",
            "scorer": "DeBERTa single-edge support; path score = mean edge support",
            "policies": "fixed Top-K, global best-minus-epsilon, relative-loss Rashomon, pruning-boundary-aware delayed pruning",
            "budget_matching": "Top-3 and Top-5 are cost anchors. Adaptive hyperparameters are swept and the nearest average-active-width setting is reported for each family.",
            "validity": "A retained partial path is viable iff it can still reach the target entity within the remaining hop budget in the train graph.",
            "direct_target_edge": "held-out direct test target is not supplied to search; evidence uses train graph only",
            "scope_warning": "This WN18RR experiment evaluates search/pruning mechanics, not final KGQA answer accuracy and not a full ToG reproduction.",
        },
        "policies": summary,
        "budget_matched": matched,
        "pareto_success_vs_expansion": pareto_front(summary),
        "diagnostics": {"total_unique_edge_nli_calls": total_unique_edges_scored},
        "records": records,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"budget_matched": matched, "pareto": output["pareto_success_vs_expansion"]}, indent=2))
    print(out)


if __name__ == "__main__":
    main()
