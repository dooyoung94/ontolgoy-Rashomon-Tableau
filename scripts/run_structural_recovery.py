from __future__ import annotations

import argparse
import json

from openrca_mr.stage1_eval import VARIANTS, run_stage1_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Stage-1 structural relation recovery evaluation for OpenRCA normalized cases"
        )
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--reference-data")
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="observation_abduction")
    parser.add_argument("--observation-drop-ratio", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--relation-threshold", type=float, default=0.5)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    result = run_stage1_evaluation(
        data=args.data,
        out=args.out,
        variant=args.variant,
        reference_data=args.reference_data,
        observation_drop_ratio=args.observation_drop_ratio,
        seed=args.seed,
        relation_threshold=args.relation_threshold,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
