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
from openrca_mr.stage1_eval import run_stage1_evaluation
from openrca_mr.topology_recovery import mask_topology_relations


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


def test_stage2_legacy_aliases_remain_compatible():
    assert MissingRelationRCA is IncidentCausalRCA
    assert AbductiveRelationGenerator is AbductiveCausalRelationGenerator


def test_incident_causal_pipeline_validates_threshold_and_root_count():
    with pytest.raises(ValueError):
        IncidentCausalRCA(edge_threshold=-0.1)
    with pytest.raises(ValueError):
        IncidentCausalRCA(edge_threshold=1.1)
    with pytest.raises(ValueError):
        IncidentCausalRCA(max_root_causes=0)


def test_topology_mask_removes_relations_only_and_is_stable():
    case = _case("stable")
    masked_a = mask_topology_relations(case.case_id, case.structural_relations, 0.5, seed=42)
    masked_b = mask_topology_relations(case.case_id, case.structural_relations, 0.5, seed=42)

    assert masked_a == masked_b
    assert len(masked_a.visible_relations) == 1
    assert len(masked_a.missing_relations) == 1
    assert set(masked_a.visible_relations).isdisjoint(set(masked_a.missing_relations))
    assert set(masked_a.visible_relations + masked_a.missing_relations) == set(case.structural_relations)
    # 수집 정보는 mask 함수의 입력조차 아니므로 삭제될 수 없다.
    assert len(case.relation_observations) == 2


def test_topology_mask_is_nested_across_missing_ratios():
    case = _case("nested")
    m0 = mask_topology_relations(case.case_id, case.structural_relations, 0.0, seed=42)
    m50 = mask_topology_relations(case.case_id, case.structural_relations, 0.5, seed=42)
    m100 = mask_topology_relations(case.case_id, case.structural_relations, 1.0, seed=42)

    assert m0.missing_relations == []
    assert set(m50.missing_relations) <= set(m100.missing_relations)
    assert m100.visible_relations == []


def test_s0_keeps_incomplete_topology_without_recovery(tmp_path):
    data = tmp_path / "cases.jsonl"
    out = tmp_path / "s0.json"
    dump_normalized_cases([_case()], data)

    result = run_stage1_evaluation(
        data=str(data),
        out=str(out),
        variant="topology_only",
        topology_missing_ratio=0.5,
        seed=42,
    )

    assert result["track"] == "missing_topology_relation_recovery"
    assert result["protocol"]["collector_observations_modified"] is False
    assert result["protocol"]["masked_object"] == "topology_relation"
    assert result["summary"]["micro_missing_relation_recall"] == 0.0
    assert result["rows"][0]["n_visible_relations"] == 1
    assert result["rows"][0]["n_missing_relations"] == 1
    assert result["rows"][0]["n_added_relations"] == 0


def test_s1_recovers_relation_missing_from_topology_using_unchanged_collector_data(tmp_path):
    data = tmp_path / "cases.jsonl"
    out = tmp_path / "s1.json"
    dump_normalized_cases([_case()], data)

    result = run_stage1_evaluation(
        data=str(data),
        out=str(out),
        variant="abduction",
        topology_missing_ratio=0.5,
        seed=42,
    )

    assert result["summary"]["micro_missing_relation_precision"] == 1.0
    assert result["summary"]["micro_missing_relation_recall"] == 1.0
    assert result["summary"]["micro_missing_relation_f1"] == 1.0
    assert result["summary"]["micro_full_topology_f1"] == 1.0
    assert result["rows"][0]["n_collector_observations"] == 2
    assert result["rows"][0]["n_added_relations"] == 1

    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["topology_missing_ratio"] == 0.5
    assert saved["protocol"]["masked_relation_marker_visible_to_model"] is False


def test_runner_joins_independent_topology_reference_by_case_id(tmp_path):
    data = tmp_path / "input.jsonl"
    reference = tmp_path / "reference.jsonl"
    out = tmp_path / "independent.json"
    dump_normalized_cases([_case("case-A")], data)
    dump_normalized_cases([_case("case-B"), _case("case-A")], reference)

    result = run_stage1_evaluation(
        data=str(data),
        reference_data=str(reference),
        out=str(out),
        variant="abduction",
        topology_missing_ratio=0.5,
    )

    assert result["n"] == 1
    assert result["reference_protocol"] == "independent_topology_reference"
    assert result["rows"][0]["case_id"] == "case-A"


def test_runner_rejects_missing_reference_case_ids(tmp_path):
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
            variant="abduction",
            topology_missing_ratio=0.5,
        )
