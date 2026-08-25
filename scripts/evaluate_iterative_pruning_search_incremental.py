from __future__ import annotations

import argparse
import json
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
    kind: str
    value: float
    max_width: int | None = None
    active: list[PathT] = field(default_factory=list)
    success: bool = False
    success_depth: int | None = None
    expanded: int = 0
    selected: int = 0
    depth_steps: int = 0
    regret_events: int = 0
    had_regret: bool = False
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


def policies() -> dict[str, PolicyState]:
    return {
        "top1": PolicyState("top1", "topk", 1),
        "top3_tog_style": PolicyState("top3_tog_style", "topk", 3),
        "top5": PolicyState("top5", "topk", 5),
        "rashomon_eps_0.05": PolicyState("rashomon_eps_0.05", "rashomon", 0.05, 20),
        "rashomon_eps_0.10": PolicyState("rashomon_eps_0.10", "rashomon", 0.10, 20),
    }


def select(candidates: list[PathT], state: PolicyState, edge_scores: dict[EdgeKey, float]) -> list[PathT]:
    ranked = sorted(candidates, key=lambda p: (-path_score(p, edge_scores), path_key(p)))
    if state.kind == "topk":
        return ranked[: int(state.value)]
    best = path_score(ranked[0], edge_scores) if ranked else 0.0
    chosen = [p for p in ranked if path_score(p, edge_scores) >= best - state.value]
    if state.max_width is not None:
        chosen = chosen[: state.max_width]
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="data/kg_benchmarks/WN18RR")
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--min-hops", type=int, default=2)
    ap.add_argument("--max-hops", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--device", default=None)
    ap.add_argument("--output", default="results/wn18rr_iterative_pruning_incremental.json")
    args = ap.parse_args()

    root = Path(args.dataset_dir)
    rows = load_examples(Path(args.benchmark))
    if args.limit > 0:
        rows = rows[: args.limit]
    train = read_triples(root / "train.tsv")
    adjacency = build_adjacency(train)
    mappings = load_text_mappings(root / "entity2text.txt", root / "relation2text.txt")
    scorer = DebertaWorldScorer(device=args.device)

    totals = {
        name: {
            "successes": 0,
            "regret_queries": 0,
            "regret_events": 0,
            "expanded": 0,
            "selected": 0,
            "depth_steps": 0,
            "success_depth_sum": 0,
            "success_depth_n": 0,
            "by_hop": defaultdict(lambda: {"n": 0, "successes": 0}),
            "pre": defaultdict(int),
            "post": defaultdict(int),
        }
        for name in policies()
    }
    records = []
    total_unique_edges_scored = 0

    for idx, row in enumerate(rows):
        start, goal = row["head"], row["tail"]
        ref_hop = int(row["hop_count"])
        query = candidate_relation_text(start, row["gold_relation"], goal, mappings)
        states = policies()
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
                # A direct one-hop answer is outside the 2-4 hop benchmark.
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
                pre_viable = any(can_reach(p, start, goal, remaining, adjacency) for p in cands)
                if pre_viable:
                    state.pre_viable_by_depth[depth] += 1
                selected = select(cands, state, edge_scores) if cands else []
                state.selected += len(selected)
                post_viable = any(can_reach(p, start, goal, remaining, adjacency) for p in selected)
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
            }
        records.append(rec)
        print(f"completed {idx+1}/{len(rows)}; unique edges scored={len(edge_scores)}")

    n = len(rows)
    summary_policies = {}
    for name, t in totals.items():
        by_hop = {
            str(h): {
                "n": b["n"],
                "success_rate": b["successes"] / b["n"] if b["n"] else 0.0,
            }
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
        summary_policies[name] = {
            "search_success_rate": t["successes"] / n if n else 0.0,
            "query_pruning_regret_rate": t["regret_queries"] / n if n else 0.0,
            "pruning_regret_events": t["regret_events"],
            "avg_expanded_candidates": t["expanded"] / n if n else 0.0,
            "avg_active_width": t["selected"] / t["depth_steps"] if t["depth_steps"] else 0.0,
            "avg_success_depth": t["success_depth_sum"] / t["success_depth_n"] if t["success_depth_n"] else None,
            "viable_prefix_survival_by_depth": depth_survival,
            "by_reference_hop": by_hop,
        }

    def cmp(a: str, b: str) -> dict:
        pa, pb = summary_policies[a], summary_policies[b]
        return {
            "success_gain_pp": 100 * (pa["search_success_rate"] - pb["search_success_rate"]),
            "regret_rate_delta_pp": 100 * (pa["query_pruning_regret_rate"] - pb["query_pruning_regret_rate"]),
            "expanded_candidate_delta": pa["avg_expanded_candidates"] - pb["avg_expanded_candidates"],
            "avg_width_delta": pa["avg_active_width"] - pb["avg_active_width"],
        }

    output = {
        "protocol": {
            "dataset": root.name,
            "n": n,
            "task": "iterative 2-4 hop evidence-path search for held-out query claim (h,r,t)",
            "scorer": "DeBERTa single-edge support; path score = mean edge support",
            "selection": "same scorer; fixed Top-K vs Rashomon best-minus-epsilon",
            "direct_target_edge": "not supplied from held-out test target; search evidence uses train graph",
            "note": "Incremental edge scoring approximates ToG-style repeated relevance evaluation while avoiding repeated full-path NLI inference. This is a pruning-policy experiment, not a full ToG reproduction.",
        },
        "policies": summary_policies,
        "comparisons": {
            "rashomon_eps_0.05_vs_top3": cmp("rashomon_eps_0.05", "top3_tog_style"),
            "rashomon_eps_0.10_vs_top5": cmp("rashomon_eps_0.10", "top5"),
        },
        "diagnostics": {"total_unique_edge_nli_calls": total_unique_edges_scored},
        "records": records,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"policies": summary_policies, "comparisons": output["comparisons"], "diagnostics": output["diagnostics"]}, indent=2))
    print(out)


if __name__ == "__main__":
    main()
