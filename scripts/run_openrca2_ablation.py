from __future__ import annotations

import argparse
import json
from pathlib import Path

from openrca_mr.abduction import AbductiveRelationGenerator
from openrca_mr.masking import mask_relations
from openrca_mr.metrics import edge_metrics, path_reachability, root_hit_at_k
from openrca_mr.openrca2 import load_normalized_cases
from openrca_mr.pipeline import MissingRelationRCA
from openrca_mr.psl import PslGlobalInference
from openrca_mr.semantic import DebertaEvidenceScorer


VARIANTS = {
    "graph_only": (False, False, False),
    "abduction": (True, False, False),
    "abduction_deberta": (True, True, False),
    "abduction_psl": (True, False, True),
    "full": (True, True, True),
}


def _graph_only_prediction(case):
    predicted_edges = [edge.key() for edge in case.known_edges]
    anomaly_by_node = {}
    for evidence in case.evidence:
        if evidence.node in case.symptom_nodes:
            continue
        anomaly_by_node[evidence.node] = max(anomaly_by_node.get(evidence.node, 0.0), evidence.abnormality)
    roots = [node for node, _ in sorted(anomaly_by_node.items(), key=lambda x: x[1], reverse=True)][:3]
    return predicted_edges, roots


def run(data: str, out: str, mask_ratio: float, seed: int, variant: str, limit: int) -> None:
    use_abduction, use_deberta, use_psl = VARIANTS[variant]
    model = None
    if use_abduction:
        semantic = DebertaEvidenceScorer() if use_deberta else None
        logic = PslGlobalInference() if use_psl else None
        model = MissingRelationRCA(AbductiveRelationGenerator(), semantic, logic)

    cases = load_normalized_cases(data)
    if limit:
        cases = cases[:limit]

    rows = []
    for case in cases:
        visible, masked = mask_relations(case, mask_ratio, seed)
        if model is None:
            predicted_edges, predicted_roots = _graph_only_prediction(visible)
        else:
            pred = model.run(visible)
            predicted_edges = pred.predicted_edges
            predicted_roots = pred.predicted_root_causes

        missing = edge_metrics(predicted_edges, masked)
        rows.append({
            "case_id": case.case_id,
            "missing_edge_precision": missing.precision,
            "missing_edge_recall": missing.recall,
            "missing_edge_f1": missing.f1,
            "root_hit_at_1": root_hit_at_k(predicted_roots, case.gold_root_causes, 1),
            "root_hit_at_3": root_hit_at_k(predicted_roots, case.gold_root_causes, 3),
            "path_reachability": path_reachability(predicted_edges, case.gold_root_causes, case.symptom_nodes),
        })

    metrics = [key for key in rows[0] if key != "case_id"] if rows else []
    result = {
        "dataset": "OpenRCA 2.0",
        "variant": variant,
        "mask_ratio": mask_ratio,
        "seed": seed,
        "n": len(rows),
        "summary": {m: sum(r[m] for r in rows) / len(rows) for m in metrics} if rows else {},
        "rows": rows,
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mask-ratio", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="full")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    run(args.data, args.out, args.mask_ratio, args.seed, args.variant, args.limit)


if __name__ == "__main__":
    main()
