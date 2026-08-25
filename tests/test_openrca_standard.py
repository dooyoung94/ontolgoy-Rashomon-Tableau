from openrca_mr.metrics import node_metrics, root_set_metrics, service_edge_metrics
from openrca_mr.models import Evidence, RcaCase
from openrca_mr.pipeline import MissingRelationRCA


def test_openrca_empty_set_boundary_is_perfect_when_both_empty():
    edge = service_edge_metrics([], [])
    node = node_metrics([], [])
    root = root_set_metrics([], [])
    assert edge.precision == edge.recall == edge.f1 == 1.0
    assert node.precision == node.recall == node.f1 == 1.0
    assert root.precision == root.recall == root.f1 == 1.0


def test_node_metric_includes_root_claim_without_propagation_edge():
    score = node_metrics([], [], predicted_roots=["ts-seat"], gold_roots=["seat"])
    assert score.f1 == 1.0


def test_pipeline_falls_back_to_telemetry_root_without_edges():
    case = RcaCase(
        case_id="no-topology",
        symptom_nodes=["gateway"],
        known_edges=[],
        evidence=[
            Evidence("e1", "seat", "metric", "cpu", 0.95, 1.0, "seat cpu anomaly"),
            Evidence("e2", "gateway", "trace", "latency", 0.99, 3.0, "gateway slow"),
            Evidence("e3", "route", "metric", "cpu", 0.2, 2.0, "route mostly normal"),
        ],
    )
    pred = MissingRelationRCA(max_root_causes=3).run(case)
    assert pred.predicted_edges == []
    assert pred.predicted_root_causes
    assert pred.predicted_root_causes[0] == "seat"


def test_telemetry_root_fallback_does_not_read_gold():
    case = RcaCase(
        case_id="gold-hidden",
        symptom_nodes=["gateway"],
        known_edges=[],
        evidence=[Evidence("e1", "seat", "metric", "cpu", 0.9, 1.0, "seat anomalous")],
        gold_root_causes=["secret-gold-service"],
    )
    pred = MissingRelationRCA().run(case)
    assert "secret-gold-service" not in pred.predicted_root_causes
