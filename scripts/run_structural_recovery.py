from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from openrca_mr.models import RcaCase, RelationObservation
from openrca_mr.openrca2 import load_normalized_cases
from openrca_mr.psl import PslStructuralInference
from openrca_mr.semantic import DebertaStructuralRelationScorer
from openrca_mr.structural import (
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
    """Controlled observation-removal stress protocol.

    This intentionally removes evidence observations, not structural predicate
    labels. Endpoint pairs with no remaining observation become unknown rather
    than being invented by a global all-pairs generator. The protocol is useful
    for robustness analysis; a paper-level structural claim should prefer an
    independent reference artifact when available.
    """
    if not 0.0 <= ratio <= 1.0:
        raise ValueError("observation drop ratio must be in [0, 1]")
    ordered = sorted(
        case.relation_observations,
        key=lambda item: _stable_rank(case.case_id, seed, item),
    )
    n_drop = round(len(ordered) * ratio)
    dropped = {item.observation_id for item in ordered[:n_drop]}
    return [item for item in case.relation_observations if item.observation_id not in dropped]


def _mean(rows: list[dict], key: str) -> float | None:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return sum(values) / len(values) if values else None


def _reference_map(cases: list[RcaCase]) -> dict[str, list]:
    return {case.case_id: list(case.structural_relations) for case in cases}


def run(
    data: str,
    out: str,
    variant: str,
    reference_data: str | None = None,
    observation_drop_ratio: float = 0.0,
    seed: int = 42,
    relation_threshold: float = 0.5,
    limit: int = 0,
) -> dict:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    if not 0.0 <= relation_threshold <= 1.0:
        raise ValueError("relation_threshold must be in [0, 1]")

    use_deberta, use_psl = VARIANTS[variant]
    cases = load_normalized_cases(data)
    if limit:
        cases = cases[:limit]

    if reference_data:
        reference_cases = load_normalized_cases(reference_data)
        references = _reference_map(reference_cases)
        reference_protocol = "independent_reference_artifact"
    else:
        # This mode is explicitly diagnostic: the full-observation recovered
        # triples in the same normalized artifact are used as the reference for
        # controlled observation-drop robustness. It must not be described as
        # independent structural ground truth.
        references = _reference_map(cases)
        reference_protocol = "same_artifact_full_observation_reference_diagnostic"

    semantic = DebertaStructuralRelationScorer() if use_deberta else None
    logic = PslStructuralInference() if use_psl else None
    recovery = StructuralRelationRecovery(
        semantic_scorer=semantic,
        global_inference=logic,
        relation_threshold=relation_threshold,
    )

    rows: list[dict] = []
    for case in cases:
        truth = references.get(case.case_id)
        if truth is None:
            # Never align references by row order; case_id is the only accepted
            # join key to prevent accidental cross-case evaluation leakage.
            continue
        observations = drop_relation_observations(case, observation_drop_ratio, seed)
        result = recovery.run(observations)
        score = structural_relation_metrics(result.relations, truth)
        rows.append(
            {
                "case_id": case.case_id,
                "structural_precision": score.precision,
                "structural_recall": score.recall,
                "structural_f1": score.f1,
                "n_observations_full": len(case.relation_observations),
                "n_observations_visible": len(observations),
                "n_candidates": len(result.hypotheses),
                "n_selected_relations": len(result.relations),
                "n_reference_relations": len(truth),
                "selected_relation_types": relation_type_counts(result.relations),
                "reference_relation_types": relation_type_counts(truth),
            }
        )

    summary = {
        "structural_precision": _mean(rows, "structural_precision"),
        "structural_recall": _mean(rows, "structural_recall"),
        "structural_f1": _mean(rows, "structural_f1"),
        "mean_observations_full": _mean(rows, "n_observations_full"),
        "mean_observations_visible": _mean(rows, "n_observations_visible"),
        "mean_candidates": _mean(rows, "n_candidates"),
        "mean_selected_relations": _mean(rows, "n_selected_relations"),
        "mean_reference_relations": _mean(rows, "n_reference_relations"),
    }
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
            "warning": (
                "same-artifact reference mode is a controlled robustness diagnostic, "
                "not independent structural ground truth"
            ),
        },
        "summary": summary,
        "rows": rows,
    }

    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage-1 structural relation recovery evaluation for OpenRCA normalized cases"
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--reference-data")
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="observation_abduction")
    parser.add_argument("--observation-drop-ratio", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--relation-threshold", type=float, default=0.5)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    result = run(
        data=args.data,
        out=args.out,
        variant=args.variant,
        reference_data=args.reference_data,
        observation_drop_ratio=args.observation_drop_ratio,
        seed=args.seed,
        relation_threshold=args.relation_threshold,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
