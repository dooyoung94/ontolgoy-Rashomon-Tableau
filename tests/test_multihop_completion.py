from rashomon_tableau.models import Literal
from rashomon_tableau.multihop_completion import (
    RelationCandidate,
    complete_missing_relation,
    select_rashomon_candidates,
)
from rashomon_tableau.ontology import Ontology


def lit(predicate, subject, object_, negated=False):
    return Literal(predicate, subject, object_, negated)


def test_rashomon_keeps_near_optimal_candidates():
    candidates = [
        RelationCandidate("part of", 0.82),
        RelationCandidate("located in", 0.79),
        RelationCandidate("distinct from", 0.20),
    ]
    retained = select_rashomon_candidates(candidates, epsilon=0.05)
    assert [candidate.relation for candidate in retained] == ["part of", "located in"]


def test_tableau_rejects_incompatible_completion_world():
    ontology = Ontology(incompatible={("equivalent to", "distinct from"), ("distinct from", "equivalent to")})
    facts = [lit("distinct from", "a", "c")]
    candidates = [
        RelationCandidate("equivalent to", 0.90),
        RelationCandidate("distinct from", 0.88),
    ]
    result = complete_missing_relation(facts, "a", "c", candidates, ontology, epsilon=0.05)
    assert [world.relation for world in result.rejected_worlds] == ["equivalent to"]
    assert [world.relation for world in result.valid_worlds] == ["distinct from"]
    assert result.top_relation == "distinct from"
    assert result.relation_marginal == {"distinct from": 1.0}


def test_multiple_paths_are_marginalized_to_same_relation():
    ontology = Ontology()
    path1 = (lit("r1", "a", "b"), lit("r2", "b", "d"))
    path2 = (lit("r3", "a", "c"), lit("r4", "c", "d"))
    candidates = [
        RelationCandidate("part of", 0.80, path1),
        RelationCandidate("part of", 0.75, path2),
        RelationCandidate("located in", 0.77, path1),
    ]
    result = complete_missing_relation([], "a", "d", candidates, ontology, epsilon=0.05)
    assert len(result.valid_worlds) == 3
    assert result.relation_marginal["part of"] > result.relation_marginal["located in"]
    assert result.top_relation == "part of"
