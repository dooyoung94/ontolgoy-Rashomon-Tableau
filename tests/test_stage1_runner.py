from __future__ import annotations

import json

import pytest

from openrca_mr.abduction import (
    AbductiveCausalRelationGenerator,
    AbductiveRelationGenerator,
)
from openrca_mr.models import (
    CausalEdge,
    Evidence,
    RcaCase,
    RelationObservation,
    REL_CALLS,
    REL_CAUSAL,
    REL_DEPLOYED_ON,
)
from openrca_mr.openrca2 import dump_normalized_cases
from openrca_mr.pipeline import IncidentCausalRCA, MissingRelationRCA
from openrca_mr.stage1_eval import drop_relation_observations, run_stage1_evaluation


def _case(case_id: str = "s1") -> RcaCase:
    observations = [
        RelationObservation(
            "o1",
            "service:frontend",
            "service:orders",
            "trace_parent_child",
            0.98,
            "frontend parent span has orders child span",
        ),
        RelationObservation(
            "o2",
            "service:orders",
            "pod:orders-1",
            "service_pod_cooccurrence",
            0.98,
            "orders telemetry emitted from orders-1",
        ),
    ]
    structural = [
        CausalEdge("service:frontend", REL_CALLS, "service:orders"),
        CausalEdge("service:orders", REL_DEPLOYED_ON, "pod:orders-1"),
    ]
    return RcaCase(
        case_id=case_id,
        symptom_nodes=["frontend"],
        known_edges=[CausalEdge("orders", "dependency_propagates_to", "frontend")],
        evidence=[
            Evidence("e1", "orders", "metric", "latency", 0.9, 1.0, "orders slow"),
            Evidence("e2", "frontend", "trace", "latency", 0.9, 2.0, "frontend slow"),
        ],
        gold_root_causes=["orders"],
        gold_edges=[CausalEdge("orders", REL_CAUSAL, "frontend")],
        structural_relations=structural,
        relation_observations=observations,
    )


def test_stage2_new_names_and_legacy_aliases_are_identical():
    assert MissingRelationRCA is IncidentCausalRCA
    assert AbductiveRelationGenerator is AbductiveCausalRelationGenerator


def test_incident_causal_pipeline_validates_threshold_and_root_count():
    with pytest.raises(ValueError):
        IncidentCausalRCA(edge_threshold=-0.1)
    with pytest.raises(ValueError):
        IncidentCausalRCA(edge_threshold=1.1)
    with pytest.raises(ValueError):
        IncidentCausalRCA(max_root_causes=0)


def test_observation_drop_is_stable_and_nested():
    case = _case("stable")
    keep0 = drop_relation_observations(case, 0.0, seed=42)
    keep50 = drop_relation_observations(case, 0.5, seed=42)
    keep100 = drop_relation_observations(case, 1.0, seed=42)
    keep50_again = drop_relation_observations(case, 0.5, seed=42)
    assert keep0 == case.relation_observations
    assert keep50 == keep50_again
    assert set(x.observation_id for x in keep100) <= set(x.observation_id for x in keep50)
    assert len(keep50) == 1
    assert keep100 == []


def test_stage1_runner_uses_observations_only_and_scores_typed_triples(tmp_path):
    data = tmp_path / "cases.jsonl"
    out = tmp_path / "result.json"
    dump_normalized_cases([_case()], data)

    result = run_stage1_evaluation(
        data=str(data),
        out=str(out),
        variant="observation_abduction",
        observation_drop_ratio=0.0,
        seed=42,
    )
    assert result["track"] == "stage1_structural_relation_recovery"
    assert result["reference_protocol"] == "same_artifact_full_observation_reference_diagnostic"
    assert result["protocol"]["all_pairs_generation"] is False
    assert result["summary"]["macro_structural_precision"] == 1.0
    assert result["summary"]["macro_structural_recall"] == 1.0
    assert result["summary"]["macro_structural_f1"] == 1.0
    assert result["summary"]["micro_structural_f1"] == 1.0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["rows"][0]["n_candidates"] == 2
    assert saved["rows"][0]["n_selected_relations"] == 2


def test_stage1_runner_joins_independent_reference_by_case_id(tmp_path):
    data = tmp_path / "input.jsonl"
    reference = tmp_path / "reference.jsonl"
    out = tmp_path / "independent.json"
    dump_normalized_cases([_case("case-A")], data)
    dump_normalized_cases([_case("case-B"), _case("case-A")], reference)

    result = run_stage1_evaluation(
        data=str(data),
        reference_data=str(reference),
        out=str(out),
        variant="observation_abduction",
    )
    assert result["n"] == 1
    assert result["reference_protocol"] == "independent_reference_artifact"
    assert result["rows"][0]["case_id"] == "case-A"
    assert result["summary"]["micro_structural_f1"] == 1.0


def test_stage1_runner_rejects_missing_reference_case_ids(tmp_path):
    data = tmp_path / "input.jsonl"
    reference = tmp_path / "reference.jsonl"
    out = tmp_path / "out.json"
    dump_normalized_cases([_case("case-A")], data)
    dump_normalized_cases([_case("case-B")], reference)

    with pytest.raises(ValueError, match="missing input case_id"):
        run_stage1_evaluation(
            data=str(data),
            reference_data=str(reference),
            out=str(out),
            variant="observation_abduction",
        )


def test_stage1_runner_detects_cross_window_protocol(tmp_path):
    data = tmp_path / "cross-window.jsonl"
    out = tmp_path / "out.json"
    case = _case("case-A")
    case.metadata["structural_reference_protocol"] = (
        "normal_window_reference_vs_abnormal_window_observations"
    )
    dump_normalized_cases([case], data)

    result = run_stage1_evaluation(
        data=str(data),
        out=str(out),
        variant="observation_abduction",
    )
    assert result["reference_protocol"] == (
        "normal_window_reference_vs_abnormal_window_observations"
    )
    assert "cross-window structural consistency" in result["protocol"]["warning"].lower()
