from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from .models import Derivation, Literal


@dataclass
class Ontology:
    symmetric: set[str] = field(default_factory=set)
    inverse: dict[str, str] = field(default_factory=dict)
    hierarchy: dict[str, set[str]] = field(default_factory=dict)
    incompatible: set[tuple[str, str]] = field(default_factory=set)
    exclusive: set[str] = field(default_factory=set)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Ontology":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        symmetric = set(data.get("symmetric", []))
        inverse = dict(data.get("inverse", {}))
        hierarchy = {k: set(v or []) for k, v in (data.get("hierarchy", {}) or {}).items()}
        incompatible = set()
        for pair in data.get("incompatible", []) or []:
            if len(pair) == 2:
                a, b = pair
                incompatible.add((a, b)); incompatible.add((b, a))
        exclusive = set(data.get("exclusive", []))
        return cls(symmetric, inverse, hierarchy, incompatible, exclusive)

    def forward_chain(self, facts: Iterable[Literal]):
        closure = set(facts)
        derivations = {lit.key(): Derivation(lit, "asserted", []) for lit in closure}
        changed = True
        while changed:
            changed = False
            for lit in list(closure):
                if lit.negated:
                    continue
                if lit.predicate in self.symmetric:
                    new = Literal(lit.predicate, lit.object, lit.subject, False, lit.perspective, lit.story, lit.source)
                    if new not in closure:
                        closure.add(new); derivations[new.key()] = Derivation(new, f"symmetry:{lit.predicate}", [lit]); changed = True
                inv = self.inverse.get(lit.predicate)
                if inv:
                    new = Literal(inv, lit.object, lit.subject, False, lit.perspective, lit.story, lit.source)
                    if new not in closure:
                        closure.add(new); derivations[new.key()] = Derivation(new, f"inverse:{lit.predicate}->{inv}", [lit]); changed = True
                for parent in self.hierarchy.get(lit.predicate, set()):
                    new = Literal(parent, lit.subject, lit.object, False, lit.perspective, lit.story, lit.source)
                    if new not in closure:
                        closure.add(new); derivations[new.key()] = Derivation(new, f"hierarchy:{lit.predicate}->{parent}", [lit]); changed = True
        return closure, derivations
