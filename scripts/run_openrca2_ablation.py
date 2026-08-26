from __future__ import annotations

import argparse
import json
from pathlib import Path

from openrca_mr.abduction import AbductiveCausalRelationGenerator
from openrca_mr.masking import mask_causal_relation_types, mask_relations
from openrca_mr.metrics import (
    all_root_services_hit,
    any_root_service_hit,
    exact_root_set,
    is_loadgen,
    node_metrics,
    normalize_service,
    process_path_reachability,
    relation_classification_metrics,
    root_hit_at_k,
    root_set_metrics,
    service_edge_metrics,
)
from openrca_mr.models import REL_CAUSAL
from openrca_mr.openrca2 import load_normalized_cases
from openrca_mr.pipeline import IncidentCausalRCA
from openrca_mr.psl import PslGlobalInference
from openrca_mr.semantic import DebertaEvidenceScorer


VARIANTS = {
    "graph_only": (False, False, False),
    "abduction": (True, False, False),
    "abduction_deberta": (True, True, False),
    "abduction_psl": (True, False, True),
    "full": (True, True, True),
}

EDGE_THRESHOLD = 0.5


def _graph_only_prediction(case):
    # For causal relation masking, only explicitly visible causal labels count
    # as causal edges. Masked and known non-causal dependencies stay unresolved.
    predicted_edges = [edge.key() for edge in case.known_edges if edge.relation == REL_CAUSAL]
    anomaly_by_node = {}
    first_time = {}
    for evidence in case.evidence:
        if evidence.node in case.symptom_nodes:
            continue
        anomaly_by_node[evidence.node] = max(
            anomaly_by_node.get(evidence.node, 0.0), evidence.abnormality
        )
        if evidence.timestamp is not None and evidence.is_anomalous:
            first_time[evidence.node] = min(
                first_time.get(evidence.node, evidence.timestamp), evidence.timestamp
            )
    roots = sorted(
        anomaly_by_node,
        key=lambda node: (-anomaly_by_node[node], first_time.get(node, float("inf")), node),
    )[:3]
    return predicted_edges, roots


def _mean(rows: list[dict], key: str):
    values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
    return sum(values) / len(values) if values else None


def _pair(source: str, target: str) -> tuple[str, str]:
    return normalize_service(source), normalize_service(target)


def _pair_diagnostics(masked_truth, predicted_edges, hypotheses) -> list[dict]:
    predicted_pairs = {_pair(source, target) for source, _, target in predicted_edges}
    hypothesis_by_pair = {_pair(h.edge.source, h.edge.target): h for h in hypotheses}
    out: list[dict] = []
    for idx, truth in enumerate(masked_truth):
        if is_loadgen(truth.source) or is_loadgen(truth.target):
            continue
        key = _pair(truth.source, truth.target)
        h = hypothesis_by_pair.get(key)
        semantic_margin = None
        if (
            h is not None
            and h.semantic_support is not None
            and h.semantic_contradiction is not None
        ):
            semantic_margin = h.semantic_support - h.semantic_contradiction
        out.append(
            {
                "candidate_id": idx,
                "source": truth.source,
                "target": truth.target,
                "source_norm": key[0],
                "target_norm": key[1],
                # Evaluator-only labels below are intentionally stored for
                # diagnostics; the A5 script strips them before prompt creation.
                "truth_relation": truth.relation,
                "truth_causal": truth.relation == REL_CAUSAL,
                "predicted_causal": key in predicted_pairs,
                "abductive_score": h.abductive_score if h is not None else None,
                "temporal_score": h.temporal_score if h is not None else None,
                "anomaly_score": h.anomaly_score if h is not None else None,
                "semantic_support": h.semantic_support if h is not None else None,
                "semantic_contradiction": h.semantic_contradiction if h is not None else None,
                "semantic_neutral": h.semantic_neutral if h is not None else None,
                "semantic_margin": semantic_margin,
                "soft_logic_score": h.soft_logic_score if h is not None else None,
                "final_score": h.final_score if h is not None else None,
                "threshold": EDGE_THRESHOLD,
            }
        )
    return out


def _score_diagnostic_summary(rows: list[dict]) -> dict:
    pairs = [item for row in rows for item in row.get("pair_diagnostics", [])]

    def avg(key: str):
        vals = [float(x[key]) for x in pairs if x.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    def avg_abs_delta(a: str, b: str):
        vals = [
            abs(float(x[a]) - float(x[b]))
            for x in pairs
            if x.get(a) is not None and x.get(b) is not None
        ]
        return sum(vals) / len(vals) if vals else None

    semantic_margins = [
        abs(float(x["semantic_margin"]))
        for x in pairs
        if x.get("semantic_margin") is not None
    ]
    return {
        "n_masked_pairs_evaluated": len(pairs),
        "masked_positive_rate": (
            sum(bool(x["truth_causal"]) for x in pairs) / len(pairs) if pairs else None
        ),
        "predicted_positive_rate": (
            sum(bool(x["predicted_causal"]) for x in pairs) / len(pairs) if pairs else None
        ),
        "mean_abductive_score": avg("abductive_score"),
        "mean_semantic_margin": avg("semantic_margin"),
        "mean_abs_semantic_margin": (
            sum(semantic_margins) / len(semantic_margins) if semantic_margins else None
        ),
        "mean_semantic_neutral": avg("semantic_neutral"),
        "mean_soft_logic_score": avg("soft_logic_score"),
        "mean_final_score": avg("final_score"),
        "mean_abs_final_minus_abduction": avg_abs_delta("final_score", "abductive_score"),
    }


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
        model = IncidentCausalRCA(
            AbductiveCausalRelationGenerator(max_candidates=None),
            semantic,
            logic,
            edge_threshold=EDGE_THRESHOLD,
        )

    cases = load_normalized_cases(data)
    if limit:
        cases = cases[:limit]

    rows = []
    for case in cases:
        if mask_mode == "relation":
            visible, masked = mask_causal_relation_types(case, mask_ratio, seed)
        elif mask_mode == "edge":
            # Legacy stress test that physically removes grounded candidate
            # pairs. It is not the paper's structural-recovery protocol.
            visible, masked = mask_relations(case, mask_ratio, seed)
        elif mask_mode == "none":
            visible, masked = case, []
        else:
            raise ValueError(f"unknown mask mode: {mask_mode}")

        hypotheses = []
        if model is None:
            predicted_edges, predicted_roots = _graph_only_prediction(visible)
        else:
            pred = model.run(visible)
            predicted_edges = pred.predicted_edges
            predicted_roots = pred.predicted_root_causes
            hypotheses = pred.ranked_hypotheses

        process_edge = service_edge_metrics(predicted_edges, case.gold_edges)
        process_node = node_metrics(
            predicted_edges,
            case.gold_edges,
            predicted_roots=predicted_roots,
            gold_roots=case.gold_root_causes,
        )
        root_service = root_set_metrics(predicted_roots, case.gold_root_causes)
        path_reachability = process_path_reachability(
            predicted_edges,
            predicted_roots,
            case.gold_root_causes,
            case.gold_alarm_nodes or case.symptom_nodes,
        )
        relation = (
            relation_classification_metrics(predicted_edges, masked)
            if mask_mode == "relation" and masked
            else None
        )
        edge_removal = (
            service_edge_metrics(predicted_edges, masked)
            if mask_mode == "edge" and masked
            else None
        )
        pair_diagnostics = (
            _pair_diagnostics(masked, predicted_edges, hypotheses)
            if mask_mode == "relation" and masked
            else []
        )

        rows.append(
            {
                "case_id": case.case_id,
                # OpenRCA 2.0-compatible outcome/process metrics.
                "root_service_precision": root_service.precision,
                "root_service_recall": root_service.recall,
                "root_service_f1": root_service.f1,
                "root_service_exact": exact_root_set(predicted_roots, case.gold_root_causes),
                "any_service_hit": any_root_service_hit(predicted_roots, case.gold_root_causes),
                "all_service_hit": all_root_services_hit(predicted_roots, case.gold_root_causes),
                "path_reachability": path_reachability,
                "node_precision": process_node.precision,
                "node_recall": process_node.recall,
                "node_f1": process_node.f1,
                "edge_precision": process_edge.precision,
                "edge_recall": process_edge.recall,
                "edge_f1": process_edge.f1,
                # Main controlled Stage-2 causal relation diagnostics.
                "relation_accuracy": relation.accuracy if relation else None,
                "relation_precision": relation.precision if relation else None,
                "relation_recall": relation.recall if relation else None,
                "relation_f1": relation.f1 if relation else None,
                "process_path_reachability": path_reachability,
                "root_exact_set": exact_root_set(predicted_roots, case.gold_root_causes),
                "root_hit_at_1": root_hit_at_k(predicted_roots, case.gold_root_causes, 1),
                "root_hit_at_3": root_hit_at_k(predicted_roots, case.gold_root_causes, 3),
                # Legacy physical edge-removal stress metrics; explicitly not
                # called structural relation recovery.
                "edge_removal_precision": edge_removal.precision if edge_removal else None,
                "edge_removal_recall": edge_removal.recall if edge_removal else None,
                "edge_removal_f1": edge_removal.f1 if edge_removal else None,
                "n_predicted_edges": len(predicted_edges),
                "n_gold_edges": len(case.gold_edges),
                "n_masked_relations": len(masked) if mask_mode == "relation" else 0,
                "n_removed_edges": len(masked) if mask_mode == "edge" else 0,
                # Stored for downstream A5 adjudication. No gold values are
                # consumed by the A5 prompt; diagnostics are sanitized before use.
                "predicted_roots": list(predicted_roots),
                "predicted_edges": [list(edge) for edge in predicted_edges],
                "pair_diagnostics": pair_diagnostics,
            }
        )

    metric_exclude = {
        "case_id",
        "predicted_roots",
        "predicted_edges",
        "pair_diagnostics",
    }
    metrics = [
        key
        for key, value in (rows[0].items() if rows else [])
        if key not in metric_exclude
        and not key.startswith("n_")
        and isinstance(value, (int, float))
    ]
    result = {
        "dataset_id": dataset_id,
        "track": "stage2_incident_causal_qualification",
        "variant": variant,
        "mask_mode": mask_mode,
        "mask_ratio": mask_ratio,
        "seed": seed,
        "n": len(rows),
        "edge_threshold": EDGE_THRESHOLD,
        "protocol": {
            "main_task": "qualify masked causal-vs-noncausal semantics on grounded service pairs",
            "structural_relation_visibility": "preserved for relation masking",
            "candidate_policy": "score every grounded unresolved pair; no candidate cap in main benchmark",
            "edge_metric": "OpenRCA2-style directed normalized service pair; relation label ignored",
            "node_metric": "OpenRCA2-style service nodes from propagation edges plus predicted/gold roots",
            "outcome_metrics": "root service P/R/F1 + exact + AnySvc + AllSvc",
            "relation_metric": "binary masked incident relation classification: causal_propagates_to vs non_causal_dependency",
            "path_reachability": "correct predicted root -> gold alarm service via predicted causal edges",
            "gold_usage": "gold causal edges construct controlled causal-mask labels and evaluation only; masked labels are hidden from model",
            "threshold_policy": "fixed 0.5 for A1-A4; no full-set threshold tuning",
            "edge_mode_note": "mask-mode=edge is a legacy physical-edge-removal stress test, not Stage-1 structural relation recovery",
        },
        "summary": {m: _mean(rows, m) for m in metrics},
        "score_diagnostics": _score_diagnostic_summary(rows),
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
    run(
        args.data,
        args.out,
        args.mask_ratio,
        args.mask_mode,
        args.seed,
        args.variant,
        args.limit,
        args.dataset_id,
    )


if __name__ == "__main__":
    main()
