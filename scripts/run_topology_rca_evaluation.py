from __future__ import annotations

import argparse
import json

from openrca_mr.topology_rca_eval import RCA_VARIANTS, TOPOLOGY_VARIANTS, run_topology_rca_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate topology relation recovery and downstream OpenRCA 2.0 RCA together"
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--reference-data")
    parser.add_argument("--out", required=True)
    parser.add_argument("--topology-variant", choices=sorted(TOPOLOGY_VARIANTS), default="abduction_deberta_psl")
    parser.add_argument("--rca-variant", choices=sorted(RCA_VARIANTS), default="abduction_psl")
    parser.add_argument("--topology-missing-ratio", type=float, default=0.4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--relation-threshold", type=float, default=0.5)
    parser.add_argument("--rca-edge-threshold", type=float, default=0.5)
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

    result = run_topology_rca_evaluation(
        data=args.data,
        out=args.out,
        topology_variant=args.topology_variant,
        rca_variant=args.rca_variant,
        topology_missing_ratio=args.topology_missing_ratio,
        seed=args.seed,
        relation_threshold=args.relation_threshold,
        rca_edge_threshold=args.rca_edge_threshold,
        limit=args.limit,
        reference_data=args.reference_data,
        allow_derived_reference=args.allow_derived_reference,
        evaluation_relation_types=frozenset(args.evaluation_relation_types),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
