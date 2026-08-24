from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import CompositionRule, Ontology
from rashomon_tableau.tableau import RelationalTableau
from rashomon_tableau.rashomon import minimal_unsat_subsets


def test_explicit_clash():
    r = RelationalTableau(Ontology())
    a = Literal('friend', 'A', 'B')
    b = Literal('friend', 'A', 'B', True)
    x = r.check([a, b])
    assert not x.satisfiable
    assert x.clashes[0].kind == 'literal_negation'


def test_hierarchy_implicit_clash():
    o = Ontology(hierarchy={'father_of_x': {'parent_of_x'}})
    r = RelationalTableau(o)
    facts = [Literal('father_of_x', 'A', 'B'), Literal('parent_of_x', 'A', 'B', True)]
    x = r.check(facts)
    assert not x.satisfiable
    assert any('hierarchy' in rule for c in x.clashes for rule in c.rules)


def test_inverse_implicit_clash():
    o = Ontology(inverse={'host_of_x': 'guest_of_x'})
    r = RelationalTableau(o)
    facts = [Literal('host_of_x', 'A', 'B'), Literal('guest_of_x', 'B', 'A', True)]
    assert not r.check(facts).satisfiable


def test_transitive_derivation():
    o = Ontology(transitive={'part_of'})
    closure, derivations = o.forward_chain([
        Literal('part_of', 'A', 'B'),
        Literal('part_of', 'B', 'C'),
    ])
    target = Literal('part_of', 'A', 'C')
    assert target in closure
    assert derivations[target.key()].rule == 'transitive:part_of'


def test_relation_composition_derivation():
    o = Ontology(compositions={CompositionRule('instance_of', 'subclass_of', 'instance_of')})
    closure, derivations = o.forward_chain([
        Literal('instance_of', 'A', 'B'),
        Literal('subclass_of', 'B', 'C'),
    ])
    target = Literal('instance_of', 'A', 'C')
    assert target in closure
    assert 'composition:' in derivations[target.key()].rule


def test_bidirectional_supported():
    o = Ontology(hierarchy={'father': {'parent'}})
    r = RelationalTableau(o)
    result = r.verify([Literal('father', 'A', 'B')], Literal('parent', 'A', 'B'))
    assert result.status == 'SUPPORTED'
    assert any('hierarchy' in x for x in result.support_rules)


def test_bidirectional_contradicted_by_explicit_negation():
    r = RelationalTableau(Ontology())
    result = r.verify([Literal('parent', 'A', 'B', True)], Literal('parent', 'A', 'B'))
    assert result.status == 'CONTRADICTED'


def test_bidirectional_both():
    r = RelationalTableau(Ontology())
    result = r.verify(
        [Literal('parent', 'A', 'B'), Literal('parent', 'A', 'B', True)],
        Literal('parent', 'A', 'B'),
    )
    assert result.status == 'BOTH'


def test_bidirectional_unresolved_is_not_false():
    r = RelationalTableau(Ontology())
    result = r.verify([Literal('coworker', 'A', 'C')], Literal('parent', 'A', 'B'))
    assert result.status == 'UNRESOLVED'


def test_divergence_is_satisfiable():
    r = RelationalTableau(Ontology())
    assert r.check([Literal('friend', 'A', 'B'), Literal('coworker', 'A', 'C')]).satisfiable


def test_mus():
    r = RelationalTableau(Ontology())
    facts = [Literal('friend', 'A', 'B'), Literal('friend', 'A', 'B', True), Literal('coworker', 'X', 'Y')]
    mus = minimal_unsat_subsets(facts, r)
    assert len(mus) == 1
    assert len(mus[0]) == 2
