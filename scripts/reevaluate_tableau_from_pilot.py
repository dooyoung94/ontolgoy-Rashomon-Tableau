from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from rashomon_tableau.kg_multihop_benchmark import KGTriple, path_as_literals, read_triples
from rashomon_tableau.multihop_completion import RelationCandidate, complete_missing_relation
from rashomon_tableau.ontology import Ontology


def ontology_predicates(ontology: Ontology) -> set[str]:
    predicates = set(ontology.symmetric)
    predicates.update(ontology.inverse)
    predicates.update(ontology.inverse.values())
    predicates.update(ontology.hierarchy)
    for parents in ontology.hierarchy.values():
        predicates.update(parents)
    for left, right in ontology.incompatible:
        predicates.update((left, right))
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


def as_path(row: dict) -> list[KGTriple]:
    return [KGTriple(x["head"], x["relation"], x["tail"]) for x in row["path"]]


def local_facts(
    path: list[KGTriple],
    row: dict,
    node_index: dict[str, list[KGTriple]],
    allowed: set[str],
    cap: int,
):
    focus = {row["head"], row["tail"]}
    for triple in path:
        focus.update((triple.head, triple.tail))

    selected: dict[tuple[str, str, str], KGTriple] = {
        (t.head, t.relation, t.tail): t for t in path
    }
    extra: dict[tuple[str, str, str], KGTriple] = {}
    for node in sorted(focus):
        for triple in node_index.get(node, []):
            if triple.relation not in allowed:
                continue
            key = (triple.head, triple.relation, triple.tail)
            if key not in selected:
                extra[key] = triple
    for key in sorted(extra)[: max(0, cap - len(selected))]:
        selected[key] = extra[key]
    triples = [selected[key] for key in sorted(selected)]
    return path_as_literals(triples, source="kg_local_tableau")


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="data/kg_benchmarks/WN18RR")
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--previous-result", required=True)
    ap.add_argument("--ontology", default="config/wn18rr_ontology_rules.yaml")
    ap.add_argument("--epsilon", type=float, default=0.05)
    ap.add_argument("--local-neighborhood-cap", type=int, default=16)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.dataset_dir)
    train = read_triples(root / "train.tsv")
    rows = [json.loads(x) for x in Path(args.benchmark).read_text(encoding="utf-8").splitlines() if x.strip()]
    previous = json.loads(Path(args.previous_result).read_text(encoding="utf-8"))
    prior_records = {r["example_id"]: r for r in previous["records"]}

    ontology = Ontology.from_yaml(args.ontology)
    node_index = build_node_index(train)
    allowed = ontology_predicates(ontology)

    totals = defaultdict(float)
    by_hop: dict[int, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    records = []

    for row in rows:
        prior = prior_records[row["example_id"]]
        path = as_path(row)
        path_literals = path_as_literals(path)
        candidates = []
        for relation, score in prior["scores"].items():
            candidates.append(
                RelationCandidate(
                    relation=relation,
                    score=float(score["support"]),
                    path=path_literals,
                    support=float(score["support"]),
                    contradiction=float(score["contradiction"]),
                    unresolved=float(score["unresolved"]),
                    origin="frozen-deberta-pilot",
                )
            )

        path_rt = complete_missing_relation(
            path_literals, row["head"], row["tail"], candidates, ontology, epsilon=args.epsilon
        )
        local = local_facts(path, row, node_index, allowed, args.local_neighborhood_cap)
        local_rt = complete_missing_relation(
            local, row["head"], row["tail"], candidates, ontology, epsilon=args.epsilon
        )

        gold = row["gold_relation"]
        rashomon = {c.relation for c in path_rt.rashomon_candidates}
        path_valid = {w.relation for w in path_rt.valid_worlds}
        local_valid = {w.relation for w in local_rt.valid_worlds}
        local_rejected = list(local_rt.rejected_worlds)
        hop = int(row["hop_count"])

        vals = {
            "n": 1.0,
            "rashomon_gold": float(gold in rashomon),
            "path_gold": float(gold in path_valid),
            "path_top1": float(path_rt.top_relation == gold),
            "path_rejected": float(len(path_rt.rejected_worlds)),
            "local_gold": float(gold in local_valid),
            "local_top1": float(local_rt.top_relation == gold),
            "local_rejected": float(len(local_rejected)),
            "local_wrong_rejected": float(sum(w.relation != gold for w in local_rejected)),
            "local_gold_false_rejected": float(gold in rashomon and gold not in local_valid),
            "local_facts": float(len(local)),
            "path_entropy": float(path_rt.entropy),
            "local_entropy": float(local_rt.entropy),
        }
        for k, v in vals.items():
            totals[k] += v
            by_hop[hop][k] += v

        records.append({
            "example_id": row["example_id"],
            "hop_count": hop,
            "gold_relation": gold,
            "rashomon_relations": sorted(rashomon),
            "path_valid_relations": sorted(path_valid),
            "local_valid_relations": sorted(local_valid),
            "local_rejected_relations": sorted(w.relation for w in local_rejected),
            "local_rejection_clashes": {w.relation: w.clashes for w in local_rejected},
            "local_fact_count": len(local),
            "path_top_relation": path_rt.top_relation,
            "local_top_relation": local_rt.top_relation,
        })

    def summary(b: dict[str, float]) -> dict:
        n = b.get("n", 0.0)
        rejected = b.get("local_rejected", 0.0)
        return {
            "n": int(n),
            "rashomon_gold_coverage": safe_div(b.get("rashomon_gold", 0), n),
            "path_tableau_gold_retention": safe_div(b.get("path_gold", 0), n),
            "path_rt_top1_accuracy": safe_div(b.get("path_top1", 0), n),
            "path_avg_rejected_worlds": safe_div(b.get("path_rejected", 0), n),
            "local_tableau_gold_retention": safe_div(b.get("local_gold", 0), n),
            "local_rt_top1_accuracy": safe_div(b.get("local_top1", 0), n),
            "local_avg_rejected_worlds": safe_div(rejected, n),
            "local_wrong_rejection_precision": safe_div(b.get("local_wrong_rejected", 0), rejected),
            "local_gold_false_rejection_rate": safe_div(b.get("local_gold_false_rejected", 0), n),
            "local_avg_fact_count": safe_div(b.get("local_facts", 0), n),
            "path_avg_entropy": safe_div(b.get("path_entropy", 0), n),
            "local_avg_entropy": safe_div(b.get("local_entropy", 0), n),
        }

    out = {
        "protocol": {
            "dataset": "WN18RR",
            "source_scores": "frozen from workflow run 32799621678",
            "epsilon": args.epsilon,
            "local_neighborhood_cap": args.local_neighborhood_cap,
            "comparison": "same candidates/scores; Tableau context only changes",
        },
        "overall": summary(totals),
        "by_hop": {str(h): summary(b) for h, b in sorted(by_hop.items())},
        "records": records,
    }
    p = Path(args.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out["overall"], indent=2))


if __name__ == "__main__":
    main()
