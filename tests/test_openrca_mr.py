from openrca_mr.abduction import AbductiveRelationGenerator
from openrca_mr.masking import mask_relation_types, mask_relations
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
    REL_CAUSAL,
    REL_MASKED,
    REL_NON_CAUSAL,
)
from openrca_mr.pipeline import MissingRelationRCA


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
    )


def test_service_normalization_and_edge_metric_ignore_relation():
    assert normalize_service("TS-Order-Service") == "orderservice"
    pred = [("TS-DB", "anything", "ts-api"), ("load-generator", "anything", "ts-api")]
    gold = [CausalEdge("db", "different_relation", "api")]
    assert service_edge_metrics(pred, gold).f1 == 1.0


def test_process_pr_requires_correct_predicted_root():
    edges = [("ts-db", "x", "ts-worker"), ("ts-worker", "x", "ts-api")]
    assert process_path_reachability(edges, ["ts-db"], ["db"], ["ts-api"]) == 1.0
    assert process_path_reachability(edges, ["ts-cache"], ["db"], ["ts-api"]) == 0.0


def test_relation_masking_preserves_endpoints_and_hides_only_labels():
    case = make_case("relation-mask")
    visible, truth = mask_relation_types(case, 0.5, seed=42)
    assert len(visible.known_edges) == len(case.known_edges)
    original_pairs = {(e.source, e.target) for e in case.known_edges}
    visible_pairs = {(e.source, e.target) for e in visible.known_edges}
    assert original_pairs == visible_pairs
    assert len(truth) == 2
    assert sum(e.relation == REL_MASKED for e in visible.known_edges) == 2
    assert {e.relation for e in truth} <= {REL_CAUSAL, REL_NON_CAUSAL}


def test_relation_masking_is_reproducible_and_case_salted():
    _, a = mask_relation_types(make_case("case-a"), 0.5, seed=42)
    _, a2 = mask_relation_types(make_case("case-a"), 0.5, seed=42)
    _, b = mask_relation_types(make_case("case-b"), 0.5, seed=42)
    assert a == a2
    assert [e.key() for e in a] != [e.key() for e in b]


def test_legacy_edge_masking_still_available_for_stress_test():
    case = make_case()
    visible, masked = mask_relations(case, 0.5, seed=13)
    assert len(visible.known_edges) + len(masked) == len(case.known_edges)


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
    assert len(prediction.ranked_hypotheses) <= sum(e.relation == REL_MASKED for e in visible.known_edges)
    score = relation_classification_metrics(prediction.predicted_edges, truth)
    assert 0.0 <= score.accuracy <= 1.0
