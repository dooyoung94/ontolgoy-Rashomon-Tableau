from rashomon_tableau.kg_multihop_benchmark import KGTriple, build_multihop_examples
from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.tableau import RelationalTableau


def test_builder_masks_direct_relation_and_keeps_two_hop_path():
    train = [
        KGTriple("A", "r1", "B"),
        KGTriple("B", "r2", "C"),
    ]
    targets = [KGTriple("A", "gold", "C")]

    examples = build_multihop_examples(train, targets, min_hops=2, max_hops=4)

    assert len(examples) == 1
    assert examples[0].gold_relation == "gold"
    assert [edge.relation for edge in examples[0].path] == ["r1", "r2"]


def test_builder_rejects_one_hop_only_target():
    train = [KGTriple("A", "gold", "C")]
    targets = [KGTriple("A", "gold", "C")]

    examples = build_multihop_examples(train, targets, min_hops=2, max_hops=4)

    assert examples == []


def test_tableau_rejects_hypernym_cycle_from_candidate_completion():
    ontology = Ontology(transitive={"_hypernym"}, irreflexive={"_hypernym"}, antisymmetric={"_hypernym"})
    reasoner = RelationalTableau(ontology)
    facts = [
        Literal("_hypernym", "A", "B"),
        Literal("_hypernym", "B", "C"),
        Literal("_hypernym", "C", "A"),
    ]

    result = reasoner.check(facts)

    assert not result.satisfiable
    assert any(clash.kind in {"irreflexive_relation", "antisymmetric_relation"} for clash in result.clashes)
