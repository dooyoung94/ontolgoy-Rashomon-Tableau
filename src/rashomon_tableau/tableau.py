from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import BidirectionalVerification, Clash, Literal, TableauResult
from .ontology import Ontology


class RelationalTableau:
    """Explainable relational tableau over ontology-governed binary relations.

    `check` detects global clashes in a fact set.
    `verify` evaluates one proposition in both directions: q and not-q/incompatible evidence.
    """

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
                clashes.append(
                    Clash(
                        "literal_negation",
                        [pos, neg],
                        f"{pos.text()} conflicts with {neg.text()}",
                        _rules_for([pos, neg], derivations),
                    )
                )

        positives = [x for x in closure if not x.negated]
        grouped_pair = defaultdict(list)
        for lit in positives:
            grouped_pair[(lit.subject, lit.object)].append(lit)
        for pair_lits in grouped_pair.values():
            for i, left in enumerate(pair_lits):
                for right in pair_lits[i + 1:]:
                    if (left.predicate, right.predicate) in self.ontology.incompatible:
                        clashes.append(
                            Clash(
                                "incompatible_relations",
                                [left, right],
                                f"{left.predicate} is incompatible with {right.predicate}",
                                _rules_for([left, right], derivations),
                            )
                        )

        by_subject_pred = defaultdict(list)
        for lit in positives:
            if lit.predicate in self.ontology.exclusive:
                by_subject_pred[(lit.subject, lit.predicate)].append(lit)
        for (_, pred), rels in by_subject_pred.items():
            objects = {x.object for x in rels}
            if len(objects) > 1:
                clashes.append(
                    Clash(
                        "exclusive_relation",
                        rels,
                        f"Exclusive relation {pred} has multiple objects: {sorted(objects)}",
                        _rules_for(rels, derivations),
                    )
                )

        return TableauResult(not clashes, sorted(closure), clashes, derivations)

    def verify(self, facts: Iterable[Literal], query: Literal) -> BidirectionalVerification:
        """Verify q and its opposing direction without assuming closed-world negation.

        Contradiction is accepted only when one of the following is present/derivable:
        1) explicit not-q,
        2) an ontology-declared incompatible relation on the same ordered pair,
        3) a competing object for an ontology-declared exclusive relation.

        Missing support for q is therefore UNRESOLVED, not false.
        """
        closure, derivations = self.ontology.forward_chain(facts)
        query_key = query.key()
        neg_key = query.negate().key()

        supported_lit = next((x for x in closure if x.key() == query_key), None)
        explicit_neg = next((x for x in closure if x.key() == neg_key), None)

        contradiction_lit: Literal | None = explicit_neg
        contradiction_rule: str | None = None

        if contradiction_lit is None and not query.negated:
            for lit in closure:
                if lit.negated:
                    continue
                if lit.subject == query.subject and lit.object == query.object:
                    if (query.predicate, lit.predicate) in self.ontology.incompatible:
                        contradiction_lit = lit
                        contradiction_rule = f"incompatible:{query.predicate}!={lit.predicate}"
                        break

            if contradiction_lit is None and query.predicate in self.ontology.exclusive:
                for lit in closure:
                    if (
                        not lit.negated
                        and lit.subject == query.subject
                        and lit.predicate == query.predicate
                        and lit.object != query.object
                    ):
                        contradiction_lit = lit
                        contradiction_rule = f"exclusive:{query.predicate}"
                        break

        supported = supported_lit is not None
        contradicted = contradiction_lit is not None
        if supported and contradicted:
            status = "BOTH"
        elif supported:
            status = "SUPPORTED"
        elif contradicted:
            status = "CONTRADICTED"
        else:
            status = "UNRESOLVED"

        support_rules = _trace_rules(supported_lit, derivations) if supported_lit else []
        contradiction_rules = _trace_rules(contradiction_lit, derivations) if contradiction_lit else []
        if contradiction_rule and contradiction_rule not in contradiction_rules:
            contradiction_rules.append(contradiction_rule)

        return BidirectionalVerification(
            query=query,
            supported=supported,
            contradicted=contradicted,
            status=status,
            support_rules=support_rules,
            contradiction_rules=contradiction_rules,
            support_path=_trace_literals(supported_lit, derivations) if supported_lit else [],
            contradiction_path=_trace_literals(contradiction_lit, derivations) if contradiction_lit else [],
        )


def _rules_for(literals, derivations):
    rules = []
    for lit in literals:
        d = derivations.get(lit.key())
        if d and d.rule not in rules:
            rules.append(d.rule)
    return rules


def _trace_rules(lit: Literal | None, derivations) -> list[str]:
    if lit is None:
        return []
    seen: set[tuple[str, str, str, bool]] = set()
    rules: list[str] = []

    def walk(node: Literal):
        if node.key() in seen:
            return
        seen.add(node.key())
        d = derivations.get(node.key())
        if not d:
            return
        for parent in d.parents:
            walk(parent)
        if d.rule not in rules:
            rules.append(d.rule)

    walk(lit)
    return rules


def _trace_literals(lit: Literal | None, derivations) -> list[str]:
    if lit is None:
        return []
    seen: set[tuple[str, str, str, bool]] = set()
    path: list[str] = []

    def walk(node: Literal):
        if node.key() in seen:
            return
        seen.add(node.key())
        d = derivations.get(node.key())
        if d:
            for parent in d.parents:
                walk(parent)
        path.append(node.text())

    walk(lit)
    return path
