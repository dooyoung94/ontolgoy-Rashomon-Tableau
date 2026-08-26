import pandas as pd

from openrca_mr.abduction import AbductiveRelationGenerator
from openrca_mr.masking import (
    mask_relation_types,
    mask_relations,
    mask_structural_relation_types,
)
from openrca_mr.metrics import (
    normalize_service,
    process_path_reachability,
    relation_classification_metrics,
    service_edge_metrics,
)
from openrca_mr.models import (
    CausalEdge,
    Evidence,
    Hypothesis,
    RcaCase,
    RelationObservation,
    REL_CALLS,
    REL_CAUSAL,
    REL_DEPLOYED_ON,
    REL_MASKED,
    REL_NON_CAUSAL,
    REL_RUNS_ON,
    REL_STRUCTURAL_MASKED,
    REL_USES_DATABASE,
)
from openrca_mr.openrca2 import dump_normalized_cases, load_normalized_cases
from openrca_mr.pipeline import MissingRelationRCA
from openrca_mr.psl import StructuralSoftLogicApproximation
from openrca_mr.semantic import DeterministicStructuralScorer
from openrca_mr.structural import (
    AbductiveStructuralRelationGenerator,
    StructuralRelationRecovery,
    collect_structural_observations,
    extract_structural_relations,
    propagation_service_edges,
    recover_structural_relations,
    structural_relation_metrics,
)


def make_case(case_id="c1"):
    return RcaCase(
        case_id=case_id,
        symptom_nodes=["ts-api"],
        known_edges=[
            CausalEdge("ts-db", "dependency_propagates_to", "ts-worker"),
            CausalEdge("ts-worker", "dependency_propagates_to", "ts-api"),
            CausalEdge("ts-other", "dependency_propagates_to", "ts-api"),
            CausalEdge("ts-cache", "dependency_propagates_to", "ts-other"),
        ],
        evidence=[
            Evidence("e1", "ts-db", "metric", "latency", 0.95, 1.0, "db latency high"),
            Evidence("e2", "ts-worker", "trace", "duration", 0.90, 2.0, "worker span slow"),
            Evidence("e3", "ts-api", "metric", "latency", 0.98, 3.0, "api latency high"),
            Evidence("e4", "ts-other", "metric", "cpu", 0.10, 2.0, "cpu normal"),
            Evidence("e5", "ts-cache", "metric", "cpu", 0.05, 1.0, "cache stable"),
        ],
        gold_root_causes=["ts-db"],
        gold_edges=[
            CausalEdge("ts-db", REL_CAUSAL, "ts-worker"),
            CausalEdge("ts-worker", REL_CAUSAL, "ts-api"),
        ],
        gold_alarm_nodes=["ts-api"],
        structural_relations=[
            CausalEdge("service:ts-api", REL_CALLS, "service:ts-worker"),
            CausalEdge("service:ts-worker", REL_CALLS, "service:ts-db"),
            CausalEdge("service:ts-api", REL_DEPLOYED_ON, "pod:api-1"),
            CausalEdge("pod:api-1", REL_RUNS_ON, "node:node-1"),
        ],
        relation_observations=[
            RelationObservation(
                "ro1",
                "service:ts-api",
                "service:ts-worker",
                "trace_parent_child",
                0.98,
                "api parent span has worker child span",
            ),
            RelationObservation(
                "ro2",
                "service:ts-api",
                "pod:api-1",
                "service_pod_cooccurrence",
                0.98,
                "api telemetry emitted by api-1",
            ),
        ],
    )


def test_rca_case_legacy_positional_signature_is_preserved():
    case = RcaCase("legacy-positional", [], [], [], ["root"])
    assert case.gold_root_causes == ["root"]
    assert case.structural_relations == []
    assert case.relation_observations == []


def test_service_normalization_and_edge_metric_ignore_relation():
    assert normalize_service("TS-Order-Service") == "orderservice"
    pred = [("TS-DB", "anything", "ts-api"), ("load-generator", "anything", "ts-api")]
    gold = [CausalEdge("db", "different_relation", "api")]
    assert service_edge_metrics(pred, gold).f1 == 1.0


def test_process_pr_requires_correct_predicted_root():
    edges = [("ts-db", "x", "ts-worker"), ("ts-worker", "x", "ts-api")]
    assert process_path_reachability(edges, ["ts-db"], ["db"], ["ts-api"]) == 1.0
    assert process_path_reachability(edges, ["ts-cache"], ["db"], ["ts-api"]) == 0.0


def test_relation_masking_preserves_endpoints_and_hides_only_causal_labels():
    case = make_case("relation-mask")
    visible, truth = mask_relation_types(case, 0.5, seed=42)
    assert len(visible.known_edges) == len(case.known_edges)
    assert visible.structural_relations == case.structural_relations
    assert visible.relation_observations == case.relation_observations
    original_pairs = {(e.source, e.target) for e in case.known_edges}
    visible_pairs = {(e.source, e.target) for e in visible.known_edges}
    assert original_pairs == visible_pairs
    assert len(truth) == 2
    assert sum(e.relation == REL_MASKED for e in visible.known_edges) == 2
    assert {e.relation for e in truth} <= {REL_CAUSAL, REL_NON_CAUSAL}
    assert visible.metadata["relation_layer"] == "incident_causal"


def test_relation_masking_is_reproducible_and_case_salted():
    _, a = mask_relation_types(make_case("case-a"), 0.5, seed=42)
    _, a2 = mask_relation_types(make_case("case-a"), 0.5, seed=42)
    _, b = mask_relation_types(make_case("case-b"), 0.5, seed=42)
    assert a == a2
    assert [e.key() for e in a] != [e.key() for e in b]


def test_structural_relation_masking_preserves_pairs_observations_and_is_nested():
    case = make_case("structural-mask")
    visible20, truth20 = mask_structural_relation_types(case, 0.25, seed=7)
    visible50, truth50 = mask_structural_relation_types(case, 0.50, seed=7)
    assert {(e.source, e.target) for e in visible20.structural_relations} == {
        (e.source, e.target) for e in case.structural_relations
    }
    assert sum(e.relation == REL_STRUCTURAL_MASKED for e in visible20.structural_relations) == 1
    assert {e.key() for e in truth20} <= {e.key() for e in truth50}
    assert visible20.known_edges == case.known_edges
    assert visible20.relation_observations == case.relation_observations


def test_structural_relation_metrics_are_typed_triple_exact():
    truth = [
        CausalEdge("service:a", REL_CALLS, "service:b"),
        CausalEdge("service:a", REL_DEPLOYED_ON, "pod:p1"),
    ]
    pred = [
        CausalEdge("service:a", REL_CALLS, "service:b"),
        CausalEdge("service:a", REL_CALLS, "pod:p1"),
    ]
    score = structural_relation_metrics(pred, truth)
    assert score.precision == 0.5
    assert score.recall == 0.5
    assert score.f1 == 0.5


def _synthetic_structural_traces():
    return pd.DataFrame(
        [
            {
                "trace_id": "t1",
                "span_id": "p",
                "parent_span_id": "",
                "service_name": "frontend",
                "attr.k8s.pod.name": "front-1",
                "attr.k8s.node.name": "node-a",
                "attr.db.system": None,
                "attr.server.address": None,
            },
            {
                "trace_id": "t1",
                "span_id": "c",
                "parent_span_id": "p",
                "service_name": "orders",
                "attr.k8s.pod.name": "orders-1",
                "attr.k8s.node.name": "node-b",
                "attr.db.system": "postgresql",
                "attr.server.address": "orders-db",
            },
        ]
    )


def test_stage1_collects_observations_before_final_relations():
    observations = collect_structural_observations(_synthetic_structural_traces())
    kinds = {item.evidence_kind for item in observations}
    assert "trace_parent_child" in kinds
    assert "service_pod_cooccurrence" in kinds
    assert "pod_node_cooccurrence" in kinds
    assert "db_client_context" in kinds
    # Observations carry evidence semantics, not a gold/causal relation field.
    assert all(not hasattr(item, "relation") for item in observations)


def test_stage1_abduction_is_grounded_and_not_cartesian_product():
    observations = [
        RelationObservation(
            "x1", "service:a", "service:b", "trace_parent_child", 0.98, "a parent of b"
        ),
        RelationObservation(
            "x2", "service:c", "pod:p1", "service_pod_cooccurrence", 0.98, "c on p1"
        ),
    ]
    hypotheses = AbductiveStructuralRelationGenerator().generate(observations)
    observed_pairs = {(item.source, item.target) for item in observations}
    assert {(h.edge.source, h.edge.target) for h in hypotheses} <= observed_pairs
    assert CausalEdge("service:a", REL_CALLS, "service:b") in [h.edge for h in hypotheses]
    assert CausalEdge("service:c", REL_DEPLOYED_ON, "pod:p1") in [h.edge for h in hypotheses]
    # No unrelated a->p1 or c->b hypothesis may be invented.
    assert all((h.edge.source, h.edge.target) in observed_pairs for h in hypotheses)


def test_stage1_generic_cooccurrence_is_not_automatically_a_relation_fact():
    observations = [
        RelationObservation(
            "weak",
            "service:a",
            "service:b",
            "generic_endpoint_cooccurrence",
            1.0,
            "a and b appeared in the same broad collection window",
        )
    ]
    result = StructuralRelationRecovery(relation_threshold=0.5).run(observations)
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].abductive_support < 0.5
    assert result.relations == []


def test_stage1_semantic_and_soft_logic_are_explicit_pipeline_steps():
    observations = [
        RelationObservation(
            "x1", "service:a", "service:b", "trace_parent_child", 0.98, "a parent of b"
        )
    ]
    result = StructuralRelationRecovery(
        semantic_scorer=DeterministicStructuralScorer(),
        global_inference=StructuralSoftLogicApproximation(),
        relation_threshold=0.5,
    ).run(observations)
    assert result.hypotheses[0].semantic_support is not None
    assert result.hypotheses[0].soft_logic_score is not None
    assert result.relations == [CausalEdge("service:a", REL_CALLS, "service:b")]


def test_structural_extraction_keeps_natural_direction_and_propagation_reverses_calls():
    traces = _synthetic_structural_traces()
    relations = extract_structural_relations(traces)
    assert CausalEdge("service:frontend", REL_CALLS, "service:orders") in relations
    assert CausalEdge("service:orders", REL_USES_DATABASE, "database:postgresql:orders-db") in relations
    assert CausalEdge("service:frontend", REL_DEPLOYED_ON, "pod:front-1") in relations
    assert CausalEdge("pod:orders-1", REL_RUNS_ON, "node:node-b") in relations

    propagation = propagation_service_edges(relations)
    assert CausalEdge("orders", "dependency_propagates_to", "frontend") in propagation
    assert all(edge.source != "frontend" or edge.target != "orders" for edge in propagation)


def test_recover_structural_relations_exposes_observations_hypotheses_and_relations():
    result = recover_structural_relations(_synthetic_structural_traces())
    assert result.observations
    assert result.hypotheses
    assert result.relations
    assert len(result.relations) <= len(result.hypotheses)


def test_normalized_round_trip_preserves_structural_relations_and_observations(tmp_path):
    path = tmp_path / "case.jsonl"
    original = make_case("round-trip")
    dump_normalized_cases([original], path)
    loaded = load_normalized_cases(path)[0]
    assert loaded.structural_relations == original.structural_relations
    assert loaded.relation_observations == original.relation_observations
    assert loaded.known_edges == original.known_edges


def test_legacy_artifact_without_stage1_fields_still_loads(tmp_path):
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        '{"case_id":"legacy","symptom_nodes":[],"known_edges":[],"evidence":[]}',
        encoding="utf-8",
    )
    loaded = load_normalized_cases(path)[0]
    assert loaded.structural_relations == []
    assert loaded.relation_observations == []


def test_legacy_edge_masking_still_available_for_stress_test():
    case = make_case()
    visible, masked = mask_relations(case, 0.5, seed=13)
    assert len(visible.known_edges) + len(masked) == len(case.known_edges)
    assert visible.structural_relations == case.structural_relations
    assert visible.relation_observations == case.relation_observations


def test_abduction_generates_only_observed_unknown_pairs():
    visible, _ = mask_relation_types(make_case(), 0.5, seed=42)
    hypotheses = AbductiveRelationGenerator().generate(visible)
    masked_pairs = {(e.source, e.target) for e in visible.known_edges if e.relation == REL_MASKED}
    generated_pairs = {(h.edge.source, h.edge.target) for h in hypotheses}
    assert generated_pairs <= masked_pairs
    assert len(hypotheses) <= len(masked_pairs)


def test_abduction_main_track_does_not_truncate_more_than_64_masked_pairs():
    n = 80
    target = "ts-api"
    known_edges = [CausalEdge(f"ts-svc-{i}", REL_MASKED, target) for i in range(n)]
    evidence = [Evidence("target", target, "trace", "latency", 0.9, 2.0, "api slow")]
    evidence.extend(
        Evidence(f"e{i}", f"ts-svc-{i}", "metric", "latency", 0.8, 1.0, "upstream anomaly")
        for i in range(n)
    )
    case = RcaCase(
        case_id="many-masked",
        symptom_nodes=[target],
        known_edges=known_edges,
        evidence=evidence,
    )
    hypotheses = AbductiveRelationGenerator().generate(case)
    assert len(hypotheses) == n


def test_observed_connectivity_is_not_causal_evidence():
    h = Hypothesis(
        CausalEdge("a", REL_CAUSAL, "b"),
        [],
        "observed edge only",
        structural_score=1.0,
        temporal_score=0.0,
        anomaly_score=0.0,
    )
    assert h.abductive_score == 0.0


def test_abduction_does_not_read_gold_only_node():
    case = make_case()
    case.gold_edges.append(CausalEdge("secret-gold-node", REL_CAUSAL, "ts-api"))
    case.gold_root_causes.append("secret-gold-node")
    hypotheses = AbductiveRelationGenerator().generate(case)
    assert all("secret-gold-node" not in (h.edge.source, h.edge.target) for h in hypotheses)


def test_neutral_semantic_margin_preserves_abduction_prior():
    h = Hypothesis(
        CausalEdge("a", REL_CAUSAL, "b"),
        [],
        "test",
        structural_score=1.0,
        temporal_score=0.6,
        anomaly_score=0.6,
        semantic_support=0.5,
        semantic_contradiction=0.5,
        semantic_neutral=1.0,
    )
    assert abs(h.final_score - h.abductive_score) < 1e-9


def test_semantic_and_soft_logic_score_paths_are_distinct():
    h = Hypothesis(
        CausalEdge("a", REL_CAUSAL, "b"),
        [],
        "test",
        temporal_score=0.6,
        anomaly_score=0.6,
        semantic_support=0.9,
        semantic_contradiction=0.1,
        semantic_neutral=0.0,
    )
    semantic_final = h.final_score
    assert semantic_final > h.abductive_score
    h.soft_logic_score = 0.31
    assert h.final_score == 0.31
    assert h.final_score != semantic_final


def test_relation_metric_scores_causal_vs_noncausal_on_masked_pairs():
    truth = [
        CausalEdge("a", REL_CAUSAL, "b"),
        CausalEdge("c", REL_NON_CAUSAL, "d"),
    ]
    pred = [("a", REL_CAUSAL, "b")]
    score = relation_classification_metrics(pred, truth)
    assert score.accuracy == 1.0
    assert score.f1 == 1.0


def test_smoke_pipeline_relation_mask():
    visible, truth = mask_relation_types(make_case(), 0.5, seed=13)
    prediction = MissingRelationRCA().run(visible)
    assert prediction.case_id == visible.case_id
    assert len(prediction.ranked_hypotheses) <= sum(
        e.relation == REL_MASKED for e in visible.known_edges
    )
    score = relation_classification_metrics(prediction.predicted_edges, truth)
    assert 0.0 <= score.accuracy <= 1.0
