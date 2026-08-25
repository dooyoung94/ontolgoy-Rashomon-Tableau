from __future__ import annotations

import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .models import Literal
from .ontology import Ontology


@dataclass(frozen=True)
class TraversalEdge:
    literal: Literal
    from_entity: str
    to_entity: str
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
        return " | ".join(
            f"{'NOT ' if lit.negated else ''}{lit.subject} -[{lit.predicate}]-> {lit.object}"
            for lit in self.literals
        )


def canonical_entity(value: str) -> str:
    """Conservative entity key used only for graph connectivity.

    Surface text on Literal is never rewritten. The key removes Unicode accents,
    case differences and punctuation/spacing differences, so e.g. `Méditerranée`
    and `Mediterranee` resolve to the same graph node.
    """
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _default_ontology() -> Ontology:
    """Load reusable MAGIC relation semantics when running from the repository.

    The YAML contains relation-level semantics only (symmetry/inverses/etc.), not
    example IDs or gold answers. Falling back to an empty ontology keeps the module
    usable when installed independently of the repository config directory.
    """
    path = Path("config/magic_ontology_rules.yaml")
    return Ontology.from_yaml(path) if path.exists() else Ontology()


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
    """Create connectivity edges while preserving semantic evidence.

    Every asserted fact can be traversed structurally in either direction because
    retrieval asks only whether facts form a connected candidate explanation. The
    original Literal is preserved on a structural reverse, so no false inverse fact
    is shown to the scorer. For ontology-declared symmetric/inverse predicates, the
    semantically valid reversed Literal is used instead.
    """
    ontology = ontology or _default_ontology()
    out: list[TraversalEdge] = []
    seen: set[tuple] = set()

    def add(lit: Literal, from_entity: str, to_entity: str, rule: str) -> None:
        key = (
            lit.predicate,
            canonical_entity(lit.subject),
            canonical_entity(lit.object),
            lit.negated,
            canonical_entity(from_entity),
            canonical_entity(to_entity),
            lit.story,
            lit.source,
            rule,
        )
        if key in seen:
            return
        seen.add(key)
        out.append(TraversalEdge(lit, from_entity, to_entity, rule))

    for lit in facts:
        add(lit, lit.subject, lit.object, "asserted")

        if lit.predicate in ontology.symmetric:
            rev = _derived_reverse(lit, lit.predicate)
            add(rev, lit.object, lit.subject, f"symmetry:{lit.predicate}")
        else:
            inverse = ontology.inverse.get(lit.predicate)
            if inverse:
                rev = _derived_reverse(lit, inverse)
                add(rev, lit.object, lit.subject, f"inverse:{lit.predicate}->{inverse}")
            else:
                # Connectivity-only reverse: keep the asserted proposition unchanged.
                add(lit, lit.object, lit.subject, "structural_reverse")
    return out


def _bounded_paths(
    edges: Iterable[TraversalEdge],
    start: str,
    goal: str,
    max_hops: int,
) -> list[tuple[list[Literal], list[str]]]:
    adjacency: dict[str, list[TraversalEdge]] = {}
    for edge in edges:
        adjacency.setdefault(canonical_entity(edge.from_entity), []).append(edge)

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
            next_node = canonical_entity(edge.to_entity)
            next_path = path + [edge.literal]
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
    """Retrieve signed, ontology-aware connected evidence paths.

    Entity matching is canonicalized, negated facts remain evidence, and graph
    connectivity can be traversed in either direction without inventing semantic
    inverses. Declared symmetric/inverse relations use their valid reversed form.
    Candidate generation is deliberately separate from contradiction judgment.
    """
    edges = _traversal_edges(list(facts), ontology)
    forward = _bounded_paths(edges, subject, object_, max_hops)[:max_paths_per_direction]
    reverse = _bounded_paths(edges, object_, subject, max_hops)[:max_paths_per_direction]

    candidates = [
        CandidatePath("FORWARD", literals, rules) for literals, rules in forward
    ] + [
        CandidatePath("REVERSE", literals, rules) for literals, rules in reverse
    ]

    # Deduplicate paths that are the same evidence set reached from both endpoint
    # orientations while preserving the first deterministic traversal.
    deduped: list[CandidatePath] = []
    seen: set[tuple] = set()
    for path in candidates:
        signature = tuple(
            (lit.predicate, canonical_entity(lit.subject), canonical_entity(lit.object), lit.negated)
            for lit in path.literals
        )
        unordered_signature = tuple(sorted(signature))
        if unordered_signature in seen:
            continue
        seen.add(unordered_signature)
        deduped.append(path)
    return deduped
