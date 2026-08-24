from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from .models import Derivation, Literal


@dataclass(frozen=True)
class CompositionRule:
    left: str
    right: str
    result: str


@dataclass
class Ontology:
    symmetric: set[str] = field(default_factory=set)
    inverse: dict[str, str] = field(default_factory=dict)
    hierarchy: dict[str, set[str]] = field(default_factory=dict)
    incompatible: set[tuple[str, str]] = field(default_factory=set)
    exclusive: set[str] = field(default_factory=set)
    transitive: set[str] = field(default_factory=set)
    compositions: set[CompositionRule] = field(default_factory=set)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Ontology":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        symmetric = set(data.get("symmetric", []))
        inverse = dict(data.get("inverse", {}))
        hierarchy = {k: set(v or []) for k, v in (data.get("hierarchy", {}) or {}).items()}
        incompatible: set[tuple[str, str]] = set()
        for pair in data.get("incompatible", []) or []:
            if len(pair) == 2:
                a, b = pair
                incompatible.add((a, b))
                incompatible.add((b, a))
        exclusive = set(data.get("exclusive", []))
        transitive = set(data.get("transitive", []))
        compositions: set[CompositionRule] = set()
        for rule in data.get("composition", []) or []:
            if isinstance(rule, dict) and all(k in rule for k in ("left", "right", "result")):
                compositions.add(CompositionRule(rule["left"], rule["right"], rule["result"]))
        return cls(symmetric, inverse, hierarchy, incompatible, exclusive, transitive, compositions)

    @staticmethod
    def _derived(lit: Literal, predicate: str, subject: str, object_: str, negated: bool | None = None) -> Literal:
        return Literal(
            predicate,
            subject,
            object_,
            lit.negated if negated is None else negated,
            lit.perspective,
            lit.story,
            lit.source,
        )

    def forward_chain(self, facts: Iterable[Literal]):
        """Compute a conservative ontology closure while retaining one derivation per literal.

        Symmetric and inverse relations are logical equivalences, so their direction can be
        propagated for positive and explicitly negated literals. Hierarchy, transitivity and
        relation composition are applied only to positive facts: e.g. ¬Parent does not imply
        ¬Father from Father ⊑ Parent.
        """
        closure = set(facts)
        derivations = {lit.key(): Derivation(lit, "asserted", []) for lit in closure}

        def add(new: Literal, rule: str, parents: list[Literal]) -> bool:
            if new in closure:
                return False
            closure.add(new)
            derivations[new.key()] = Derivation(new, rule, parents)
            return True

        changed = True
        while changed:
            changed = False

            for lit in list(closure):
                if lit.predicate in self.symmetric:
                    new = self._derived(lit, lit.predicate, lit.object, lit.subject)
                    changed = add(new, f"symmetry:{lit.predicate}", [lit]) or changed

                inv = self.inverse.get(lit.predicate)
                if inv:
                    new = self._derived(lit, inv, lit.object, lit.subject)
                    changed = add(new, f"inverse:{lit.predicate}->{inv}", [lit]) or changed

                if lit.negated:
                    continue

                for parent in self.hierarchy.get(lit.predicate, set()):
                    new = self._derived(lit, parent, lit.subject, lit.object, False)
                    changed = add(new, f"hierarchy:{lit.predicate}->{parent}", [lit]) or changed

            positives = [x for x in closure if not x.negated]
            outgoing: dict[str, list[Literal]] = {}
            for lit in positives:
                outgoing.setdefault(lit.subject, []).append(lit)

            # r(x,y) ∧ r(y,z) -> r(x,z), but only for explicitly transitive r.
            for first in positives:
                if first.predicate not in self.transitive:
                    continue
                for second in outgoing.get(first.object, []):
                    if second.predicate != first.predicate:
                        continue
                    new = self._derived(first, first.predicate, first.subject, second.object, False)
                    changed = add(new, f"transitive:{first.predicate}", [first, second]) or changed

            # r1(x,y) ∧ r2(y,z) -> r3(x,z), only for declared composition rules.
            by_left: dict[str, list[CompositionRule]] = {}
            for rule in self.compositions:
                by_left.setdefault(rule.left, []).append(rule)
            for first in positives:
                for rule in by_left.get(first.predicate, []):
                    for second in outgoing.get(first.object, []):
                        if second.predicate != rule.right:
                            continue
                        new = self._derived(first, rule.result, first.subject, second.object, False)
                        changed = add(
                            new,
                            f"composition:{rule.left}+{rule.right}->{rule.result}",
                            [first, second],
                        ) or changed

        return closure, derivations
