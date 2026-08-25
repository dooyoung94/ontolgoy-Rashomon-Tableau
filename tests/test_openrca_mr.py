from openrca_mr.abduction import AbductiveRelationGenerator
from openrca_mr.masking import mask_relations
from openrca_mr.metrics import edge_metrics
from openrca_mr.models import CausalEdge, Evidence, RcaCase
from openrca_mr.pipeline import MissingRelationRCA
from openrca_mr.psl import SoftLogicApproximation
from openrca_mr.semantic import DeterministicEvidenceScorer


def sample_case() -> RcaCase:
    return RcaCase(
        case_id="case-1",
        symptom_nodes=["gateway"],
        known_edges=[
            CausalEdge("db", "causal_propagates_to", "service"),
            CausalEdge("service", "causal_propagates_to", "gateway"),
        ],
        evidence=[
            Evidence("e1", "db", "metric", "lock_wait", 0.95, 1.0),
            Evidence("e2", "service", "trace", "latency", 0.90, 2.0),
            Evidence("e3", "gateway", "metric", "latency", 0.92, 3.0),
        ],
        gold_root_causes=["db"],
    )


def test_relation_masking_is_input_only():
    case = sample_case()
    masked_case, removed = mask_relations(case, 0.5, seed=1)
    assert len(masked_case.known_edges) + len(removed) == len(case.known_edges)
    assert masked_case.gold_root_causes == case.gold_root_causes


def test_abduction_does_not_read_gold():
    case = sample_case()
    case.gold_root_causes = ["impossible-gold-only-node"]
    hypotheses = AbductiveRelationGenerator().generate(case)
    assert all("impossible-gold-only-node" not in h.edge.key() for h in hypotheses)


def test_full_smoke_pipeline():
    case = sample_case()
    visible, removed = mask_relations(case, 0.5, seed=1)
    model = MissingRelationRCA(
        semantic_scorer=DeterministicEvidenceScorer(),
        global_inference=SoftLogicApproximation(),
        edge_threshold=0.25,
    )
    prediction = model.run(visible)
    assert prediction.case_id == case.case_id
    assert prediction.ranked_hypotheses
    metrics = edge_metrics(prediction.predicted_edges, removed)
    assert 0.0 <= metrics.f1 <= 1.0
