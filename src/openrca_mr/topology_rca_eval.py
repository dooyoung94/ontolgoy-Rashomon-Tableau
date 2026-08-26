from __future__ import annotations

import json
from pathlib import Path

from .abduction import AbductiveCausalRelationGenerator
from .metrics import (
    all_root_services_hit,
    any_root_service_hit,
    exact_root_set,
    node_metrics,
    process_path_reachability,
    root_hit_at_k,
    root_set_metrics,
    service_edge_metrics,
)
from .models import RcaCase, STRUCTURAL_RELATION_TYPES
from .openrca2 import load_normalized_cases
from .pipeline import IncidentCausalRCA
from .psl import PslGlobalInference, PslStructuralInference
from .reference_topology import PRIMARY_REFERENCE_RELATION_TYPES
from .research_protocol import audit_reference_protocol, topology_group_id
from .semantic import DebertaEvidenceScorer, DebertaStructuralRelationScorer
from .structural import propagation_service_edges, structural_relation_metrics
from .topology_recovery import (
    mask_topology_relations_by_group,
    recover_missing_topology_relations,
)


TOPOLOGY_VARIANTS = {
    "topology_only": (False, False, False),
    "abduction": (True, False, False),
    "abduction_deberta": (True, True, False),
    "abduction_psl": (True, False, True),
    "abduction_deberta_psl": (True, True, True),
}

RCA_VARIANTS = {
    "abduction": (False, False),
    "abduction_deberta": (True, False),
    "abduction_psl": (False, True),
    "full": (True, True),
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


def _case_with_topology(case: RcaCase, relations) -> RcaCase:
    """Build an RCA view whose dependency candidates come only from a topology."""
    return RcaCase(
        case_id=case.case_id,
        symptom_nodes=list(case.symptom_nodes),
        known_edges=propagation_service_edges(list(relations)),
        evidence=list(case.evidence),
        gold_root_causes=list(case.gold_root_causes),
        gold_edges=list(case.gold_edges),
        gold_paths=[list(path) for path in case.gold_paths],
        gold_alarm_nodes=list(case.gold_alarm_nodes),
        metadata=dict(case.metadata),
        structural_relations=list(relations),
        relation_observations=list(case.relation_observations),
    )


def _build_rca(variant: str, edge_threshold: float) -> IncidentCausalRCA:
    if variant not in RCA_VARIANTS:
        raise ValueError(f"unknown RCA variant: {variant}")
    use_deberta, use_psl = RCA_VARIANTS[variant]
    return IncidentCausalRCA(
        generator=AbductiveCausalRelationGenerator(max_candidates=None),
        semantic_scorer=DebertaEvidenceScorer() if use_deberta else None,
        global_inference=PslGlobalInference() if use_psl else None,
        edge_threshold=edge_threshold,
    )


def _score_rca(case: RcaCase, model: IncidentCausalRCA) -> dict:
    pred = model.run(case)
    edge = service_edge_metrics(pred.predicted_edges, case.gold_edges)
    node = node_metrics(
        pred.predicted_edges,
        case.gold_edges,
        predicted_roots=pred.predicted_root_causes,
        gold_roots=case.gold_root_causes,
    )
    root = root_set_metrics(pred.predicted_root_causes, case.gold_root_causes)
    path = process_path_reachability(
        pred.predicted_edges,
        pred.predicted_root_causes,
        case.gold_root_causes,
        case.gold_alarm_nodes or case.symptom_nodes,
    )
    return {
        "any_service_hit": any_root_service_hit(pred.predicted_root_causes, case.gold_root_causes),
        "all_service_hit": all_root_services_hit(pred.predicted_root_causes, case.gold_root_causes),
        "root_precision": root.precision,
        "root_recall": root.recall,
        "root_f1": root.f1,
        "root_exact": exact_root_set(pred.predicted_root_causes, case.gold_root_causes),
        "root_hit_at_1": root_hit_at_k(pred.predicted_root_causes, case.gold_root_causes, 1),
        "root_hit_at_3": root_hit_at_k(pred.predicted_root_causes, case.gold_root_causes, 3),
        "path_reachability": path,
        "node_precision": node.precision,
        "node_recall": node.recall,
        "node_f1": node.f1,
        "edge_precision": edge.precision,
        "edge_recall": edge.recall,
        "edge_f1": edge.f1,
        "n_predicted_roots": len(pred.predicted_root_causes),
        "n_predicted_edges": len(pred.predicted_edges),
    }


def _summarize_condition(rows: list[dict], prefix: str) -> dict:
    keys = (
        "any_service_hit",
        "all_service_hit",
        "root_precision",
        "root_recall",
        "root_f1",
        "root_exact",
        "root_hit_at_1",
        "root_hit_at_3",
        "path_reachability",
        "node_precision",
        "node_recall",
        "node_f1",
        "edge_precision",
        "edge_recall",
        "edge_f1",
    )
    return {key: _mean(rows, f"{prefix}_{key}") for key in keys}


def run_topology_rca_evaluation(
    data: str,
    out: str,
    topology_variant: str = "abduction_deberta_psl",
    rca_variant: str = "abduction_psl",
    topology_missing_ratio: float = 0.4,
    seed: int = 42,
    relation_threshold: float = 0.5,
    rca_edge_threshold: float = 0.5,
    limit: int = 0,
    reference_data: str | None = None,
    allow_derived_reference: bool = False,
    evaluation_relation_types: frozenset[str] | set[str] | None = None,
) -> dict:
    """Jointly evaluate missing topology relation recovery and OpenRCA-style RCA.

    The same incident evidence and gold labels are used for all three RCA
    conditions. Only the topology supplied to the RCA engine changes:
      1) incomplete topology after relation removal
      2) recovered topology
      3) complete topology reference

    Removed topology relations and OpenRCA causal gold are never inputs to the
    recovery method or RCA model.
    """
    if topology_variant not in TOPOLOGY_VARIANTS:
        raise ValueError(f"unknown topology variant: {topology_variant}")
    if not 0.0 <= topology_missing_ratio <= 1.0:
        raise ValueError("topology_missing_ratio must be in [0, 1]")
    if not 0.0 <= relation_threshold <= 1.0:
        raise ValueError("relation_threshold must be in [0, 1]")
    if not 0.0 <= rca_edge_threshold <= 1.0:
        raise ValueError("rca_edge_threshold must be in [0, 1]")
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

    do_recovery, topology_deberta, topology_psl = TOPOLOGY_VARIANTS[topology_variant]
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

    topology_semantic = DebertaStructuralRelationScorer() if topology_deberta else None
    topology_logic = PslStructuralInference() if topology_psl else None
    rca_model = _build_rca(rca_variant, rca_edge_threshold)

    rows: list[dict] = []
    for case in cases:
        full_topology = full_relations_by_case[case.case_id]
        masked = masks[case.case_id]

        if do_recovery:
            recovery = recover_missing_topology_relations(
                visible_relations=masked.visible_relations,
                observations=list(case.relation_observations),
                semantic_scorer=topology_semantic,
                global_inference=topology_logic,
                relation_threshold=relation_threshold,
            )
            added = recovery.added_relations
            recovered_topology = recovery.recovered_topology
        else:
            added = []
            recovered_topology = list(masked.visible_relations)

        evaluated_added = [
            edge for edge in added if edge.relation in evaluation_relation_types
        ]
        evaluated_recovered = [
            edge
            for edge in recovered_topology
            if edge.relation in evaluation_relation_types
        ]
        evaluated_full = [
            edge for edge in full_topology if edge.relation in evaluation_relation_types
        ]
        missing_score = structural_relation_metrics(
            evaluated_added, masked.missing_relations
        )
        full_score = structural_relation_metrics(evaluated_recovered, evaluated_full)

        conditions = {
            "incomplete": masked.visible_relations,
            "recovered": recovered_topology,
            "complete": full_topology,
        }
        row = {
            "case_id": case.case_id,
            "topology_group": case_groups[case.case_id],
            "n_full_topology_relations": len(evaluated_full),
            "n_auxiliary_topology_relations": len(full_topology) - len(evaluated_full),
            "n_missing_topology_relations": len(masked.missing_relations),
            "n_added_topology_relations": len(evaluated_added),
            "missing_relation_precision": (
                missing_score.precision if masked.missing_relations else None
            ),
            "missing_relation_recall": (
                missing_score.recall if masked.missing_relations else None
            ),
            "missing_relation_f1": (
                missing_score.f1 if masked.missing_relations else None
            ),
            "recovered_full_topology_f1": full_score.f1,
        }
        for name, topology in conditions.items():
            scored = _score_rca(_case_with_topology(case, topology), rca_model)
            for key, value in scored.items():
                row[f"{name}_{key}"] = value

        for key in ("root_f1", "path_reachability", "node_f1", "edge_f1", "root_hit_at_1", "root_hit_at_3"):
            row[f"delta_recovered_vs_incomplete_{key}"] = (
                row[f"recovered_{key}"] - row[f"incomplete_{key}"]
            )
        rows.append(row)

    total_full_relations = sum(row["n_full_topology_relations"] for row in rows)
    total_missing_relations = sum(row["n_missing_topology_relations"] for row in rows)
    if topology_missing_ratio > 0.0 and total_missing_relations == 0:
        raise ValueError(
            "the requested topology_missing_ratio removed zero relations; "
            "the experiment has no recovery denominator"
        )

    incomplete = _summarize_condition(rows, "incomplete")
    recovered = _summarize_condition(rows, "recovered")
    complete = _summarize_condition(rows, "complete")
    delta_keys = (
        "root_f1",
        "path_reachability",
        "node_f1",
        "edge_f1",
        "root_hit_at_1",
        "root_hit_at_3",
    )

    result = {
        "track": "topology_recovery_plus_openrca2_rca",
        "n": len(rows),
        "topology_variant": topology_variant,
        "rca_variant": rca_variant,
        "topology_missing_ratio": topology_missing_ratio,
        "seed": seed,
        "claim_scope": reference_audit.claim_scope,
        "reference_audit": reference_audit.to_dict(),
        "evaluation_relation_types": sorted(evaluation_relation_types),
        "protocol": {
            "collector_observations_modified": False,
            "topology_nodes_removed": False,
            "only_topology_relations_removed": True,
            "removed_relations_visible_to_model": False,
            "rca_conditions": ["incomplete", "recovered", "complete"],
            "same_incident_evidence_across_conditions": True,
            "openrca_causal_gold_usage": "evaluation_only",
            "complete_topology_role": "controlled_upper_reference",
            "masking_unit": "topology_group",
            "empty_missing_cases_in_macro": "excluded",
            "visible_topology_constraint_inference": topology_psl,
            "auxiliary_relations_are_evaluation_targets": False,
        },
        "topology_summary": {
            "mean_missing_relations": _mean(rows, "n_missing_topology_relations"),
            "mean_added_relations": _mean(rows, "n_added_topology_relations"),
            "macro_missing_relation_precision": _mean(rows, "missing_relation_precision"),
            "macro_missing_relation_recall": _mean(rows, "missing_relation_recall"),
            "macro_missing_relation_f1": _mean(rows, "missing_relation_f1"),
            "macro_recovered_full_topology_f1": _mean(rows, "recovered_full_topology_f1"),
            "n_evaluable_missing_cases": sum(
                row["n_missing_topology_relations"] > 0 for row in rows
            ),
            "requested_missing_ratio": topology_missing_ratio,
            "realized_missing_ratio": (
                total_missing_relations / total_full_relations
                if total_full_relations
                else None
            ),
        },
        "rca_summary": {
            "incomplete": incomplete,
            "recovered": recovered,
            "complete": complete,
            "delta_recovered_vs_incomplete": {
                key: recovered[key] - incomplete[key] for key in delta_keys
            },
            "gap_recovered_to_complete": {
                key: complete[key] - recovered[key] for key in delta_keys
            },
        },
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
