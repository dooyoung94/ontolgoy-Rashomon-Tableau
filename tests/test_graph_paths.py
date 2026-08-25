from rashomon_tableau.graph_paths import bidirectional_candidate_paths, canonical_entity
from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import Ontology


def lit(predicate, subject, object_, negated=False, story="0"):
    return Literal(predicate, subject, object_, negated, story=story, source="context2")


def test_canonical_entity_removes_accents_case_and_punctuation():
    assert canonical_entity("Perpignan Méditerranée Métropole") == canonical_entity(
        "perpignan mediterranee-metropole"
    )
    assert canonical_entity("Canohès") == canonical_entity("canohes")


def test_symmetric_relation_can_be_traversed_in_reverse_semantically():
    ontology = Ontology(symmetric={"shares border with"})
    facts = [lit("shares border with", "Villemolaque", "Cabestany")]
    paths = bidirectional_candidate_paths(
        facts,
        "Cabestany",
        "Villemolaque",
        max_hops=1,
        ontology=ontology,
    )
    assert paths
    assert any(path.literals[0].subject == "Cabestany" for path in paths)
    assert any("symmetry:shares border with" in path.traversal_rules for path in paths)


def test_signed_structural_path_preserves_negated_literal():
    facts = [
        lit("located in", "Southern Ostrobothnia", "Vasa County", story="0"),
        lit("instance of", "Vasa County", "Guberniyas", story="0"),
        lit("part of", "Kuortane", "Guberniyas", negated=True, story="4"),
    ]
    paths = bidirectional_candidate_paths(
        facts,
        "Southern Ostrobothnia",
        "Kuortane",
        max_hops=3,
        ontology=Ontology(),
    )
    assert paths
    path = min(paths, key=lambda x: x.hop_count)
    assert path.hop_count == 3
    assert any(x.negated for x in path.literals)
    assert any(rule == "structural_reverse" for rule in path.traversal_rules)


def test_accent_canonicalization_recovers_magic_style_multihop_path():
    ontology = Ontology(symmetric={"shares border with"})
    facts = [
        lit("divides into", "Perpignan Méditerranée Métropole", "Ponteilla"),
        lit("shares border with", "Ponteilla", "Villemolaque"),
        lit("shares border with", "Villemolaque", "Cabestany"),
    ]
    paths = bidirectional_candidate_paths(
        facts,
        "Perpignan Mediterranee Metropole",
        "Cabestany",
        max_hops=4,
        ontology=ontology,
    )
    assert paths
    assert min(path.hop_count for path in paths) == 3
