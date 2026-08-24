from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, order=True)
class Literal:
    predicate: str
    subject: str
    object: str
    negated: bool = False
    perspective: str | None = None
    story: str | None = None
    source: str | None = None

    def key(self) -> tuple[str, str, str, bool]:
        return (self.predicate, self.subject, self.object, self.negated)

    def positive_key(self) -> tuple[str, str, str]:
        return (self.predicate, self.subject, self.object)

    def negate(self) -> "Literal":
        return Literal(self.predicate, self.subject, self.object, not self.negated, self.perspective, self.story, self.source)

    def text(self) -> str:
        prefix = "NOT " if self.negated else ""
        return f"{prefix}{self.predicate}({self.subject}, {self.object})"


@dataclass
class Derivation:
    literal: Literal
    rule: str
    parents: list[Literal] = field(default_factory=list)


@dataclass
class Clash:
    kind: str
    literals: list[Literal]
    message: str
    rules: list[str] = field(default_factory=list)


@dataclass
class TableauResult:
    satisfiable: bool
    closure: list[Literal]
    clashes: list[Clash]
    derivations: dict[tuple[str, str, str, bool], Derivation]


@dataclass
class BenchmarkCase:
    case_id: str
    story: str
    perspective_a: str
    perspective_b: str
    label: str
    subtype: str
    facts_a: list[Literal]
    facts_b: list[Literal]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Prediction:
    case_id: str
    gold: str
    predicted: str
    subtype: str
    story: str
    perspective_a: str
    perspective_b: str
    satisfiable_a: bool
    satisfiable_b: bool
    satisfiable_union: bool
    explanation_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)
