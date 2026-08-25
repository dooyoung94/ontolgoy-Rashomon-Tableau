from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from openrca_mr.abduction import AbductiveRelationGenerator
from openrca_mr.metrics import (
    all_root_services_hit,
    any_root_service_hit,
    exact_root_set,
    node_metrics,
    process_path_reachability,
    root_set_metrics,
    service_edge_metrics,
)
from openrca_mr.models import CausalEdge, RcaCase, REL_OBSERVED
from openrca_mr.openrca2 import load_normalized_cases
from openrca_mr.pipeline import MissingRelationRCA
from openrca_mr.psl import PslGlobalInference
from openrca_mr.semantic import DebertaEvidenceScorer

EDGE_THRESHOLD = 0.5


def _inference_view(case: RcaCase) -> RcaCase:
    """Drop every gold field before model execution.

    Standard OpenRCA2 exposes telemetry but not topology or causal labels. The
    dependency candidates below were reconstructed only from normal traces by
    the adapter; every candidate is marked observed/unknown, never causal.
    """
    return RcaCase(
        case_id=case.case_id,
        symptom_nodes=list(case.symptom_nodes),
        known_edges=[CausalEdge(e.source, REL_OBSERVED, e.target) for e in case.known_edges],
        evidence=list(case.evidence),
        metadata={"dataset": "anon-ops/ops-lite", "input": "telemetry-derived only"},
    )


def _avg(rows: list[dict], key: str) -> float:
    vals = [float(row[key]) for row in rows]
    return mean(vals) if vals else 0.0


def _summarize(rows: list[dict]) -> dict:
    keys = [
        "root_service_precision",
        "root_service_recall",
        "root_service_f1",
        "root_service_exact",
        "any_service_hit",
        "all_service_hit",
        "path_reachability",
        "node_precision",
        "node_recall",
        "node_f1",
        "edge_precision",
        "edge_recall",
        "edge_f1",
    ]
    return {key: _avg(rows, key) for key in keys}


def run(data: str, out: str, limit: int = 0) -> None:
    cases = load_normalized_cases(data)
    if limit:
        cases = cases[:limit]

    model = MissingRelationRCA(
        generator=AbductiveRelationGenerator(max_candidates=None),
        semantic_scorer=DebertaEvidenceScorer(),
        global_inference=PslGlobalInference(),
        edge_threshold=EDGE_THRESHOLD,
        max_root_causes=3,
    )

    rows: list[dict] = []
    predictions: list[dict] = []
    for index, case in enumerate(cases, start=1):
        inference_case = _inference_view(case)
        pred = model.run(inference_case)

        root_metric = root_set_metrics(pred.predicted_root_causes, case.gold_root_causes)
        edge_metric = service_edge_metrics(pred.predicted_edges, case.gold_edges)
        node_metric = node_metrics(
            pred.predicted_edges,
            case.gold_edges,
            predicted_roots=pred.predicted_root_causes,
            gold_roots=case.gold_root_causes,
        )
        path = process_path_reachability(
            pred.predicted_edges,
            pred.predicted_root_causes,
            case.gold_root_causes,
            case.gold_alarm_nodes,
        )
        system = str(case.metadata.get("system") or "unknown")
        row = {
            "case_id": case.case_id,
            "system": system,
            "root_service_precision": root_metric.precision,
            "root_service_recall": root_metric.recall,
            "root_service_f1": root_metric.f1,
            "root_service_exact": exact_root_set(pred.predicted_root_causes, case.gold_root_causes),
            "any_service_hit": any_root_service_hit(pred.predicted_root_causes, case.gold_root_causes),
            "all_service_hit": all_root_services_hit(pred.predicted_root_causes, case.gold_root_causes),
            "path_reachability": path,
            "node_precision": node_metric.precision,
            "node_recall": node_metric.recall,
            "node_f1": node_metric.f1,
            "edge_precision": edge_metric.precision,
            "edge_recall": edge_metric.recall,
            "edge_f1": edge_metric.f1,
            "n_predicted_roots": len(pred.predicted_root_causes),
            "n_gold_roots": len(case.gold_root_causes),
            "n_predicted_edges": len(pred.predicted_edges),
            "n_gold_edges": len(case.gold_edges),
        }
        rows.append(row)
        predictions.append({
            "case_id": case.case_id,
            "root_causes": [{"service": service} for service in pred.predicted_root_causes],
            "propagation": [
                {"from": source, "to": target}
                for source, _, target in pred.predicted_edges
            ],
        })
        if index % 25 == 0 or index == len(cases):
            print(f"PROGRESS {index}/{len(cases)}")

    by_system = {}
    for system in sorted({row["system"] for row in rows}):
        subset = [row for row in rows if row["system"] == system]
        by_system[system] = {"n": len(subset), **_summarize(subset)}

    result = {
        "dataset_id": "anon-ops/ops-lite:standard-all-500",
        "method": "Abduction+DeBERTa+PSL",
        "n": len(rows),
        "edge_threshold": EDGE_THRESHOLD,
        "max_root_causes": 3,
        "protocol": {
            "masking": "none",
            "topology_input": "none supplied; candidate dependencies reconstructed from normal traces",
            "telemetry": "paired normal/abnormal traces, metrics, logs",
            "gold_usage": "evaluation only; stripped before MissingRelationRCA.run",
            "service_normalization": "lowercase; strip ts-; remove hyphen/underscore",
            "loadgen_filter": True,
            "process_metrics": "OpenRCA2 Appendix G service-level Edge F1, Node F1, Path Reachability",
            "outcome_scope": "service-only auxiliary metrics; fault_kind is not predicted in this run",
        },
        "summary": _summarize(rows),
        "per_system": by_system,
        "rows": rows,
        "predictions": predictions,
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"n": len(rows), "summary": result["summary"], "per_system": by_system}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    run(args.data, args.out, args.limit)


if __name__ == "__main__":
    main()
