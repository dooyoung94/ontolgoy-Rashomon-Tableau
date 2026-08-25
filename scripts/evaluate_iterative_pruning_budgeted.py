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
    family: str
    kind: str
    value: float
    boundary_k: int | None = None
    max_width: int = 10
    active: list[PathT] = field(default_factory=list)
    success: bool = False
    success_depth: int | None = None
    expanded: int = 0
    selected: int = 0
    steps: int = 0
    regret_events: int = 0
    had_regret: bool = False
    viable_candidates: int = 0
    viable_selected: int = 0
    pre_by_depth: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    post_by_depth: dict[int, int] = field(default_factory=lambda: defaultdict(int))


def load_examples(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def ekey(e: KGTriple) -> EdgeKey:
    return (e.head, e.relation, e.tail)


def pkey(p: PathT) -> tuple[EdgeKey, ...]:
    return tuple(ekey(e) for e in p)


def adjacency(train: list[KGTriple]) -> dict[str, list[KGTriple]]:
    out: dict[str, list[KGTriple]] = defaultdict(list)
    for t in train:
        out[t.head].append(t)
    for h in out:
        out[h].sort(key=lambda e: (e.relation, e.tail))
    return out


def nodes(p: PathT, start: str) -> set[str]:
    return {start, *(e.tail for e in p)}


def expand(active: list[PathT], start: str, adj: dict[str, list[KGTriple]]) -> list[PathT]:
    uniq: dict[tuple[EdgeKey, ...], PathT] = {}
    for p in active:
        cur = start if not p else p[-1].tail
        seen = nodes(p, start)
        for e in adj.get(cur, []):
            if e.tail in seen:
                continue
            np = (*p, e)
            uniq[pkey(np)] = np
    return [uniq[k] for k in sorted(uniq)]


def can_reach(p: PathT, start: str, goal: str, remaining: int, adj: dict[str, list[KGTriple]]) -> bool:
    cur = start if not p else p[-1].tail
    if cur == goal:
        return True
    if remaining <= 0:
        return False
    q = deque([(cur, 0, nodes(p, start))])
    while q:
        n, used, seen = q.popleft()
        if used >= remaining:
            continue
        for e in adj.get(n, []):
            if e.tail in seen:
                continue
            if e.tail == goal:
                return True
            q.append((e.tail, used + 1, seen | {e.tail}))
    return False


def score_edges(scorer, paths: list[PathT], query: str, mappings, cache: dict[EdgeKey, float], batch: int) -> int:
    missing: dict[EdgeKey, KGTriple] = {}
    for p in paths:
        if p and ekey(p[-1]) not in cache:
            missing[ekey(p[-1])] = p[-1]
    if not missing:
        return 0
    edges = [missing[k] for k in sorted(missing)]
    scores = scorer.score_many(
        [query] * len(edges),
        [path_evidence_text([e], mappings) for e in edges],
        batch_size=batch,
    )
    for e, s in zip(edges, scores):
        cache[ekey(e)] = s.support
    return len(edges)


def pscore(p: PathT, scores: dict[EdgeKey, float]) -> float:
    return sum(scores[ekey(e)] for e in p) / len(p) if p else 0.0


def policies() -> dict[str, PolicyState]:
    out = {
        "top3_tog_style": PolicyState("top3_tog_style", "fixed_topk", "topk", 3, max_width=3),
        "top5": PolicyState("top5", "fixed_topk", "topk", 5, max_width=5),
    }
    for eps in (0.01, 0.03, 0.05, 0.10):
        n = f"global_eps_{eps:.2f}"
        out[n] = PolicyState(n, "global", "global", eps)
    for eps in (0.10, 0.25, 0.50):
        n = f"relative_loss_{eps:.2f}"
        out[n] = PolicyState(n, "relative_loss", "relative", eps)
    for k in (3, 5):
        for d in (0.001, 0.005, 0.010, 0.020, 0.050):
            n = f"boundary_top{k}_{d:.3f}"
            out[n] = PolicyState(n, f"boundary_top{k}", "boundary", d, boundary_k=k)
    return out


def select(cands: list[PathT], st: PolicyState, scores: dict[EdgeKey, float]) -> list[PathT]:
    ranked = sorted(cands, key=lambda p: (-pscore(p, scores), pkey(p)))
    if not ranked:
        return []
    if st.kind == "topk":
        return ranked[: int(st.value)]
    if st.kind == "global":
        threshold = pscore(ranked[0], scores) - st.value
    elif st.kind == "relative":
        best = pscore(ranked[0], scores)
        threshold = 1.0 - (1.0 + st.value) * (1.0 - best)
    elif st.kind == "boundary":
        k = int(st.boundary_k or 1)
        if len(ranked) <= k:
            return ranked
        threshold = pscore(ranked[k - 1], scores) - st.value
    else:
        raise ValueError(st.kind)
    return [p for p in ranked if pscore(p, scores) >= threshold][: st.max_width]


def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0


def match_budget(summary: dict[str, dict], anchor: str, family: str) -> dict:
    a = summary[anchor]
    pool = [(n, x) for n, x in summary.items() if x["family"] == family]
    n, x = min(
        pool,
        key=lambda z: (
            abs(z[1]["avg_active_width"] - a["avg_active_width"]),
            abs(z[1]["avg_expanded_candidates"] - a["avg_expanded_candidates"]),
            z[0],
        ),
    )
    return {
        "anchor": anchor,
        "matched_policy": n,
        "anchor_width": a["avg_active_width"],
        "matched_width": x["avg_active_width"],
        "width_gap": x["avg_active_width"] - a["avg_active_width"],
        "success_gain_pp": 100 * (x["search_success_rate"] - a["search_success_rate"]),
        "regret_delta_pp": 100 * (x["query_pruning_regret_rate"] - a["query_pruning_regret_rate"]),
        "viability_precision_delta_pp": 100 * (x["viability_precision"] - a["viability_precision"]),
        "viability_recall_delta_pp": 100 * (x["viability_recall"] - a["viability_recall"]),
        "viability_f1_delta_pp": 100 * (x["viability_f1"] - a["viability_f1"]),
        "expanded_delta": x["avg_expanded_candidates"] - a["avg_expanded_candidates"],
        "warning": "Exploratory post-hoc width matching; final test requires dev-set tuning and frozen hyperparameters.",
    }


def pareto(summary: dict[str, dict]) -> list[dict]:
    pts = [(n, x["avg_expanded_candidates"], x["search_success_rate"]) for n, x in summary.items()]
    front = []
    for n, c, s in pts:
        dominated = any(c2 <= c and s2 >= s and (c2 < c or s2 > s) for n2, c2, s2 in pts if n2 != n)
        if not dominated:
            front.append({"policy": n, "avg_expanded_candidates": c, "search_success_rate": s})
    return sorted(front, key=lambda x: (x["avg_expanded_candidates"], -x["search_success_rate"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="data/kg_benchmarks/WN18RR")
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--min-hops", type=int, default=2)
    ap.add_argument("--max-hops", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--device", default=None)
    ap.add_argument("--output", default="results/wn18rr_iterative_pruning_budgeted.json")
    args = ap.parse_args()

    root = Path(args.dataset_dir)
    rows = load_examples(Path(args.benchmark))[: args.limit] if args.limit > 0 else load_examples(Path(args.benchmark))
    train = read_triples(root / "train.tsv")
    adj = adjacency(train)
    mappings = load_text_mappings(root / "entity2text.txt", root / "relation2text.txt")
    scorer = DebertaWorldScorer(device=args.device)
    template = policies()
    totals = {
        n: {"family": st.family, "success": 0, "regret_q": 0, "regret_e": 0, "expanded": 0,
            "selected": 0, "steps": 0, "v_cand": 0, "v_sel": 0,
            "pre": defaultdict(int), "post": defaultdict(int), "by_hop": defaultdict(lambda: [0, 0])}
        for n, st in template.items()
    }
    records = []
    nli_calls = 0

    for idx, row in enumerate(rows):
        start, goal = row["head"], row["tail"]
        ref_hop = int(row["hop_count"])
        query = candidate_relation_text(start, row["gold_relation"], goal, mappings)
        states = policies()
        for st in states.values():
            st.active = [tuple()]
        scores: dict[EdgeKey, float] = {}

        for depth in range(1, args.max_hops + 1):
            csets: dict[str, list[PathT]] = {}
            union: dict[tuple[EdgeKey, ...], PathT] = {}
            for name, st in states.items():
                if st.success or not st.active:
                    continue
                cs = expand(st.active, start, adj)
                if depth < args.min_hops:
                    cs = [p for p in cs if p[-1].tail != goal]
                csets[name] = cs
                for p in cs:
                    union[pkey(p)] = p
            if not csets:
                break
            nli_calls += score_edges(scorer, [union[k] for k in sorted(union)], query, mappings, scores, args.batch_size)

            for name, cs in csets.items():
                st = states[name]
                st.expanded += len(cs)
                st.steps += 1
                rem = args.max_hops - depth
                viable_cs = [p for p in cs if can_reach(p, start, goal, rem, adj)]
                st.viable_candidates += len(viable_cs)
                if viable_cs:
                    st.pre_by_depth[depth] += 1
                chosen = select(cs, st, scores)
                st.selected += len(chosen)
                viable_sel = [p for p in chosen if can_reach(p, start, goal, rem, adj)]
                st.viable_selected += len(viable_sel)
                if viable_sel:
                    st.post_by_depth[depth] += 1
                if viable_cs and not viable_sel:
                    st.regret_events += 1
                    st.had_regret = True
                reached = any(p[-1].tail == goal and depth >= args.min_hops for p in chosen)
                if reached:
                    st.success, st.success_depth, st.active = True, depth, []
                else:
                    st.active = chosen

        rec = {"example_id": row["example_id"], "reference_hop": ref_hop, "policies": {}}
        for name, st in states.items():
            t = totals[name]
            t["by_hop"][ref_hop][0] += 1
            if st.success:
                t["success"] += 1
                t["by_hop"][ref_hop][1] += 1
            if st.had_regret:
                t["regret_q"] += 1
            t["regret_e"] += st.regret_events
            t["expanded"] += st.expanded
            t["selected"] += st.selected
            t["steps"] += st.steps
            t["v_cand"] += st.viable_candidates
            t["v_sel"] += st.viable_selected
            for d, v in st.pre_by_depth.items(): t["pre"][d] += v
            for d, v in st.post_by_depth.items(): t["post"][d] += v
            rec["policies"][name] = {"success": st.success, "regret_events": st.regret_events}
        records.append(rec)
        print(f"completed {idx+1}/{len(rows)} edges_scored={len(scores)}")

    n = len(rows)
    summary = {}
    for name, t in totals.items():
        precision = t["v_sel"] / t["selected"] if t["selected"] else 0.0
        recall = t["v_sel"] / t["v_cand"] if t["v_cand"] else 0.0
        summary[name] = {
            "family": t["family"],
            "search_success_rate": t["success"] / n if n else 0.0,
            "query_pruning_regret_rate": t["regret_q"] / n if n else 0.0,
            "pruning_regret_events": t["regret_e"],
            "avg_active_width": t["selected"] / t["steps"] if t["steps"] else 0.0,
            "avg_expanded_candidates": t["expanded"] / n if n else 0.0,
            "viability_precision": precision,
            "viability_recall": recall,
            "viability_f1": f1(precision, recall),
            "by_reference_hop": {str(h): {"n": v[0], "success_rate": v[1]/v[0] if v[0] else 0.0} for h, v in sorted(t["by_hop"].items())},
            "viable_prefix_survival_by_depth": {
                str(d): {"pre_viable_cases": t["pre"].get(d,0), "post_viable_cases": t["post"].get(d,0),
                         "survival": t["post"].get(d,0)/t["pre"].get(d,0) if t["pre"].get(d,0) else 0.0}
                for d in sorted(set(t["pre"]) | set(t["post"]))
            },
        }

    matched = {
        "top3": {
            "global": match_budget(summary, "top3_tog_style", "global"),
            "relative_loss": match_budget(summary, "top3_tog_style", "relative_loss"),
            "boundary": match_budget(summary, "top3_tog_style", "boundary_top3"),
        },
        "top5": {
            "global": match_budget(summary, "top5", "global"),
            "relative_loss": match_budget(summary, "top5", "relative_loss"),
            "boundary": match_budget(summary, "top5", "boundary_top5"),
        },
    }
    result = {
        "protocol": {
            "dataset": root.name,
            "n": n,
            "task": "iterative 2-4 hop evidence-path search",
            "scorer": "DeBERTa edge support; path score=mean edge support",
            "adaptive_safety_cap": 10,
            "budget_matching": "Top-3/Top-5 anchors; nearest average active width, expansion proximity tie-break",
            "validity": "retained partial path is viable iff target remains reachable within remaining hop budget",
            "scope": "pruning-policy stress test, not a full ToG reproduction or KGQA answer benchmark",
        },
        "policies": summary,
        "budget_matched": matched,
        "pareto_success_vs_expansion": pareto(summary),
        "diagnostics": {"unique_edge_nli_calls": nli_calls},
        "records": records,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"budget_matched": matched, "pareto": result["pareto_success_vs_expansion"]}, indent=2))
    print(out)


if __name__ == "__main__":
    main()
