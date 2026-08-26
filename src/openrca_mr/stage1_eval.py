from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from .models import RcaCase, RelationObservation, STRUCTURAL_RELATION_TYPES
from .openrca2 import load_normalized_cases
from .psl import PslStructuralInference
from .semantic import DebertaStructuralRelationScorer
from .structural import (
    StructuralRelationRecovery,
    relation_type_counts,
    structural_relation_metrics,
)


VARIANTS = {
    "observation_abduction": (False, False),
    "observation_abduction_deberta": (True, False),
    "observation_abduction_psl": (False, True),
    "observation_abduction_deberta_psl": (True, True),
}


def _stable_rank(case_id: str, seed: int, observation: RelationObservation) -> bytes:
    payload = (
        f"{seed}:{case_id}:{observation.observation_id}:"
        f"{observation.source}|{observation.evidence_kind}|{observation.target}"
    )
    return hashlib.sha256(payload.encode("utf-8")).digest()


def drop_relation_observations(
    case: RcaCase,
    ratio: float,
    seed: int,
) -> list[RelationObservation]:
    """Deterministically remove model-visible Stage-1 observations for stress tests."""
    if not 0.0 <= ratio <= 1.0:
        raise ValueError("observation drop ratio must be in [0, 1]")
    ordered = sorted(
        case.relation_observations,
        key=lambda item: _stable_rank(case.case_id, seed, item),
    )
    n_drop = round(len(ordered) * ratio)
    dropped = {item.observation_id for item in ordered[:n_drop]}
    return [
        item
        for item in case.relation_observations
        if item.observation_id not in dropped
    ]


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
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return precision, recall, f1


def _infer_reference_protocol(cases: list[RcaCase], explicit_reference: bool) -> str:
    if explicit_reference:
        return "independent_reference_artifact"
    protocols = {
        str(case.metadata.get("structural_reference_protocol", ""))
        for case in cases
        if case.metadata.get("structural_reference_protocol")
    }
    if protocols == {"normal_window_reference_vs_abnormal_window_observations"}:
        return "normal_window_reference_vs_abnormal_window_observations"
    return "same_artifact_full_observation_reference_diagnostic"


def run_stage1_evaluation(
    data: str,
    out: str,
    variant: str,
    reference_data: str | None = None,
    observation_drop_ratio: float = 0.0,
    seed: int = 42,
    relation_threshold: float = 0.5,
    limit: int = 0,
) -> dict:
    """Evaluate Stage-1 structural recovery without row-order or gold leakage.

    Preferred OpenRCA protocol:
      * ``structural_relations`` = normal-window telemetry structural reference.
      * ``relation_observations`` = abnormal/incident-window model input.

    This is a cross-window consistency evaluation, not a manually annotated
    structural ground-truth benchmark. An explicit ``reference_data`` artifact
    may be supplied when an independent topology/CMDB reference is available.
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    if not 0.0 <= relation_threshold <= 1.0:
        raise ValueError("relation_threshold must be in [0, 1]")
    if not 0.0 <= observation_drop_ratio <= 1.0:
        raise ValueError("observation_drop_ratio must be in [0, 1]")

    use_deberta, use_psl = VARIANTS[variant]
    cases = load_normalized_cases(data)
    _unique_case_map(cases, "input data")
    if limit:
        cases = cases[:limit]

    if reference_data:
        reference_cases = load_normalized_cases(reference_data)
        reference_map = _unique_case_map(reference_cases, "reference data")
    else:
        reference_cases = cases
        reference_map = _unique_case_map(reference_cases, "embedded reference")

    missing_reference = [case.case_id for case in cases if case.case_id not in reference_map]
    if missing_reference:
        raise ValueError(
            "reference data is missing input case_id values: "
            + ", ".join(sorted(missing_reference))
        )

    reference_protocol = _infer_reference_protocol(cases, bool(reference_data))

    semantic = DebertaStructuralRelationScorer() if use_deberta else None
    logic = PslStructuralInference() if use_psl else None
    recovery = StructuralRelationRecovery(
        semantic_scorer=semantic,
        global_inference=logic,
        relation_threshold=relation_threshold,
    )

    rows: list[dict] = []
    total_tp = total_fp = total_fn = 0
    type_counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for case in cases:
        truth = list(reference_map[case.case_id].structural_relations)
        observations = drop_relation_observations(case, observation_drop_ratio, seed)
        recovered = recovery.run(observations)
        score = structural_relation_metrics(recovered.relations, truth)

        pred_keys = _typed_keys(recovered.relations)
        gold_keys = _typed_keys(truth)
        tp_keys = pred_keys & gold_keys
        fp_keys = pred_keys - gold_keys
        fn_keys = gold_keys - pred_keys
        total_tp += len(tp_keys)
        total_fp += len(fp_keys)
        total_fn += len(fn_keys)
        for key in tp_keys:
            type_counts[key[1]]["tp"] += 1
        for key in fp_keys:
            type_counts[key[1]]["fp"] += 1
        for key in fn_keys:
            type_counts[key[1]]["fn"] += 1

        rows.append(
            {
                "case_id": case.case_id,
                "structural_precision": score.precision,
                "structural_recall": score.recall,
                "structural_f1": score.f1,
                "n_observations_full": len(case.relation_observations),
                "n_observations_visible": len(observations),
                "n_candidates": len(recovered.hypotheses),
                "n_selected_relations": len(recovered.relations),
                "n_reference_relations": len(truth),
                "tp": len(tp_keys),
                "fp": len(fp_keys),
                "fn": len(fn_keys),
                "selected_relation_types": relation_type_counts(recovered.relations),
                "reference_relation_types": relation_type_counts(truth),
            }
        )

    micro_p, micro_r, micro_f1 = _micro_from_counts(total_tp, total_fp, total_fn)
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
        "macro_structural_precision": _mean(rows, "structural_precision"),
        "macro_structural_recall": _mean(rows, "structural_recall"),
        "macro_structural_f1": _mean(rows, "structural_f1"),
        "micro_structural_precision": micro_p,
        "micro_structural_recall": micro_r,
        "micro_structural_f1": micro_f1,
        "micro_tp": total_tp,
        "micro_fp": total_fp,
        "micro_fn": total_fn,
        "mean_observations_full": _mean(rows, "n_observations_full"),
        "mean_observations_visible": _mean(rows, "n_observations_visible"),
        "mean_candidates": _mean(rows, "n_candidates"),
        "mean_selected_relations": _mean(rows, "n_selected_relations"),
        "mean_reference_relations": _mean(rows, "n_reference_relations"),
    }

    if reference_protocol == "normal_window_reference_vs_abnormal_window_observations":
        warning = (
            "Normal-window telemetry is an operational structural reference, "
            "not manually annotated structural ground truth. Report these values "
            "as cross-window structural consistency."
        )
    elif reference_protocol == "independent_reference_artifact":
        warning = (
            "Reference quality depends on the supplied artifact; verify that it is "
            "independent of model-visible relation observations."
        )
    else:
        warning = (
            "Same-artifact reference mode is a controlled robustness diagnostic, "
            "not independent structural ground truth."
        )

    result = {
        "track": "stage1_structural_relation_recovery",
        "variant": variant,
        "n": len(rows),
        "observation_drop_ratio": observation_drop_ratio,
        "seed": seed,
        "relation_threshold": relation_threshold,
        "reference_protocol": reference_protocol,
        "protocol": {
            "model_input": "relation_observations_only",
            "candidate_policy": "telemetry_grounded_endpoint_pairs_plus_ontology_type_constraints",
            "all_pairs_generation": False,
            "causal_gold_usage": "none",
            "reference_usage": "evaluation_only",
            "drop_unit": "relation_observation_not_relation_label",
            "warning": warning,
        },
        "summary": summary,
        "per_relation_type": per_relation_type,
        "rows": rows,
    }

    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
