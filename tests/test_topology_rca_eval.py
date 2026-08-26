from __future__ import annotations

from openrca_mr.models import CausalEdge, Evidence, RcaCase, RelationObservation, REL_CALLS, REL_CAUSAL
from openrca_mr.openrca2 import dump_normalized_cases
from openrca_mr.topology_rca_eval import run_topology_rca_evaluation


def _case() -> RcaCase:
    return RcaCase(
        case_id="topology-rca-1",
        symptom_nodes=["frontend"],
        known_edges=[],
        evidence=[
            Evidence("e1", "orders", "metric", "latency", 0.95, 1.0, "orders becomes slow"),
            Evidence("e2", "frontend", "trace", "latency", 0.90, 2.0, "frontend becomes slow"),
        ],
        gold_root_causes=["orders"],
        gold_edges=[CausalEdge("orders", REL_CAUSAL, "frontend")],
        gold_alarm_nodes=["frontend"],
        structural_relations=[
            CausalEdge("service:frontend", REL_CALLS, "service:orders"),
        ],
        relation_observations=[
            RelationObservation(
                "o1",
                "service:frontend",
                "service:orders",
                "trace_parent_child",
                0.98,
                "frontend parent span has orders child span",
            )
        ],
    )


def test_recovered_topology_improves_rca_path_and_edge(tmp_path):
    data = tmp_path / "case.jsonl"
    out = tmp_path / "result.json"
    dump_normalized_cases([_case()], data)

    result = run_topology_rca_evaluation(
        data=str(data),
        out=str(out),
        topology_variant="abduction",
        rca_variant="abduction",
        topology_missing_ratio=1.0,
        seed=42,
    )

    assert result["track"] == "topology_recovery_plus_openrca2_rca"
    assert result["protocol"]["collector_observations_modified"] is False
    assert result["protocol"]["only_topology_relations_removed"] is True
    assert result["topology_summary"]["macro_missing_relation_f1"] == 1.0

    rca = result["rca_summary"]
    assert rca["incomplete"]["path_reachability"] == 0.0
    assert rca["recovered"]["path_reachability"] == 1.0
    assert rca["complete"]["path_reachability"] == 1.0
    assert rca["incomplete"]["edge_f1"] == 0.0
    assert rca["recovered"]["edge_f1"] == 1.0
    assert rca["complete"]["edge_f1"] == 1.0
    assert rca["delta_recovered_vs_incomplete"]["path_reachability"] == 1.0
    assert rca["delta_recovered_vs_incomplete"]["edge_f1"] == 1.0
