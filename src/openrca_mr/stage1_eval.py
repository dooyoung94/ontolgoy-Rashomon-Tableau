from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .models import RcaCase, StructuralHypothesis, STRUCTURAL_RELATION_TYPES
from .openrca2 import load_normalized_cases
from .psl import PslStructuralInference, visible_functional_conflicts
from .reference_topology import PRIMARY_REFERENCE_RELATION_TYPES
from .research_protocol import audit_reference_protocol, topology_group_id
from .semantic import DebertaStructuralRelationScorer
from .structural import relation_type_counts, structural_relation_metrics
from .topology_recovery import (
    mask_topology_relations_by_group,
    recover_missing_topology_relations,
)


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
STAGE1_PROTOCOL_VERSION = "stage1-primary-relation-recovery-v1"


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


def _typed_keys(
    relations,
    relation_types: frozenset[str] | set[str] = STRUCTURAL_RELATION_TYPES,
) -> set[tuple[str, str, str]]:
    return {
        edge.key()
        for edge in relations
        if edge.relation in relation_types
    }


def _semantic_adjusted_score(hypothesis: StructuralHypothesis) -> float:
    if hypothesis.semantic_support is None:
        return max(0.0, min(1.0, hypothesis.abductive_support))
    contradiction = hypothesis.semantic_contradiction or 0.0
    margin = hypothesis.semantic_support - contradiction
    return max(0.0, min(1.0, hypothesis.abductive_support + 0.25 * margin))


def _hypothesis_diagnostics(
    hypotheses: list[StructuralHypothesis],
    visible_relations,
    *,
    relation_threshold: float,
    use_deberta: bool,
    use_psl: bool,
) -> dict[str, float | int | None]:
    by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    semantic_shift = 0.0
    semantic_flips = 0
    psl_shift = 0.0
    psl_flips = 0

    for hypothesis in hypotheses:
        by_pair[(hypothesis.edge.source, hypothesis.edge.target)].add(
            hypothesis.edge.relation
        )
        abductive_score = max(0.0, min(1.0, hypothesis.abductive_support))
        pre_psl_score = _semantic_adjusted_score(hypothesis)
        if use_deberta:
            semantic_shift += abs(pre_psl_score - abductive_score)
            semantic_flips += (abductive_score >= relation_threshold) != (
                pre_psl_score >= relation_threshold
            )
        if use_psl:
            final_score = hypothesis.final_score
            psl_shift += abs(final_score - pre_psl_score)
            psl_flips += (pre_psl_score >= relation_threshold) != (
                final_score >= relation_threshold
            )

    n = len(hypotheses)
    return {
        "n_semantic_decision_flips": semantic_flips,
        "semantic_decision_flip_rate": semantic_flips / n if use_deberta and n else None,
        "mean_abs_semantic_score_shift": semantic_shift / n if use_deberta and n else None,
        "n_psl_decision_flips": psl_flips,
        "psl_decision_flip_rate": psl_flips / n if use_psl and n else None,
        "mean_abs_psl_score_shift": psl_shift / n if use_psl and n else None,
        "n_competing_endpoint_pairs": sum(len(relations) > 1 for relations in by_pair.values()),
        "n_visible_functional_conflicts": len(
            visible_functional_conflicts(list(visible_relations), hypotheses)
        ),
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
    allow_derived_reference: bool = False,
    evaluation_relation_types: frozenset[str] | set[str] | None = None,
    semantic_scorer=None,
    global_inference=None,
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

    evaluation_relation_types = frozenset(
        PRIMARY_REFERENCE_RELATION_TYPES
        if evaluation_relation_types is None
        else evaluation_relation_types
    )
    unknown_relation_types = evaluation_relation_types - STRUCTURAL_RELATION_TYPES
    if unknown_relation_types:
        raise ValueError(
            f"unknown evaluation relation types: {sorted(unknown_relation_types)}"
        )
    if not evaluation_relation_types:
        raise ValueError("evaluation_relation_types must not be empty")

    do_recovery, use_deberta, use_psl = VARIANTS[variant]
    cases = load_normalized_cases(data)
    _unique_case_map(cases, "input data")
    if limit:
        cases = cases[:limit]

    if reference_data:
        reference_cases = load_normalized_cases(reference_data)
        reference_map = _unique_case_map(reference_cases, "reference data")
    else:
        reference_map = _unique_case_map(cases, "embedded complete topology")

    missing_case_ids = [case.case_id for case in cases if case.case_id not in reference_map]
    if missing_case_ids:
        raise ValueError(
            "reference data is missing input case_id values: "
            + ", ".join(sorted(missing_case_ids))
        )

    selected_reference_cases = [reference_map[case.case_id] for case in cases]
    reference_audit = audit_reference_protocol(
        cases,
        selected_reference_cases,
        data=data,
        reference_data=reference_data,
        allow_derived_reference=allow_derived_reference,
    )
    reference_protocol = (
        "independent_topology_reference"
        if reference_audit.independent_reference
        else "derived_reference_diagnostic_only"
    )

    full_relations_by_case = {
        case.case_id: list(reference_map[case.case_id].structural_relations)
        for case in cases
    }
    case_groups = {case.case_id: topology_group_id(case) for case in cases}
    masks = mask_topology_relations_by_group(
        full_relations_by_case,
        case_groups,
        topology_missing_ratio,
        seed,
        eligible_relation_types=evaluation_relation_types,
    )

    semantic = None
    if use_deberta:
        semantic = (
            semantic_scorer
            if semantic_scorer is not None
            else DebertaStructuralRelationScorer()
        )
    logic = None
    if use_psl:
        logic = (
            global_inference
            if global_inference is not None
            else PslStructuralInference()
        )

    rows: list[dict] = []
    missing_tp = missing_fp = missing_fn = 0
    candidate_gold_hits = candidate_gold_total = 0
    full_tp = full_fp = full_fn = 0
    type_counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    diagnostic_totals = defaultdict(float)
    diagnostic_denominators = defaultdict(int)

    for case in cases:
        full_reference = list(reference_map[case.case_id].structural_relations)
        full_truth = [
            edge for edge in full_reference if edge.relation in evaluation_relation_types
        ]
        masked = masks[case.case_id]

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
            evaluated_hypotheses = [
                hypothesis
                for hypothesis in recovered.hypotheses
                if hypothesis.edge.relation in evaluation_relation_types
            ]
            n_hypotheses = len(evaluated_hypotheses)
            n_all_hypotheses = len(recovered.hypotheses)
            hypothesis_keys = _typed_keys(
                (h.edge for h in evaluated_hypotheses), evaluation_relation_types
            )
            diagnostics = _hypothesis_diagnostics(
                evaluated_hypotheses,
                masked.visible_relations,
                relation_threshold=relation_threshold,
                use_deberta=use_deberta,
                use_psl=use_psl,
            )
        else:
            added_relations = []
            final_topology = list(masked.visible_relations)
            n_hypotheses = 0
            n_all_hypotheses = 0
            hypothesis_keys = set()
            diagnostics = _hypothesis_diagnostics(
                [],
                masked.visible_relations,
                relation_threshold=relation_threshold,
                use_deberta=use_deberta,
                use_psl=use_psl,
            )

        # 주 지표: 실제로 토폴로지에서 제거한 관계를 얼마나 되찾았는가.
        evaluated_added = [
            edge for edge in added_relations if edge.relation in evaluation_relation_types
        ]
        missing_score = structural_relation_metrics(
            evaluated_added, masked.missing_relations
        )
        pred_missing = _typed_keys(evaluated_added, evaluation_relation_types)
        gold_missing = _typed_keys(masked.missing_relations, evaluation_relation_types)
        tp_keys = pred_missing & gold_missing
        fp_keys = pred_missing - gold_missing
        fn_keys = gold_missing - pred_missing
        missing_tp += len(tp_keys)
        missing_fp += len(fp_keys)
        missing_fn += len(fn_keys)
        if do_recovery:
            candidate_gold_hits += len(hypothesis_keys & gold_missing)
            candidate_gold_total += len(gold_missing)

        for key in tp_keys:
            type_counts[key[1]]["tp"] += 1
        for key in fp_keys:
            type_counts[key[1]]["fp"] += 1
        for key in fn_keys:
            type_counts[key[1]]["fn"] += 1

        # 보조 지표: 복원 후 전체 토폴로지가 원래 토폴로지와 얼마나 같은가.
        evaluated_final = [
            edge for edge in final_topology if edge.relation in evaluation_relation_types
        ]
        full_score = structural_relation_metrics(evaluated_final, full_truth)
        pred_full = _typed_keys(evaluated_final, evaluation_relation_types)
        gold_full = _typed_keys(full_truth, evaluation_relation_types)
        full_tp += len(pred_full & gold_full)
        full_fp += len(pred_full - gold_full)
        full_fn += len(gold_full - pred_full)

        row = {
            "case_id": case.case_id,
            "topology_group": case_groups[case.case_id],
            # Empty-denominator cases are retained for coverage accounting,
            # but must not inflate macro recovery scores to 1.0.
            "missing_relation_precision": (
                missing_score.precision if gold_missing else None
            ),
            "missing_relation_recall": missing_score.recall if gold_missing else None,
            "missing_relation_f1": missing_score.f1 if gold_missing else None,
            "candidate_recall_ceiling": (
                len(hypothesis_keys & gold_missing) / len(gold_missing)
                if do_recovery and gold_missing
                else None
            ),
            "full_topology_precision": full_score.precision,
            "full_topology_recall": full_score.recall,
            "full_topology_f1": full_score.f1,
            "n_full_relations": len(full_truth),
            "n_visible_relations": sum(
                edge.relation in evaluation_relation_types
                for edge in masked.visible_relations
            ),
            "n_auxiliary_visible_relations": sum(
                edge.relation not in evaluation_relation_types
                for edge in masked.visible_relations
            ),
            "n_missing_relations": len(masked.missing_relations),
            "n_collector_observations": len(case.relation_observations),
            "n_hypotheses": n_hypotheses,
            "n_auxiliary_hypotheses": n_all_hypotheses - n_hypotheses,
            "n_added_relations": len(evaluated_added),
            "missing_relation_types": relation_type_counts(masked.missing_relations),
            "added_relation_types": relation_type_counts(evaluated_added),
            **diagnostics,
        }
        rows.append(row)
        for key in (
            "n_semantic_decision_flips",
            "n_psl_decision_flips",
            "n_competing_endpoint_pairs",
            "n_visible_functional_conflicts",
        ):
            diagnostic_totals[key] += float(row[key])
        for key in ("mean_abs_semantic_score_shift", "mean_abs_psl_score_shift"):
            value = row[key]
            if isinstance(value, (int, float)):
                diagnostic_totals[key] += float(value) * n_hypotheses
                diagnostic_denominators[key] += n_hypotheses

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

    total_full_relations = sum(row["n_full_relations"] for row in rows)
    total_missing_relations = sum(row["n_missing_relations"] for row in rows)
    if topology_missing_ratio > 0.0 and total_missing_relations == 0:
        raise ValueError(
            "the requested topology_missing_ratio removed zero relations; "
            "the experiment has no recovery denominator"
        )

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
        "false_edge_insertion_rate": (
            missing_fp / (missing_tp + missing_fp)
            if missing_tp + missing_fp
            else 0.0
        ),
        "candidate_recall_ceiling": (
            candidate_gold_hits / candidate_gold_total
            if candidate_gold_total
            else None
        ),
        "n_evaluable_missing_cases": sum(
            row["n_missing_relations"] > 0 for row in rows
        ),
        "requested_missing_ratio": topology_missing_ratio,
        "realized_missing_ratio": (
            total_missing_relations / total_full_relations
            if total_full_relations
            else None
        ),
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
        "n_semantic_decision_flips": int(
            diagnostic_totals["n_semantic_decision_flips"]
        ),
        "semantic_decision_flip_rate": (
            diagnostic_totals["n_semantic_decision_flips"]
            / sum(row["n_hypotheses"] for row in rows)
            if use_deberta and sum(row["n_hypotheses"] for row in rows)
            else None
        ),
        "mean_abs_semantic_score_shift": (
            diagnostic_totals["mean_abs_semantic_score_shift"]
            / diagnostic_denominators["mean_abs_semantic_score_shift"]
            if diagnostic_denominators["mean_abs_semantic_score_shift"]
            else None
        ),
        "n_psl_decision_flips": int(diagnostic_totals["n_psl_decision_flips"]),
        "psl_decision_flip_rate": (
            diagnostic_totals["n_psl_decision_flips"]
            / sum(row["n_hypotheses"] for row in rows)
            if use_psl and sum(row["n_hypotheses"] for row in rows)
            else None
        ),
        "mean_abs_psl_score_shift": (
            diagnostic_totals["mean_abs_psl_score_shift"]
            / diagnostic_denominators["mean_abs_psl_score_shift"]
            if diagnostic_denominators["mean_abs_psl_score_shift"]
            else None
        ),
        "n_competing_endpoint_pairs": int(
            diagnostic_totals["n_competing_endpoint_pairs"]
        ),
        "n_visible_functional_conflicts": int(
            diagnostic_totals["n_visible_functional_conflicts"]
        ),
    }

    result = {
        "protocol_version": STAGE1_PROTOCOL_VERSION,
        "track": "missing_topology_relation_recovery",
        "variant": variant,
        "n": len(rows),
        "topology_missing_ratio": topology_missing_ratio,
        "seed": seed,
        "relation_threshold": relation_threshold,
        "reference_protocol": reference_protocol,
        "claim_scope": reference_audit.claim_scope,
        "reference_audit": reference_audit.to_dict(),
        "evaluation_relation_types": sorted(evaluation_relation_types),
        "method_components": {
            "deberta_enabled": use_deberta,
            "deberta_model": getattr(semantic, "model_name", None),
            "deberta_revision": getattr(semantic, "model_revision", None),
            "psl_enabled": use_psl,
            "psl_inference_class": type(logic).__name__ if logic is not None else None,
        },
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
            "masking_unit": "topology_group",
            "empty_missing_cases_in_macro": "excluded",
            "visible_topology_constraint_inference": use_psl,
            "auxiliary_relations_are_evaluation_targets": False,
        },
        "summary": summary,
        "per_relation_type": per_relation_type,
        "rows": rows,
    }

    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)
    return result
