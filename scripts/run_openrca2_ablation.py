from __future__ import annotations

import argparse
import json
from pathlib import Path

from openrca_mr.abduction import AbductiveRelationGenerator
from openrca_mr.masking import mask_relation_types, mask_relations
from openrca_mr.metrics import (
    exact_root_set,
    node_metrics,
    process_path_reachability,
    relation_classification_metrics,
    root_hit_at_k,
    service_edge_metrics,
)
from openrca_mr.models import REL_CAUSAL
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
    # For relation masking, only explicitly visible causal labels count as
    # causal edges. Masked and known non-causal dependencies stay unresolved.
    predicted_edges = [edge.key() for edge in case.known_edges if edge.relation == REL_CAUSAL]
    anomaly_by_node = {}
    first_time = {}
    for evidence in case.evidence:
        if evidence.node in case.symptom_nodes:
            continue
        anomaly_by_node[evidence.node] = max(anomaly_by_node.get(evidence.node, 0.0), evidence.abnormality)
        if evidence.timestamp is not None and evidence.is_anomalous:
            first_time[evidence.node] = min(first_time.get(evidence.node, evidence.timestamp), evidence.timestamp)
    roots = sorted(
        anomaly_by_node,
        key=lambda node: (-anomaly_by_node[node], first_time.get(node, float("inf")), node),
    )[:3]
    return predicted_edges, roots


def _mean(rows: list[dict], key: str):
    values = [row[key] for row in rows if row.get(key) is not None]
    return sum(values) / len(values) if values else None


def run(
    data: str,
    out: str,
    mask_ratio: float,
    mask_mode: str,
    seed: int,
    variant: str,
    limit: int,
    dataset_id: str,
) -> None:
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
        if mask_mode == "relation":
            visible, masked = mask_relation_types(case, mask_ratio, seed)
        elif mask_mode == "edge":
            visible, masked = mask_relations(case, mask_ratio, seed)
        elif mask_mode == "none":
            visible, masked = case, []
        else:
            raise ValueError(f"unknown mask mode: {mask_mode}")

        if model is None:
            predicted_edges, predicted_roots = _graph_only_prediction(visible)
        else:
            pred = model.run(visible)
            predicted_edges = pred.predicted_edges
            predicted_roots = pred.predicted_root_causes

        process_edge = service_edge_metrics(predicted_edges, case.gold_edges)
        process_node = node_metrics(predicted_edges, case.gold_edges)
        relation = relation_classification_metrics(predicted_edges, masked) if mask_mode == "relation" and masked else None
        missing = service_edge_metrics(predicted_edges, masked) if mask_mode == "edge" and masked else None

        rows.append({
            "case_id": case.case_id,
            "node_precision": process_node.precision,
            "node_recall": process_node.recall,
            "node_f1": process_node.f1,
            "edge_precision": process_edge.precision,
            "edge_recall": process_edge.recall,
            "edge_f1": process_edge.f1,
            "relation_accuracy": relation.accuracy if relation else None,
            "relation_precision": relation.precision if relation else None,
            "relation_recall": relation.recall if relation else None,
            "relation_f1": relation.f1 if relation else None,
            "process_path_reachability": process_path_reachability(
                predicted_edges,
                predicted_roots,
                case.gold_root_causes,
                case.gold_alarm_nodes or case.symptom_nodes,
            ),
            "root_exact_set": exact_root_set(predicted_roots, case.gold_root_causes),
            "root_hit_at_1": root_hit_at_k(predicted_roots, case.gold_root_causes, 1),
            "root_hit_at_3": root_hit_at_k(predicted_roots, case.gold_root_causes, 3),
            "missing_edge_precision": missing.precision if missing else None,
            "missing_edge_recall": missing.recall if missing else None,
            "missing_edge_f1": missing.f1 if missing else None,
            "n_predicted_edges": len(predicted_edges),
            "n_gold_edges": len(case.gold_edges),
            "n_masked_relations": len(masked) if mask_mode == "relation" else 0,
            "n_masked_edges": len(masked) if mask_mode == "edge" else 0,
        })

    metrics = [key for key in rows[0] if key != "case_id" and not key.startswith("n_")] if rows else []
    result = {
        "dataset_id": dataset_id,
        "variant": variant,
        "mask_mode": mask_mode,
        "mask_ratio": mask_ratio,
        "seed": seed,
        "n": len(rows),
        "protocol": {
            "main_task": "recover masked causal-vs-noncausal relation semantics on observed service pairs",
            "structural_edge_visibility": "preserved for relation masking",
            "edge_metric": "directed normalized service pair; relation label ignored for OpenRCA process scoring",
            "relation_metric": "binary masked-relation classification: causal_propagates_to vs non_causal_dependency",
            "process_path_reachability": "correct predicted root -> gold alarm service via predicted causal edges",
            "gold_usage": "gold causal edges construct controlled relation-mask labels and evaluation only; masked labels are hidden from model",
        },
        "summary": {m: _mean(rows, m) for m in metrics},
        "rows": rows,
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dataset-id", default="OpenRCA2-normalized")
    parser.add_argument("--mask-mode", choices=["relation", "edge", "none"], default="relation")
    parser.add_argument("--mask-ratio", type=float, default=0.40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="full")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    run(args.data, args.out, args.mask_ratio, args.mask_mode, args.seed, args.variant, args.limit, args.dataset_id)


if __name__ == "__main__":
    main()
