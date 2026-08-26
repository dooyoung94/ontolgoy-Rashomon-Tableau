from __future__ import annotations

import argparse
import json

from openrca_mr.stage1_eval import VARIANTS, run_stage1_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recover relations missing from an existing topology while collector data remains available"
        )
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--reference-data")
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="abduction")
    parser.add_argument("--topology-missing-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--relation-threshold", type=float, default=0.5)
    parser.add_argument(
        "--evaluation-relation-types",
        nargs="+",
        default=["calls", "uses_database"],
        help="Primary relation types to mask and score (default: calls uses_database).",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--allow-derived-reference",
        action="store_true",
        help=(
            "Allow a telemetry-derived embedded reference for diagnostic smoke tests. "
            "The output is labelled diagnostic_only and must not be reported as a paper result."
        ),
    )
    args = parser.parse_args()

    result = run_stage1_evaluation(
        data=args.data,
        out=args.out,
        variant=args.variant,
        reference_data=args.reference_data,
        topology_missing_ratio=args.topology_missing_ratio,
        seed=args.seed,
        relation_threshold=args.relation_threshold,
        limit=args.limit,
        allow_derived_reference=args.allow_derived_reference,
        evaluation_relation_types=frozenset(args.evaluation_relation_types),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
