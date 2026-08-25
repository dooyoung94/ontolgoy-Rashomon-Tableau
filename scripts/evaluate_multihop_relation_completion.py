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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default="data/kg_benchmarks/WN18RR")
    parser.add_argument("--benchmark", default="data/kg_benchmarks/WN18RR/multihop_test.jsonl")
    parser.add_argument("--ontology", default="config/wn18rr_ontology_rules.yaml")
    parser.add_argument("--epsilon", type=float, default=0.05)
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=100)
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

    totals = defaultdict(float)
    by_hop: dict[int, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    records = []

    for index, row in enumerate(benchmark_rows):
        path = as_path(row)
        evidence = path_evidence_text(path, mappings)
        queries = [candidate_relation_text(row["head"], relation, row["tail"], mappings) for relation in relations]
        evidence_groups = [evidence for _ in relations]
        nli_scores = scorer.score_many(queries, evidence_groups, batch_size=min(32, len(relations)))

        candidates = [
            RelationCandidate(
                relation=relation,
                score=score.support,
                path=path_as_literals(path),
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

        completion = complete_missing_relation(
            path_as_literals(path),
            row["head"],
            row["tail"],
            candidates,
            ontology,
            epsilon=args.epsilon,
            min_score=args.min_score,
        )
        valid_relations = {world.relation for world in completion.valid_worlds}
        gold = row["gold_relation"]
        hop = int(row["hop_count"])

        values = {
            "n": 1.0,
            "top1_correct": float(top1 == gold),
            "rashomon_gold_coverage": float(gold in rashomon_relations),
            "tableau_gold_retention": float(gold in valid_relations),
            "rt_top1_correct": float(completion.top_relation == gold),
            "rashomon_size": float(len(completion.rashomon_candidates)),
            "valid_worlds": float(len(completion.valid_worlds)),
            "rejected_worlds": float(len(completion.rejected_worlds)),
            "entropy": float(completion.entropy),
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
                "valid_relations": sorted(valid_relations),
                "rejected_relations": sorted(world.relation for world in completion.rejected_worlds),
                "rt_top_relation": completion.top_relation,
                "relation_marginal": completion.relation_marginal,
                "entropy": completion.entropy,
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
        if (index + 1) % 10 == 0:
            print(f"evaluated {index + 1}/{len(benchmark_rows)}")

    def summarize(bucket: dict[str, float]) -> dict:
        n = bucket.get("n", 0.0)
        return {
            "n": int(n),
            "top1_accuracy": safe_div(bucket.get("top1_correct", 0.0), n),
            "rashomon_gold_coverage": safe_div(bucket.get("rashomon_gold_coverage", 0.0), n),
            "tableau_gold_retention": safe_div(bucket.get("tableau_gold_retention", 0.0), n),
            "rashomon_tableau_top1_accuracy": safe_div(bucket.get("rt_top1_correct", 0.0), n),
            "avg_rashomon_size": safe_div(bucket.get("rashomon_size", 0.0), n),
            "avg_valid_worlds": safe_div(bucket.get("valid_worlds", 0.0), n),
            "avg_rejected_worlds": safe_div(bucket.get("rejected_worlds", 0.0), n),
            "avg_entropy": safe_div(bucket.get("entropy", 0.0), n),
        }

    summary = {
        "protocol": {
            "dataset": root.name,
            "candidate_relations": len(relations),
            "epsilon": args.epsilon,
            "min_score": args.min_score,
            "scorer": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
            "gold_policy": "gold relation used only after scoring for evaluation",
            "evidence_policy": "train-graph directed multi-hop path only",
            "tableau_policy": "ontology SAT filter over path evidence plus proposed relation",
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
