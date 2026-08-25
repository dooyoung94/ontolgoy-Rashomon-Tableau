from openrca_mr.abduction import AbductiveRelationGenerator
from openrca_mr.masking import mask_relations
from openrca_mr.metrics import normalize_service, process_path_reachability, service_edge_metrics
from openrca_mr.models import CausalEdge, Evidence, RcaCase
from openrca_mr.pipeline import MissingRelationRCA


def make_case(case_id="c1"):
    return RcaCase(
        case_id=case_id,
        symptom_nodes=["ts-api"],
        known_edges=[
            CausalEdge("ts-db", "calls", "ts-worker"),
            CausalEdge("ts-worker", "calls", "ts-api"),
            CausalEdge("ts-other", "calls", "ts-api"),
            CausalEdge("ts-cache", "calls", "ts-other"),
        ],
        evidence=[
            Evidence("e1", "ts-db", "metric", "latency", 0.95, 1.0, "db latency high"),
            Evidence("e2", "ts-worker", "trace", "duration", 0.90, 2.0, "worker span slow"),
            Evidence("e3", "ts-api", "metric", "latency", 0.98, 3.0, "api latency high"),
            Evidence("e4", "ts-other", "metric", "cpu", 0.10, 2.0, "cpu normal"),
        ],
        gold_root_causes=["ts-db"],
        gold_edges=[
            CausalEdge("ts-db", "causes", "ts-worker"),
            CausalEdge("ts-worker", "causes", "ts-api"),
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


def test_masking_is_reproducible_and_case_salted():
    a_visible, a_masked = mask_relations(make_case("case-a"), 0.5, seed=42)
    a_visible2, a_masked2 = mask_relations(make_case("case-a"), 0.5, seed=42)
    _, b_masked = mask_relations(make_case("case-b"), 0.5, seed=42)
    assert a_masked == a_masked2
    assert a_visible.known_edges == a_visible2.known_edges
    assert [e.key() for e in a_masked] != [e.key() for e in b_masked]
    assert a_visible.gold_alarm_nodes == ["ts-api"]


def test_abduction_does_not_read_gold_only_node():
    case = make_case()
    case.gold_edges.append(CausalEdge("secret-gold-node", "causes", "ts-api"))
    case.gold_root_causes.append("secret-gold-node")
    hypotheses = AbductiveRelationGenerator().generate(case)
    assert all("secret-gold-node" not in (h.edge.source, h.edge.target) for h in hypotheses)


def test_smoke_pipeline_and_pair_metric():
    case = make_case()
    visible, masked = mask_relations(case, 0.5, seed=13)
    prediction = MissingRelationRCA().run(visible)
    assert prediction.case_id == case.case_id
    assert prediction.ranked_hypotheses
    score = service_edge_metrics(prediction.predicted_edges, masked)
    assert 0.0 <= score.f1 <= 1.0
