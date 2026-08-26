from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .models import RcaCase, STRUCTURAL_RELATION_TYPES
from .openrca2 import load_normalized_cases
from .psl import PslStructuralInference
from .semantic import DebertaStructuralRelationScorer
from .structural import relation_type_counts, structural_relation_metrics
from .topology_recovery import mask_topology_relations, recover_missing_topology_relations


# 논문 표의 이름과 코드 이름을 맞춘다.
# S0: 복원 없음
# S1: 귀추만 사용
# S2: 귀추 + DeBERTa
# S3: 귀추 + PSL
# S4: 귀추 + DeBERTa + PSL
VARIANTS = {
    "topology_only": (False, False, False),
    "abduction": (True, False, False),
    "abduction_deberta": (True, True, False),
    "abduction_psl": (True, False, True),
    "abduction_deberta_psl": (True, True, True),
}


def _mean(rows: list[dict], key: str) -> float | None:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return sum(values) / len(values) if values else None


def _unique_case_map(cases: list[RcaCase], label: str) -> dict[str, RcaCase]:
    out: dict[str, RcaCase] = {}
    duplicates: set[str] = set()
    for case in cases:
        if case.case_id in out:
            duplicates.add(case.case_id)
        out[case.case_id] = case
    if duplicates:
        raise ValueError(f"duplicate case_id values in {label}: {sorted(duplicates)}")
    return out


def _typed_keys(relations) -> set[tuple[str, str, str]]:
    return {
        edge.key()
        for edge in relations
        if edge.relation in STRUCTURAL_RELATION_TYPES
    }


def _micro_from_counts(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def run_stage1_evaluation(
    data: str,
    out: str,
    variant: str,
    reference_data: str | None = None,
    topology_missing_ratio: float = 0.2,
    seed: int = 42,
    relation_threshold: float = 0.5,
    limit: int = 0,
) -> dict:
    """Evaluate recovery when relations are absent from an existing topology.

    Model-visible input:
      1. topology with a controlled fraction of relations removed
      2. collector observations left completely unchanged

    Evaluation-only reference:
      complete structural topology before masking

    No causal graph, fault label, root-cause label, or removed-relation marker is
    exposed to the recovery method.
    """

    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    if not 0.0 <= topology_missing_ratio <= 1.0:
        raise ValueError("topology_missing_ratio must be in [0, 1]")
    if not 0.0 <= relation_threshold <= 1.0:
        raise ValueError("relation_threshold must be in [0, 1]")

    do_recovery, use_deberta, use_psl = VARIANTS[variant]
    cases = load_normalized_cases(data)
    _unique_case_map(cases, "input data")
    if limit:
        cases = cases[:limit]

    if reference_data:
        reference_cases = load_normalized_cases(reference_data)
        reference_map = _unique_case_map(reference_cases, "reference data")
        reference_protocol = "independent_topology_reference"
    else:
        reference_map = _unique_case_map(cases, "embedded complete topology")
        reference_protocol = "controlled_topology_relation_missingness"

    missing_case_ids = [case.case_id for case in cases if case.case_id not in reference_map]
    if missing_case_ids:
        raise ValueError(
            "reference data is missing input case_id values: "
            + ", ".join(sorted(missing_case_ids))
        )

    semantic = DebertaStructuralRelationScorer() if use_deberta else None
    logic = PslStructuralInference() if use_psl else None

    rows: list[dict] = []
    missing_tp = missing_fp = missing_fn = 0
    full_tp = full_fp = full_fn = 0
    type_counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for case in cases:
        full_truth = list(reference_map[case.case_id].structural_relations)
        masked = mask_topology_relations(
            case_id=case.case_id,
            full_relations=full_truth,
            ratio=topology_missing_ratio,
            seed=seed,
        )

        if do_recovery:
            recovered = recover_missing_topology_relations(
                visible_relations=masked.visible_relations,
                observations=list(case.relation_observations),
                semantic_scorer=semantic,
                global_inference=logic,
                relation_threshold=relation_threshold,
            )
            added_relations = recovered.added_relations
            final_topology = recovered.recovered_topology
            n_hypotheses = len(recovered.hypotheses)
        else:
            added_relations = []
            final_topology = list(masked.visible_relations)
            n_hypotheses = 0

        # 주 지표: 실제로 토폴로지에서 제거한 관계를 얼마나 되찾았는가.
        missing_score = structural_relation_metrics(added_relations, masked.missing_relations)
        pred_missing = _typed_keys(added_relations)
        gold_missing = _typed_keys(masked.missing_relations)
        tp_keys = pred_missing & gold_missing
        fp_keys = pred_missing - gold_missing
        fn_keys = gold_missing - pred_missing
        missing_tp += len(tp_keys)
        missing_fp += len(fp_keys)
        missing_fn += len(fn_keys)

        for key in tp_keys:
            type_counts[key[1]]["tp"] += 1
        for key in fp_keys:
            type_counts[key[1]]["fp"] += 1
        for key in fn_keys:
            type_counts[key[1]]["fn"] += 1

        # 보조 지표: 복원 후 전체 토폴로지가 원래 토폴로지와 얼마나 같은가.
        full_score = structural_relation_metrics(final_topology, full_truth)
        pred_full = _typed_keys(final_topology)
        gold_full = _typed_keys(full_truth)
        full_tp += len(pred_full & gold_full)
        full_fp += len(pred_full - gold_full)
        full_fn += len(gold_full - pred_full)

        rows.append(
            {
                "case_id": case.case_id,
                "missing_relation_precision": missing_score.precision,
                "missing_relation_recall": missing_score.recall,
                "missing_relation_f1": missing_score.f1,
                "full_topology_precision": full_score.precision,
                "full_topology_recall": full_score.recall,
                "full_topology_f1": full_score.f1,
                "n_full_relations": len(full_truth),
                "n_visible_relations": len(masked.visible_relations),
                "n_missing_relations": len(masked.missing_relations),
                "n_collector_observations": len(case.relation_observations),
                "n_hypotheses": n_hypotheses,
                "n_added_relations": len(added_relations),
                "missing_relation_types": relation_type_counts(masked.missing_relations),
                "added_relation_types": relation_type_counts(added_relations),
            }
        )

    missing_micro_p, missing_micro_r, missing_micro_f1 = _micro_from_counts(
        missing_tp, missing_fp, missing_fn
    )
    full_micro_p, full_micro_r, full_micro_f1 = _micro_from_counts(full_tp, full_fp, full_fn)

    per_relation_type: dict[str, dict[str, float | int]] = {}
    for relation, counts in sorted(type_counts.items()):
        p, r, f1 = _micro_from_counts(counts["tp"], counts["fp"], counts["fn"])
        per_relation_type[relation] = {
            **counts,
            "precision": p,
            "recall": r,
            "f1": f1,
        }

    summary = {
        "macro_missing_relation_precision": _mean(rows, "missing_relation_precision"),
        "macro_missing_relation_recall": _mean(rows, "missing_relation_recall"),
        "macro_missing_relation_f1": _mean(rows, "missing_relation_f1"),
        "micro_missing_relation_precision": missing_micro_p,
        "micro_missing_relation_recall": missing_micro_r,
        "micro_missing_relation_f1": missing_micro_f1,
        "micro_missing_tp": missing_tp,
        "micro_missing_fp": missing_fp,
        "micro_missing_fn": missing_fn,
        "macro_full_topology_f1": _mean(rows, "full_topology_f1"),
        "micro_full_topology_precision": full_micro_p,
        "micro_full_topology_recall": full_micro_r,
        "micro_full_topology_f1": full_micro_f1,
        "mean_full_relations": _mean(rows, "n_full_relations"),
        "mean_visible_relations": _mean(rows, "n_visible_relations"),
        "mean_missing_relations": _mean(rows, "n_missing_relations"),
        "mean_collector_observations": _mean(rows, "n_collector_observations"),
        "mean_hypotheses": _mean(rows, "n_hypotheses"),
        "mean_added_relations": _mean(rows, "n_added_relations"),
    }

    result = {
        "track": "missing_topology_relation_recovery",
        "variant": variant,
        "n": len(rows),
        "topology_missing_ratio": topology_missing_ratio,
        "seed": seed,
        "relation_threshold": relation_threshold,
        "reference_protocol": reference_protocol,
        "protocol": {
            "problem": "collector_data_available_but_topology_relation_missing",
            "collector_observations_modified": False,
            "masked_object": "topology_relation",
            "masked_relation_marker_visible_to_model": False,
            "node_or_endpoint_removal": False,
            "model_inputs": ["incomplete_topology", "collector_observations"],
            "causal_gold_usage": "none",
            "primary_metric": "recovery_of_removed_topology_relations",
            "secondary_metric": "full_topology_similarity_after_recovery",
        },
        "summary": summary,
        "per_relation_type": per_relation_type,
        "rows": rows,
    }

    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
