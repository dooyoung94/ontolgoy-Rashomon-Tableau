from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.tableau import RelationalTableau
from rashomon_tableau.rashomon import minimal_unsat_subsets


def test_explicit_clash():
    r=RelationalTableau(Ontology())
    a=Literal('friend','A','B'); b=Literal('friend','A','B',True)
    x=r.check([a,b]); assert not x.satisfiable; assert x.clashes[0].kind=='literal_negation'


def test_hierarchy_implicit_clash():
    o=Ontology(hierarchy={'father_of_x':{'parent_of_x'}}); r=RelationalTableau(o)
    facts=[Literal('father_of_x','A','B'),Literal('parent_of_x','A','B',True)]
    x=r.check(facts); assert not x.satisfiable
    assert any('hierarchy' in rule for c in x.clashes for rule in c.rules)


def test_inverse_implicit_clash():
    o=Ontology(inverse={'host_of_x':'guest_of_x'}); r=RelationalTableau(o)
    facts=[Literal('host_of_x','A','B'),Literal('guest_of_x','B','A',True)]
    assert not r.check(facts).satisfiable


def test_divergence_is_satisfiable():
    r=RelationalTableau(Ontology())
    assert r.check([Literal('friend','A','B'),Literal('coworker','A','C')]).satisfiable


def test_mus():
    r=RelationalTableau(Ontology())
    facts=[Literal('friend','A','B'),Literal('friend','A','B',True),Literal('coworker','X','Y')]
    mus=minimal_unsat_subsets(facts,r); assert len(mus)==1; assert len(mus[0])==2
