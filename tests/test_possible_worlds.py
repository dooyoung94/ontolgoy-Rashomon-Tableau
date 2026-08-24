from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.possible_worlds import (
    PathRelationHypothesis,
    RelationHypothesis,
    WorldChoice,
    build_possible_worlds,
    truth_marginal,
)
from rashomon_tableau.tableau import RelationalTableau


def test_relation_hypotheses_branch_into_worlds():
    reasoner = RelationalTableau(Ontology())
    facts = [Literal("r1", "A", "X", source="S1"), Literal("r2", "X", "B", source="S2")]
    positive = RelationHypothesis("positive", "r1", "r2", "q", 0.7)
    negative = RelationHypothesis("negative", "r1", "r2", "q", 0.2, negated_result=True)
    worlds = build_possible_worlds(
        facts,
        [[WorldChoice(positive, "q", 0.7), WorldChoice(negative, "not-q", 0.2), WorldChoice.unresolved(confidence=0.1)]],
        reasoner,
        {"S1": 0.9, "S2": 0.8},
    )
    assert len(worlds) == 3
    assert abs(sum(world.weight for world in worlds) - 1.0) < 1e-9


def test_truth_is_marginalized_over_worlds():
    reasoner = RelationalTableau(Ontology())
    facts = [Literal("r1", "A", "X"), Literal("r2", "X", "B")]
    positive = RelationHypothesis("positive", "r1", "r2", "q", 0.75)
    negative = RelationHypothesis("negative", "r1", "r2", "q", 0.25, negated_result=True)
    worlds = build_possible_worlds(
        facts,
        [[WorldChoice(positive, "q", 0.75), WorldChoice(negative, "not-q", 0.25)]],
        reasoner,
    )
    result = truth_marginal(worlds, Literal("q", "A", "B"), reasoner)
    assert result.winning_status == "SUPPORTED"
    assert round(result.support, 2) == 0.75
    assert round(result.contradiction, 2) == 0.25


def test_inconsistent_world_is_pruned():
    reasoner = RelationalTableau(Ontology())
    facts = [Literal("q", "A", "B")]
    negative = RelationHypothesis("negative", "r1", "r2", "q", 1.0, negated_result=True)
    base = [*facts, Literal("r1", "A", "X"), Literal("r2", "X", "B")]
    worlds = build_possible_worlds(base, [[WorldChoice(negative, "not-q", 1.0)]], reasoner)
    assert worlds == []


def test_three_hop_path_hypothesis_derives_endpoint_claim():
    reasoner = RelationalTableau(Ontology())
    facts = [Literal("r1", "A", "X"), Literal("r2", "X", "Y"), Literal("r3", "Y", "B")]
    hypothesis = PathRelationHypothesis("three-hop", ("r1", "r2", "r3"), "q", 0.8, negated_result=True)
    worlds = build_possible_worlds(facts, [[WorldChoice(hypothesis, "not-q", 0.8)]], reasoner)
    assert len(worlds) == 1
    result = truth_marginal(worlds, Literal("q", "A", "B"), reasoner)
    assert result.contradiction == 1.0
