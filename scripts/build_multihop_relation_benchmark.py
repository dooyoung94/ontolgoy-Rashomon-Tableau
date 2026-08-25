from __future__ import annotations

import argparse
import json
from pathlib import Path

from rashomon_tableau.kg_multihop_benchmark import (
    build_multihop_examples,
    read_triples,
)


def serialize(example) -> dict:
    return {
        "example_id": example.example_id,
        "head": example.head,
        "gold_relation": example.gold_relation,
        "tail": example.tail,
        "hop_count": example.hop_count,
        "path": [
            {"head": t.head, "relation": t.relation, "tail": t.tail}
            for t in example.path
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default="data/kg_benchmarks/WN18RR")
    parser.add_argument("--target-split", choices=("dev", "test"), default="test")
    parser.add_argument("--min-hops", type=int, default=2)
    parser.add_argument("--max-hops", type=int, default=4)
    parser.add_argument("--max-examples", type=int, default=500)
    parser.add_argument("--max-paths-per-target", type=int, default=1)
    parser.add_argument("--output", default="data/kg_benchmarks/WN18RR/multihop_test.jsonl")
    args = parser.parse_args()

    root = Path(args.dataset_dir)
    train = read_triples(root / "train.tsv")
    targets = read_triples(root / f"{args.target_split}.tsv")
    examples = build_multihop_examples(
        train,
        targets,
        min_hops=args.min_hops,
        max_hops=args.max_hops,
        max_examples=args.max_examples,
        max_paths_per_target=args.max_paths_per_target,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(serialize(example), ensure_ascii=False) + "\n")

    counts = {}
    for example in examples:
        counts[str(example.hop_count)] = counts.get(str(example.hop_count), 0) + 1
    print(json.dumps({"examples": len(examples), "hop_counts": counts, "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
