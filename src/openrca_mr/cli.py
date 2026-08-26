from __future__ import annotations

import argparse
import json

from .abduction import AbductiveCausalRelationGenerator
from .masking import mask_causal_relation_types
from .metrics import (
    process_path_reachability,
    relation_classification_metrics,
    root_hit_at_k,
)
from .openrca2 import load_normalized_cases
from .pipeline import IncidentCausalRCA
from .psl import PslGlobalInference, SoftLogicApproximation
from .semantic import DebertaEvidenceScorer, DeterministicEvidenceScorer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "OpenRCA 2.0 Stage-2 controlled incident-causal relation qualification. "
            "Stage-1 structural recovery uses scripts/run_structural_recovery.py."
        )
    )
    parser.add_argument("data", help="Normalized OpenRCA 2.0 JSONL")
    parser.add_argument("--mask-ratio", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--semantic",
        choices=["deberta", "deterministic", "none"],
        default="none",
    )
    parser.add_argument("--logic", choices=["psl", "soft", "none"], default="none")
    parser.add_argument("--limit", type=int, default=0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cases = load_normalized_cases(args.data)
    if args.limit:
        cases = cases[: args.limit]

    semantic = {
        "deberta": lambda: DebertaEvidenceScorer(),
        "deterministic": lambda: DeterministicEvidenceScorer(),
        "none": lambda: None,
    }[args.semantic]()
    logic = {
        "psl": lambda: PslGlobalInference(),
        "soft": lambda: SoftLogicApproximation(),
        "none": lambda: None,
    }[args.logic]()

    model = IncidentCausalRCA(
        generator=AbductiveCausalRelationGenerator(),
        semantic_scorer=semantic,
        global_inference=logic,
    )

    rows = []
    for case in cases:
        visible, masked_truth = mask_causal_relation_types(
            case, args.mask_ratio, args.seed
        )
        prediction = model.run(visible)
        relation = relation_classification_metrics(
            prediction.predicted_edges, masked_truth
        )
        rows.append(
            {
                "case_id": case.case_id,
                "mask_ratio": args.mask_ratio,
                "causal_relation_accuracy": relation.accuracy,
                "causal_relation_precision": relation.precision,
                "causal_relation_recall": relation.recall,
                "causal_relation_f1": relation.f1,
                "root_hit_at_1": root_hit_at_k(
                    prediction.predicted_root_causes, case.gold_root_causes, 1
                ),
                "root_hit_at_3": root_hit_at_k(
                    prediction.predicted_root_causes, case.gold_root_causes, 3
                ),
                "process_path_reachability": process_path_reachability(
                    prediction.predicted_edges,
                    prediction.predicted_root_causes,
                    case.gold_root_causes,
                    case.gold_alarm_nodes,
                ),
            }
        )

    keys = [
        "causal_relation_accuracy",
        "causal_relation_precision",
        "causal_relation_recall",
        "causal_relation_f1",
        "root_hit_at_1",
        "root_hit_at_3",
        "process_path_reachability",
    ]
    summary = {
        key: sum(row[key] for row in rows) / len(rows) if rows else 0.0
        for key in keys
    }
    print(
        json.dumps(
            {
                "track": "stage2_incident_causal_qualification",
                "n": len(rows),
                "summary": summary,
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
