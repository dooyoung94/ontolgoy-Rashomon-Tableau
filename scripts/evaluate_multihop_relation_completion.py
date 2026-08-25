from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from rashomon_tableau.deberta_world_scorer import DebertaWorldScorer
from rashomon_tableau.kg_multihop_benchmark import (
    KGTriple,
    candidate_relation_text,
    load_text_mappings,
    path_as_literals,
    path_evidence_text,
    read_triples,
    relation_vocabulary,
)
from rashomon_tableau.multihop_completion import RelationCandidate, complete_missing_relation
from rashomon_tableau.ontology import Ontology


def load_examples(path: Path) -> list[dict]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            out.append(json.loads(raw))
    return out


def as_path(row: dict) -> list[KGTriple]:
    return [KGTriple(x["head"], x["relation"], x["tail"]) for x in row["path"]]


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def ontology_predicates(ontology: Ontology) -> set[str]:
    predicates = set(ontology.symmetric)
    predicates.update(ontology.inverse)
    predicates.update(ontology.inverse.values())
    predicates.update(ontology.hierarchy)
    for parents in ontology.hierarchy.values():
        predicates.update(parents)
    for left, right in ontology.incompatible:
        predicates.add(left)
        predicates.add(right)
    predicates.update(ontology.exclusive)
    predicates.update(ontology.transitive)
    predicates.update(ontology.irreflexive)
    predicates.update(ontology.antisymmetric)
    for rule in ontology.compositions:
        predicates.update((rule.left, rule.right, rule.result))
    return predicates


def build_node_index(train: list[KGTriple]) -> dict[str, list[KGTriple]]:
    index: dict[str, list[KGTriple]] = defaultdict(list)
    for triple in train:
        index[triple.head].append(triple)
        if triple.tail != triple.head:
            index[triple.tail].append(triple)
    return index


def local_tableau_facts(
    path: list[KGTriple],
    row: dict,
    node_index: dict[str, list[KGTriple]],
    allowed_predicates: set[str],
    *,
    cap: int,
) -> tuple:
    """Build a label-blind ontology-relevant local subgraph for Tableau.

    The selected evidence path is always present. We then add train-graph facts touching
    the query endpoints or any intermediate path node, restricted to predicates that the
    ontology can reason about. This exposes reverse edges, short cycles, composition and
    other hard clashes that are invisible when Tableau sees the selected path alone.
    """
    focus_nodes = {row["head"], row["tail"]}
    for triple in path:
        focus_nodes.add(triple.head)
        focus_nodes.add(triple.tail)

    selected: dict[tuple[str, str, str], KGTriple] = {}
    for triple in path:
        selected[(triple.head, triple.relation, triple.tail)] = triple

    local_candidates: dict[tuple[str, str, str], KGTriple] = {}
    for node in sorted(focus_nodes):
        for triple in node_index.get(node, []):
            if triple.relation not in allowed_predicates:
                continue
            key = (triple.head, triple.relation, triple.tail)
            if key not in selected:
                local_candidates[key] = triple

    # Deterministic cap. Path evidence is never dropped.
    for key in sorted(local_candidates)[: max(0, cap - len(selected))]:
        selected[key] = local_candidates[key]

    triples = [selected[key] for key in sorted(selected)]
    return path_as_literals(triples, source="kg_local_tableau")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default="data/kg_benchmarks/WN18RR")
    parser.add_argument("--benchmark", default="data/kg_benchmarks/WN18RR/multihop_test.jsonl")
    parser.add_argument("--ontology", default="config/wn18rr_ontology_rules.yaml")
    parser.add_argument("--epsilon", type=float, default=0.05)
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--local-neighborhood-cap", type=int, default=256)
    parser.add_argument("--device", default=None)
    parser.add_argument("--output", default="results/wn18rr_multihop_completion_pilot.json")
    args = parser.parse_args()

    root = Path(args.dataset_dir)
    benchmark_rows = load_examples(Path(args.benchmark))
    if args.limit > 0:
        benchmark_rows = benchmark_rows[: args.limit]

    train = read_triples(root / "train.tsv")
    dev = read_triples(root / "dev.tsv")
    test = read_triples(root / "test.tsv")
    relations = relation_vocabulary(train, dev, test)
    mappings = load_text_mappings(root / "entity2text.txt", root / "relation2text.txt")
    ontology = Ontology.from_yaml(args.ontology)
    scorer = DebertaWorldScorer(device=args.device)
    node_index = build_node_index(train)
    allowed_predicates = ontology_predicates(ontology)

    prepared = []
    all_queries: list[str] = []
    all_evidence_groups: list[list[str]] = []
    for row in benchmark_rows:
        path = as_path(row)
        evidence = path_evidence_text(path, mappings)
        start = len(all_queries)
        for relation in relations:
            all_queries.append(candidate_relation_text(row["head"], relation, row["tail"], mappings))
            all_evidence_groups.append(evidence)
        prepared.append((row, path, start, len(all_queries)))

    print(
        f"batch scoring {len(benchmark_rows)} examples x {len(relations)} relations "
        f"= {len(all_queries)} NLI pairs"
    )
    all_scores = scorer.score_many(
        all_queries,
        all_evidence_groups,
        batch_size=max(1, args.batch_size),
    )

    totals = defaultdict(float)
    by_hop: dict[int, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    records = []

    for index, (row, path, start, end) in enumerate(prepared):
        nli_scores = all_scores[start:end]
        path_literals = path_as_literals(path)
        candidates = [
            RelationCandidate(
                relation=relation,
                score=score.support,
                path=path_literals,
                support=score.support,
                contradiction=score.contradiction,
                unresolved=score.unresolved,
                origin="deberta-nli",
            )
            for relation, score in zip(relations, nli_scores)
        ]
        ranked = sorted(candidates, key=lambda c: (-c.score, c.relation))
        top1 = ranked[0].relation if ranked else None
        rashomon_threshold = max((c.score for c in candidates), default=0.0) - args.epsilon
        rashomon_relations = {
            c.relation
            for c in candidates
            if c.score >= max(args.min_score, rashomon_threshold)
        }

        path_completion = complete_missing_relation(
            path_literals,
            row["head"],
            row["tail"],
            candidates,
            ontology,
            epsilon=args.epsilon,
            min_score=args.min_score,
        )
        local_facts = local_tableau_facts(
            path,
            row,
            node_index,
            allowed_predicates,
            cap=args.local_neighborhood_cap,
        )
        local_completion = complete_missing_relation(
            local_facts,
            row["head"],
            row["tail"],
            candidates,
            ontology,
            epsilon=args.epsilon,
            min_score=args.min_score,
        )

        path_valid_relations = {world.relation for world in path_completion.valid_worlds}
        local_valid_relations = {world.relation for world in local_completion.valid_worlds}
        gold = row["gold_relation"]
        hop = int(row["hop_count"])

        local_rejected = list(local_completion.rejected_worlds)
        local_wrong_rejected = sum(world.relation != gold for world in local_rejected)
        local_gold_false_rejected = float(gold in rashomon_relations and gold not in local_valid_relations)

        values = {
            "n": 1.0,
            "top1_correct": float(top1 == gold),
            "rashomon_gold_coverage": float(gold in rashomon_relations),
            "rashomon_size": float(len(path_completion.rashomon_candidates)),
            "path_tableau_gold_retention": float(gold in path_valid_relations),
            "path_rt_top1_correct": float(path_completion.top_relation == gold),
            "path_valid_worlds": float(len(path_completion.valid_worlds)),
            "path_rejected_worlds": float(len(path_completion.rejected_worlds)),
            "local_tableau_gold_retention": float(gold in local_valid_relations),
            "local_rt_top1_correct": float(local_completion.top_relation == gold),
            "local_valid_worlds": float(len(local_completion.valid_worlds)),
            "local_rejected_worlds": float(len(local_rejected)),
            "local_wrong_worlds_rejected": float(local_wrong_rejected),
            "local_gold_false_rejections": local_gold_false_rejected,
            "local_facts": float(len(local_facts)),
            "path_entropy": float(path_completion.entropy),
            "local_entropy": float(local_completion.entropy),
        }
        for key, value in values.items():
            totals[key] += value
            by_hop[hop][key] += value

        records.append(
            {
                "example_id": row["example_id"],
                "hop_count": hop,
                "head": row["head"],
                "tail": row["tail"],
                "gold_relation": gold,
                "top1_relation": top1,
                "rashomon_relations": sorted(rashomon_relations),
                "path_only": {
                    "valid_relations": sorted(path_valid_relations),
                    "rejected_relations": sorted(world.relation for world in path_completion.rejected_worlds),
                    "top_relation": path_completion.top_relation,
                    "relation_marginal": path_completion.relation_marginal,
                    "entropy": path_completion.entropy,
                },
                "local_subgraph": {
                    "fact_count": len(local_facts),
                    "valid_relations": sorted(local_valid_relations),
                    "rejected_relations": sorted(world.relation for world in local_rejected),
                    "rejection_clashes": {
                        world.relation: world.clashes for world in local_rejected
                    },
                    "top_relation": local_completion.top_relation,
                    "relation_marginal": local_completion.relation_marginal,
                    "entropy": local_completion.entropy,
                },
                "scores": {
                    candidate.relation: {
                        "support": candidate.support,
                        "contradiction": candidate.contradiction,
                        "unresolved": candidate.unresolved,
                    }
                    for candidate in ranked
                },
            }
        )
        if (index + 1) % 10 == 0 or index + 1 == len(prepared):
            print(f"assembled {index + 1}/{len(prepared)} results")

    def summarize(bucket: dict[str, float]) -> dict:
        n = bucket.get("n", 0.0)
        local_rejected = bucket.get("local_rejected_worlds", 0.0)
        return {
            "n": int(n),
            "top1_accuracy": safe_div(bucket.get("top1_correct", 0.0), n),
            "rashomon_gold_coverage": safe_div(bucket.get("rashomon_gold_coverage", 0.0), n),
            "avg_rashomon_size": safe_div(bucket.get("rashomon_size", 0.0), n),
            "path_tableau_gold_retention": safe_div(bucket.get("path_tableau_gold_retention", 0.0), n),
            "path_rashomon_tableau_top1_accuracy": safe_div(bucket.get("path_rt_top1_correct", 0.0), n),
            "path_avg_rejected_worlds": safe_div(bucket.get("path_rejected_worlds", 0.0), n),
            "local_tableau_gold_retention": safe_div(bucket.get("local_tableau_gold_retention", 0.0), n),
            "local_rashomon_tableau_top1_accuracy": safe_div(bucket.get("local_rt_top1_correct", 0.0), n),
            "local_avg_valid_worlds": safe_div(bucket.get("local_valid_worlds", 0.0), n),
            "local_avg_rejected_worlds": safe_div(local_rejected, n),
            "local_wrong_rejection_precision": safe_div(
                bucket.get("local_wrong_worlds_rejected", 0.0), local_rejected
            ),
            "local_gold_false_rejection_rate": safe_div(
                bucket.get("local_gold_false_rejections", 0.0), n
            ),
            "local_avg_fact_count": safe_div(bucket.get("local_facts", 0.0), n),
            "path_avg_entropy": safe_div(bucket.get("path_entropy", 0.0), n),
            "local_avg_entropy": safe_div(bucket.get("local_entropy", 0.0), n),
        }

    summary = {
        "protocol": {
            "dataset": root.name,
            "candidate_relations": len(relations),
            "epsilon": args.epsilon,
            "min_score": args.min_score,
            "batch_size": args.batch_size,
            "local_neighborhood_cap": args.local_neighborhood_cap,
            "scorer": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
            "gold_policy": "gold relation used only after scoring for evaluation",
            "scoring_evidence_policy": "selected train-graph directed multi-hop path only",
            "path_tableau_policy": "selected path plus proposed relation",
            "local_tableau_policy": (
                "selected path plus ontology-relevant one-hop train facts touching query/path nodes "
                "plus proposed relation"
            ),
        },
        "overall": summarize(totals),
        "by_hop": {str(hop): summarize(bucket) for hop, bucket in sorted(by_hop.items())},
        "records": records,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary["overall"], indent=2))
    print(output)


if __name__ == "__main__":
    main()
