from __future__ import annotations

import argparse
import json

from openrca_mr.reference_topology import build_independent_reference


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build an evaluator-only normalized topology reference from a versioned "
            "external CSV. The CSV must contain topology_group,source,relation,target."
        )
    )
    parser.add_argument("--data", required=True, help="Normalized model-input JSONL")
    parser.add_argument("--external-topology-csv", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--source", required=True, help="External artifact/source name")
    parser.add_argument("--version", required=True, help="Immutable version or commit")
    parser.add_argument(
        "--attest-independent-of-model-observations",
        action="store_true",
        help=(
            "Required declaration that the external topology was not derived from the "
            "telemetry observations consumed by the recovery model."
        ),
    )
    parser.add_argument(
        "--include-auxiliary-has-service",
        action="store_true",
        help="Include HAS_SERVICE as visible auxiliary context, not a primary target.",
    )
    args = parser.parse_args()

    cases = build_independent_reference(
        data=args.data,
        external_topology_csv=args.external_topology_csv,
        out=args.out,
        source=args.source,
        version=args.version,
        independent_attested=args.attest_independent_of_model_observations,
        include_auxiliary_has_service=args.include_auxiliary_has_service,
    )
    print(
        json.dumps(
            {
                "out": args.out,
                "n_cases": len(cases),
                "n_relations": sum(len(case.structural_relations) for case in cases),
                "status": "evaluator_only_reference_built",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
