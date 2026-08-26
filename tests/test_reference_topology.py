from __future__ import annotations

from dataclasses import replace

import pytest

from openrca_mr.models import (
    CausalEdge,
    RcaCase,
    RelationObservation,
    REL_CALLS,
    REL_USES_DATABASE,
)
from openrca_mr.openrca2 import dump_normalized_cases
from openrca_mr.reference_topology import (
    REFERENCE_SCHEMA_VERSION,
    ReferenceEntity,
    ReferenceProvenance,
    ReferenceRelation,
    ReferenceStatus,
    ReferenceTopology,
    dump_reference_topologies,
    load_evaluation_reference,
    load_reference_topologies,
    score_reference_relations,
)
from openrca_mr.reference_validation import validate_reference_topologies
from openrca_mr.stage1_eval import run_stage1_evaluation


def _provenance(**overrides) -> ReferenceProvenance:
    values = {
        "source_type": "git",
        "source": "checkout deployment repository",
        "version": "abc1234",
        "locator": "config/services.yaml#L10-L20",
        "independent_of_model_observations": True,
        "evaluator_only": True,
        "verification_level": "reviewed",
    }
    values.update(overrides)
    return ReferenceProvenance(**values)


def _topology() -> ReferenceTopology:
    provenance = _provenance()
    return ReferenceTopology(
        schema_version=REFERENCE_SCHEMA_VERSION,
        topology_id="checkout:abc1234:deploy-v7",
        system="checkout",
        version="deploy-v7",
        valid_from="2026-08-01T00:00:00+09:00",
        valid_to="2026-09-01T00:00:00+09:00",
        provenance=provenance,
        entities=(
            ReferenceEntity("service:frontend", "service"),
            ReferenceEntity("service:orders", "service"),
            ReferenceEntity("service:catalog", "service"),
            ReferenceEntity("database:orders", "database"),
        ),
        relations=(
            ReferenceRelation(
                "service:frontend",
                REL_CALLS,
                "service:orders",
                ReferenceStatus.VERIFIED_POSITIVE,
                provenance,
            ),
            ReferenceRelation(
                "service:frontend",
                REL_CALLS,
                "service:catalog",
                ReferenceStatus.VERIFIED_NEGATIVE,
                provenance,
            ),
            ReferenceRelation(
                "service:orders",
                REL_USES_DATABASE,
                "database:orders",
                ReferenceStatus.UNKNOWN,
                provenance,
            ),
        ),
    )


def _case(case_id: str = "incident-1") -> RcaCase:
    return RcaCase(
        case_id=case_id,
        symptom_nodes=[],
        known_edges=[],
        evidence=[],
        metadata={
            "system": "checkout",
            "topology_id": "checkout:abc1234:deploy-v7",
        },
        relation_observations=[
            RelationObservation(
                "o-positive",
                "service:frontend",
                "service:orders",
                "trace_parent_child",
                0.98,
                "frontend parent span has orders child span",
            ),
            RelationObservation(
                "o-unknown",
                "service:orders",
                "database:orders",
                "db_client_context",
                0.95,
                "orders span contains an orders database client attribute",
            ),
        ],
    )


def test_reference_topology_round_trip_and_validation(tmp_path):
    path = tmp_path / "reference.jsonl"
    dump_reference_topologies([_topology()], path)

    loaded = load_reference_topologies(path)
    report = validate_reference_topologies(loaded)

    assert loaded == [_topology()]
    assert report.valid is True
    assert report.errors == ()
    assert report.relation_status_counts == {
        "VERIFIED_POSITIVE": 1,
        "VERIFIED_NEGATIVE": 1,
        "UNKNOWN": 1,
    }


def test_validator_rejects_model_derived_reference_and_domain_range_violation():
    topology = _topology()
    bad_provenance = _provenance(source_type="telemetry_observation")
    bad_relation = replace(
        topology.relations[0],
        relation=REL_USES_DATABASE,
    )
    invalid = replace(
        topology,
        provenance=bad_provenance,
        relations=(bad_relation,) + topology.relations[1:],
    )

    report = validate_reference_topologies([invalid])
    codes = {issue.code for issue in report.errors}

    assert report.valid is False
    assert "MODEL_DERIVED_REFERENCE" in codes
    assert "DOMAIN_RANGE_VIOLATION" in codes


def test_validator_rejects_ambiguous_time_and_conflicting_relation_status():
    topology = _topology()
    conflict = replace(
        topology.relations[0], status=ReferenceStatus.VERIFIED_NEGATIVE
    )
    invalid = replace(
        topology,
        valid_from="2026-08-01T00:00:00",
        relations=topology.relations + (conflict,),
    )

    report = validate_reference_topologies([invalid])
    codes = {issue.code for issue in report.errors}

    assert "TIMEZONE_REQUIRED" in codes
    assert "RELATION_STATUS_CONFLICT" in codes


def test_unknown_prediction_is_not_counted_as_false_positive():
    topology = _topology()
    predicted = [
        CausalEdge("service:frontend", REL_CALLS, "service:orders"),
        CausalEdge("service:orders", REL_USES_DATABASE, "database:orders"),
        CausalEdge("service:orders", REL_CALLS, "service:unreviewed"),
        CausalEdge("service:frontend", REL_CALLS, "service:catalog"),
    ]
    truth = [CausalEdge("service:frontend", REL_CALLS, "service:orders")]

    score = score_reference_relations(
        predicted,
        truth,
        status_index=topology.status_index(),
    )

    assert score.tp == 1
    assert score.fp == 1
    assert score.unknown == 2
    assert score.fn == 0
    assert score.precision == 0.5


def test_reference_topology_binds_once_to_all_incidents_in_same_system(tmp_path):
    reference_path = tmp_path / "reference.jsonl"
    dump_reference_topologies([_topology()], reference_path)
    cases = [
        replace(_case("incident-a"), metadata={"system": "checkout"}),
        replace(_case("incident-b"), metadata={"system": "checkout"}),
    ]

    binding = load_evaluation_reference(cases, str(reference_path))

    assert binding.open_world is True
    assert binding.topology_id_by_case == {
        "incident-a": "checkout:abc1234:deploy-v7",
        "incident-b": "checkout:abc1234:deploy-v7",
    }
    assert binding.cases_by_id["incident-a"].structural_relations == (
        binding.cases_by_id["incident-b"].structural_relations
    )
    assert (
        binding.cases_by_id["incident-a"].metadata[
            "reference_topology_provenance"
        ]["binding_method"]
        == "unique_system_diagnostic_fallback"
    )


def test_primary_evaluation_rejects_system_only_reference_binding(tmp_path):
    data_path = tmp_path / "cases.jsonl"
    reference_path = tmp_path / "reference.jsonl"
    out_path = tmp_path / "result.json"
    case = replace(_case(), metadata={"system": "checkout"})
    dump_normalized_cases([case], data_path)
    dump_reference_topologies([_topology()], reference_path)

    with pytest.raises(ValueError, match="explicit topology_id binding"):
        run_stage1_evaluation(
            data=str(data_path),
            reference_data=str(reference_path),
            out=str(out_path),
            variant="abduction",
            topology_missing_ratio=1.0,
            seed=42,
        )


def test_stage1_contract_reference_excludes_unknown_addition_from_fp(tmp_path):
    data_path = tmp_path / "cases.jsonl"
    reference_path = tmp_path / "reference.jsonl"
    out_path = tmp_path / "result.json"
    dump_normalized_cases([_case()], data_path)
    dump_reference_topologies([_topology()], reference_path)

    result = run_stage1_evaluation(
        data=str(data_path),
        reference_data=str(reference_path),
        out=str(out_path),
        variant="abduction",
        topology_missing_ratio=1.0,
        seed=42,
    )

    assert result["claim_scope"] == "primary"
    assert result["reference_artifact_kind"] == "reference_topology_contract_v1"
    assert result["protocol"]["reference_world_assumption"] == "open_world_tristate"
    assert result["summary"]["micro_missing_tp"] == 1
    assert result["summary"]["micro_missing_fp"] == 0
    assert result["summary"]["micro_missing_unknown_predictions"] == 1
    assert result["summary"]["micro_missing_relation_precision"] == 1.0
