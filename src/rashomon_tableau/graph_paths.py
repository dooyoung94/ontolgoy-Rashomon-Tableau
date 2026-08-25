from __future__ import annotations

import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from .models import Literal
from .ontology import Ontology


@dataclass(frozen=True)
class TraversalEdge:
    literal: Literal
    rule: str = "asserted"


@dataclass
class CandidatePath:
    direction: str
    literals: list[Literal]
    traversal_rules: list[str] = field(default_factory=list)

    @property
    def hop_count(self) -> int:
        return len(self.literals)

    @property
    def negated_hops(self) -> int:
        return sum(1 for lit in self.literals if lit.negated)

    def text(self) -> str:
        if not self.literals:
            return ""
        parts = [self.literals[0].subject]
        for lit in self.literals:
            sign = "NOT " if lit.negated else ""
            parts.append(f"-[{sign}{lit.predicate}]->")
            parts.append(lit.object)
        return " ".join(parts)


def canonical_entity(value: str) -> str:
    """Conservative entity key used only for graph connectivity.

    The original surface form remains on each Literal for scoring/audit.  The key
    removes Unicode accents, case differences and punctuation/spacing differences,
    so e.g. `Méditerranée` and `Mediterranee` resolve to the same graph node.
    """
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _derived_reverse(lit: Literal, predicate: str) -> Literal:
    return Literal(
        predicate=predicate,
        subject=lit.object,
        object=lit.subject,
        negated=lit.negated,
        perspective=lit.perspective,
        story=lit.story,
        source=lit.source,
    )


def _traversal_edges(facts: Iterable[Literal], ontology: Ontology | None) -> list[TraversalEdge]:
    """Build asserted + logically reversible edges without collapsing the path.

    We intentionally do not materialize transitive/composition closure here: the
    candidate scorer should see the original multi-hop evidence. Symmetry/inverse
    rules only provide a legal traversal orientation while preserving sentence
    provenance and negation polarity.
    """
    ontology = ontology or Ontology()
    out: list[TraversalEdge] = []
    seen: set[tuple] = set()

    def add(lit: Literal, rule: str) -> None:
        key = (
            lit.predicate,
            canonical_entity(lit.subject),
            canonical_entity(lit.object),
            lit.negated,
            lit.story,
            lit.source,
        )
        if key in seen:
            return
        seen.add(key)
        out.append(TraversalEdge(lit, rule))

    for lit in facts:
        add(lit, "asserted")
        if lit.predicate in ontology.symmetric:
            add(_derived_reverse(lit, lit.predicate), f"symmetry:{lit.predicate}")
        inverse = ontology.inverse.get(lit.predicate)
        if inverse:
            add(_derived_reverse(lit, inverse), f"inverse:{lit.predicate}->{inverse}")
    return out


def _bounded_paths(
    edges: Iterable[TraversalEdge],
    start: str,
    goal: str,
    max_hops: int,
) -> list[tuple[list[Literal], list[str]]]:
    adjacency: dict[str, list[TraversalEdge]] = {}
    for edge in edges:
        adjacency.setdefault(canonical_entity(edge.literal.subject), []).append(edge)

    start_key = canonical_entity(start)
    goal_key = canonical_entity(goal)
    if not start_key or not goal_key:
        return []

    out: list[tuple[list[Literal], list[str]]] = []
    queue = deque([(start_key, [], [], {start_key})])
    while queue:
        node, path, rules, visited = queue.popleft()
        if len(path) >= max_hops:
            continue
        for edge in adjacency.get(node, []):
            lit = edge.literal
            next_node = canonical_entity(lit.object)
            next_path = path + [lit]
            next_rules = rules + [edge.rule]
            if next_node == goal_key:
                out.append((next_path, next_rules))
                continue
            if not next_node or next_node in visited:
                continue
            queue.append((next_node, next_path, next_rules, visited | {next_node}))
    return out


def bidirectional_candidate_paths(
    facts: Iterable[Literal],
    subject: str,
    object_: str,
    max_hops: int = 4,
    max_paths_per_direction: int = 20,
    ontology: Ontology | None = None,
) -> list[CandidatePath]:
    """Retrieve signed semantic candidate paths in both graph directions.

    Entity matching is canonicalized, negated facts remain traversable evidence,
    and ontology-declared symmetric/inverse predicates may be traversed in their
    logically equivalent direction. This function only generates candidates; it
    does not declare a path supportive or contradictory.
    """
    edges = _traversal_edges(list(facts), ontology)
    forward = _bounded_paths(edges, subject, object_, max_hops)[:max_paths_per_direction]
    reverse = _bounded_paths(edges, object_, subject, max_hops)[:max_paths_per_direction]
    return [
        CandidatePath("FORWARD", literals, rules) for literals, rules in forward
    ] + [
        CandidatePath("REVERSE", literals, rules) for literals, rules in reverse
    ]
