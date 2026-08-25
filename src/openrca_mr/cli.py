from __future__ import annotations

import argparse
import json

from .abduction import AbductiveRelationGenerator
from .masking import mask_relations
from .metrics import edge_metrics, path_reachability, root_hit_at_k
from .openrca2 import load_normalized_cases
from .pipeline import MissingRelationRCA
from .psl import PslGlobalInference, SoftLogicApproximation
from .semantic import DebertaEvidenceScorer, DeterministicEvidenceScorer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenRCA 2.0 missing-relation experiment")
    parser.add_argument("data", help="Normalized OpenRCA 2.0 JSONL")
    parser.add_argument("--mask-ratio", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--semantic", choices=["deberta", "deterministic", "none"], default="none")
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

    model = MissingRelationRCA(
        generator=AbductiveRelationGenerator(),
        semantic_scorer=semantic,
        global_inference=logic,
    )

    rows = []
    for case in cases:
        visible, masked = mask_relations(case, args.mask_ratio, args.seed)
        prediction = model.run(visible)
        # Masked edges are evaluator-side gold only. Full PAVE gold is evaluated
        # separately using the official/normalized labels.
        missing = edge_metrics(prediction.predicted_edges, masked)
        rows.append(
            {
                "case_id": case.case_id,
                "mask_ratio": args.mask_ratio,
                "missing_edge_precision": missing.precision,
                "missing_edge_recall": missing.recall,
                "missing_edge_f1": missing.f1,
                "root_hit_at_1": root_hit_at_k(prediction.predicted_root_causes, case.gold_root_causes, 1),
                "root_hit_at_3": root_hit_at_k(prediction.predicted_root_causes, case.gold_root_causes, 3),
                "path_reachability": path_reachability(
                    prediction.predicted_edges, case.gold_root_causes, case.symptom_nodes
                ),
            }
        )

    keys = [
        "missing_edge_precision",
        "missing_edge_recall",
        "missing_edge_f1",
        "root_hit_at_1",
        "root_hit_at_3",
        "path_reachability",
    ]
    summary = {
        key: sum(row[key] for row in rows) / len(rows) if rows else 0.0
        for key in keys
    }
    print(json.dumps({"n": len(rows), "summary": summary, "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
