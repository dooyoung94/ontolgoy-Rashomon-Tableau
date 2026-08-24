from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import Clash, Literal, TableauResult
from .ontology import Ontology


class RelationalTableau:
    """Lightweight explainable tableau for binary Conan relations."""

    def __init__(self, ontology: Ontology):
        self.ontology = ontology

    def check(self, facts: Iterable[Literal]) -> TableauResult:
        closure, derivations = self.ontology.forward_chain(facts)
        clashes: list[Clash] = []

        by_key = defaultdict(dict)
        for lit in closure:
            by_key[lit.positive_key()][lit.negated] = lit
        for signs in by_key.values():
            if False in signs and True in signs:
                pos, neg = signs[False], signs[True]
                clashes.append(Clash("literal_negation", [pos, neg], f"{pos.text()} conflicts with {neg.text()}", _rules_for([pos, neg], derivations)))

        positives = [x for x in closure if not x.negated]
        grouped_pair = defaultdict(list)
        for lit in positives:
            grouped_pair[(lit.subject, lit.object)].append(lit)
        for pair_lits in grouped_pair.values():
            for i, left in enumerate(pair_lits):
                for right in pair_lits[i + 1:]:
                    if (left.predicate, right.predicate) in self.ontology.incompatible:
                        clashes.append(Clash("incompatible_relations", [left, right], f"{left.predicate} is incompatible with {right.predicate}", _rules_for([left, right], derivations)))

        by_subject_pred = defaultdict(list)
        for lit in positives:
            if lit.predicate in self.ontology.exclusive:
                by_subject_pred[(lit.subject, lit.predicate)].append(lit)
        for (_, pred), rels in by_subject_pred.items():
            objects = {x.object for x in rels}
            if len(objects) > 1:
                clashes.append(Clash("exclusive_relation", rels, f"Exclusive relation {pred} has multiple objects: {sorted(objects)}", _rules_for(rels, derivations)))

        return TableauResult(not clashes, sorted(closure), clashes, derivations)


def _rules_for(literals, derivations):
    rules = []
    for lit in literals:
        d = derivations.get(lit.key())
        if d and d.rule not in rules:
            rules.append(d.rule)
    return rules
