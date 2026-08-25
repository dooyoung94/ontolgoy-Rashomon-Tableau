from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from rashomon_tableau.deberta_world_scorer import DebertaWorldScorer
from rashomon_tableau.kg_multihop_benchmark import (
    KGTriple,
    candidate_relation_text,
    load_text_mappings,
    path_evidence_text,
    read_triples,
)


PathT = tuple[KGTriple, ...]


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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def path_key(path: PathT) -> tuple:
    return tuple((edge.head, edge.relation, edge.tail) for edge in path)


def path_nodes(path: PathT, start: str) -> set[str]:
    nodes = {start}
    for edge in path:
        nodes.add(edge.tail)
    return nodes


def build_adjacency(train: Iterable[KGTriple]) -> dict[str, list[KGTriple]]:
    adjacency: dict[str, list[KGTriple]] = defaultdict(list)
    for triple in train:
        adjacency[triple.head].append(triple)
    for node in adjacency:
        adjacency[node].sort(key=lambda x: (x.relation, x.tail, x.head))
    return adjacency


def expand_paths(
    active: list[PathT],
    *,
    start: str,
    goal: str,
    depth: int,
    min_hops: int,
    adjacency: dict[str, list[KGTriple]],
) -> list[PathT]:
    out: dict[tuple, PathT] = {}
    for path in active:
        node = start if not path else path[-1].tail
        visited = path_nodes(path, start)
        for edge in adjacency.get(node, []):
            if edge.tail in visited:
                continue
            new_path = (*path, edge)
            # Direct one-hop arrival is intentionally excluded: the experiment is 2-4 hop reasoning.
            if edge.tail == goal and depth < min_hops:
                continue
            out[path_key(new_path)] = new_path
    return [out[key] for key in sorted(out)]


def can_reach_goal(
    path: PathT,
    *,
    start: str,
    goal: str,
    remaining_hops: int,
    adjacency: dict[str, list[KGTriple]],
) -> bool:
    node = start if not path else path[-1].tail
    if node == goal:
        return True
    if remaining_hops <= 0:
        return False
    blocked = path_nodes(path, start)
    queue = deque([(node, 0, blocked)])
    while queue:
        current, used, visited = queue.popleft()
        if used >= remaining_hops:
            continue
        for edge in adjacency.get(current, []):
            nxt = edge.tail
            if nxt in visited:
                continue
            if nxt == goal:
                return True
            queue.append((nxt, used + 1, visited | {nxt}))
    return False


def select_paths(
    candidates: list[PathT],
    scores: dict[tuple, float],
    state: PolicyState,
) -> list[PathT]:
    ranked = sorted(candidates, key=lambda p: (-scores[path_key(p)], path_key(p)))
    if not ranked:
        return []
    if state.kind == "topk":
        return ranked[: int(state.value)]
    if state.kind == "rashomon":
        best = scores[path_key(ranked[0])]
        threshold = best - state.value
        selected = [p for p in ranked if scores[path_key(p)] >= threshold]
        if state.max_width is not None:
            selected = selected[: state.max_width]
        return selected
    raise ValueError(f"unknown policy kind: {state.kind}")


def score_missing_paths(
    scorer: DebertaWorldScorer,
    paths: list[PathT],
    query_text: str,
    mappings,
    cache: dict[tuple, float],
    *,
    batch_size: int,
) -> int:
    missing = [p for p in paths if path_key(p) not in cache]
    if not missing:
        return 0
    queries = [query_text] * len(missing)
    evidence = [path_evidence_text(p, mappings) for p in missing]
    nli_scores = scorer.score_many(queries, evidence, batch_size=batch_size)
    for path, score in zip(missing, nli_scores):
        cache[path_key(path)] = score.support
    return len(missing)


def make_policy_states() -> dict[str, PolicyState]:
    return {
        "top1": PolicyState("top1", "topk", 1),
        "top3_tog_style": PolicyState("top3_tog_style", "topk", 3),
        "top5": PolicyState("top5", "topk", 5),
        "rashomon_eps_0.05": PolicyState("rashomon_eps_0.05", "rashomon", 0.05, max_width=20),
        "rashomon_eps_0.10": PolicyState("rashomon_eps_0.10", "rashomon", 0.10, max_width=20),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default="data/kg_benchmarks/WN18RR")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--min-hops", type=int, default=2)
    parser.add_argument("--max-hops", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--candidate-cap", type=int, default=0, help="0 disables pre-score truncation")
    parser.add_argument("--device", default=None)
    parser.add_argument("--output", default="results/wn18rr_iterative_pruning_search.json")
    args = parser.parse_args()

    root = Path(args.dataset_dir)
    rows = load_examples(Path(args.benchmark))
    if args.limit > 0:
        rows = rows[: args.limit]

    train = read_triples(root / "train.tsv")
    adjacency = build_adjacency(train)
    mappings = load_text_mappings(root / "entity2text.txt", root / "relation2text.txt")
    scorer = DebertaWorldScorer(device=args.device)

    aggregate: dict[str, dict] = {}
    for name in make_policy_states():
        aggregate[name] = {
            "successes": 0,
            "success_depth_sum": 0,
            "success_depth_n": 0,
            "expanded": 0,
            "selected": 0,
            "depth_steps": 0,
            "regret_queries": 0,
            "regret_events": 0,
            "pre_viable_by_depth": defaultdict(int),
            "post_viable_by_depth": defaultdict(int),
            "by_target_hop": defaultdict(lambda: {"n": 0, "successes": 0}),
        }

    records = []
    total_unique_scored = 0
    truncation_events = 0

    for row_index, row in enumerate(rows):
        start = row["head"]
        goal = row["tail"]
        target_hop = int(row["hop_count"])
        query_text = candidate_relation_text(start, row["gold_relation"], goal, mappings)
        states = make_policy_states()
        for state in states.values():
            state.active = [tuple()]

        score_cache: dict[tuple, float] = {}
        depth_record: dict[str, dict] = {}

        for depth in range(1, args.max_hops + 1):
            candidate_sets: dict[str, list[PathT]] = {}
            union: dict[tuple, PathT] = {}

            for name, state in states.items():
                if state.success or not state.active:
                    continue
                candidates = expand_paths(
                    state.active,
                    start=start,
                    goal=goal,
                    depth=depth,
                    min_hops=args.min_hops,
                    adjacency=adjacency,
                )
                if args.candidate_cap > 0 and len(candidates) > args.candidate_cap:
                    truncation_events += 1
                    candidates = candidates[: args.candidate_cap]
                candidate_sets[name] = candidates
                for path in candidates:
                    union[path_key(path)] = path

            if not candidate_sets:
                break

            unique_paths = [union[key] for key in sorted(union)]
            total_unique_scored += score_missing_paths(
                scorer,
                unique_paths,
                query_text,
                mappings,
                score_cache,
                batch_size=max(1, args.batch_size),
            )

            for name, candidates in candidate_sets.items():
                state = states[name]
                state.expanded += len(candidates)
                state.depth_steps += 1
                remaining = args.max_hops - depth
                pre_viable = any(
                    can_reach_goal(
                        p,
                        start=start,
                        goal=goal,
                        remaining_hops=remaining,
                        adjacency=adjacency,
                    )
                    for p in candidates
                )
                if pre_viable:
                    state.pre_viable_by_depth[depth] += 1

                selected = select_paths(candidates, score_cache, state)
                state.selected += len(selected)
                post_viable = any(
                    can_reach_goal(
                        p,
                        start=start,
                        goal=goal,
                        remaining_hops=remaining,
                        adjacency=adjacency,
                    )
                    for p in selected
                )
                if post_viable:
                    state.post_viable_by_depth[depth] += 1
                if pre_viable and not post_viable:
                    state.regret_events += 1
                    state.had_regret = True

                reached = [p for p in selected if p and p[-1].tail == goal and depth >= args.min_hops]
                if reached:
                    state.success = True
                    state.success_depth = depth
                    state.active = []
                else:
                    state.active = selected

                depth_record.setdefault(str(depth), {})[name] = {
                    "candidate_count": len(candidates),
                    "selected_count": len(selected),
                    "pre_viable": pre_viable,
                    "post_viable": post_viable,
                    "reached_target": bool(reached),
                    "best_score": max((score_cache[path_key(p)] for p in candidates), default=0.0),
                    "selected_scores": [score_cache[path_key(p)] for p in selected],
                }

        record = {
            "example_id": row["example_id"],
            "head": start,
            "relation": row["gold_relation"],
            "tail": goal,
            "known_reference_hop": target_hop,
            "policies": {},
            "depths": depth_record,
        }

        for name, state in states.items():
            agg = aggregate[name]
            agg["by_target_hop"][target_hop]["n"] += 1
            if state.success:
                agg["successes"] += 1
                agg["success_depth_sum"] += int(state.success_depth)
                agg["success_depth_n"] += 1
                agg["by_target_hop"][target_hop]["successes"] += 1
            if state.had_regret:
                agg["regret_queries"] += 1
            agg["regret_events"] += state.regret_events
            agg["expanded"] += state.expanded
            agg["selected"] += state.selected
            agg["depth_steps"] += state.depth_steps
            for depth, value in state.pre_viable_by_depth.items():
                agg["pre_viable_by_depth"][depth] += value
            for depth, value in state.post_viable_by_depth.items():
                agg["post_viable_by_depth"][depth] += value

            record["policies"][name] = {
                "success": state.success,
                "success_depth": state.success_depth,
                "expanded_candidates": state.expanded,
                "avg_active_width": state.selected / state.depth_steps if state.depth_steps else 0.0,
                "pruning_regret_events": state.regret_events,
            }

        records.append(record)
        print(f"completed query {row_index + 1}/{len(rows)}; unique NLI paths scored={len(score_cache)}")

    policies = {}
    n = len(rows)
    for name, agg in aggregate.items():
        depth_survival = {}
        all_depths = sorted(set(agg["pre_viable_by_depth"]) | set(agg["post_viable_by_depth"]))
        for depth in all_depths:
            pre = agg["pre_viable_by_depth"].get(depth, 0)
            post = agg["post_viable_by_depth"].get(depth, 0)
            depth_survival[str(depth)] = {
                "pre_viable_cases": pre,
                "post_viable_cases": post,
                "viable_prefix_survival": post / pre if pre else 0.0,
            }

        by_hop = {}
        for hop, bucket in sorted(agg["by_target_hop"].items()):
            by_hop[str(hop)] = {
                "n": bucket["n"],
                "success_rate": bucket["successes"] / bucket["n"] if bucket["n"] else 0.0,
            }

        policies[name] = {
            "search_success_rate": agg["successes"] / n if n else 0.0,
            "query_pruning_regret_rate": agg["regret_queries"] / n if n else 0.0,
            "pruning_regret_events": agg["regret_events"],
            "avg_expanded_candidates": agg["expanded"] / n if n else 0.0,
            "avg_active_width": agg["selected"] / agg["depth_steps"] if agg["depth_steps"] else 0.0,
            "avg_success_depth": (
                agg["success_depth_sum"] / agg["success_depth_n"] if agg["success_depth_n"] else None
            ),
            "viable_prefix_survival_by_depth": depth_survival,
            "by_reference_hop": by_hop,
        }

    def compare(a: str, b: str) -> dict:
        pa = policies[a]
        pb = policies[b]
        return {
            "success_gain_pp": 100.0 * (pa["search_success_rate"] - pb["search_success_rate"]),
            "regret_rate_delta_pp": 100.0 * (
                pa["query_pruning_regret_rate"] - pb["query_pruning_regret_rate"]
            ),
            "expanded_candidate_delta": pa["avg_expanded_candidates"] - pb["avg_expanded_candidates"],
            "avg_width_delta": pa["avg_active_width"] - pb["avg_active_width"],
        }

    summary = {
        "protocol": {
            "dataset": root.name,
            "n": n,
            "task": "held-out triple evidence-path search; direct target edge absent from evidence train graph",
            "query": "(h, r, t) natural-language claim",
            "scorer": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli support probability",
            "search": f"directed simple-path expansion, {args.min_hops}-{args.max_hops} hops",
            "selection": "same scorer, policy varies only at prune step",
            "candidate_cap": args.candidate_cap,
            "rashomon_max_width": 20,
            "note": "This is the first iterative search pilot aligned with ToG-style repeated search/prune. It is not a full ToG reproduction or QA benchmark.",
        },
        "policies": policies,
        "comparisons": {
            "rashomon_eps_0.05_vs_top3": compare("rashomon_eps_0.05", "top3_tog_style"),
            "rashomon_eps_0.10_vs_top5": compare("rashomon_eps_0.10", "top5"),
        },
        "diagnostics": {
            "total_unique_nli_paths_scored": total_unique_scored,
            "candidate_truncation_events": truncation_events,
        },
        "records": records,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"policies": policies, "comparisons": summary["comparisons"], "diagnostics": summary["diagnostics"]}, indent=2))
    print(output)


if __name__ == "__main__":
    main()
