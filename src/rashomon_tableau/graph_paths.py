from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from .models import Literal


@dataclass
class CandidatePath:
    direction: str
    literals: list[Literal]

    @property
    def hop_count(self) -> int:
        return len(self.literals)

    def text(self) -> str:
        if not self.literals:
            return ""
        parts = [self.literals[0].subject]
        for lit in self.literals:
            parts.append(f"-[{lit.predicate}]->")
            parts.append(lit.object)
        return " ".join(parts)


def _bounded_paths(facts: Iterable[Literal], start: str, goal: str, max_hops: int) -> list[list[Literal]]:
    adjacency: dict[str, list[Literal]] = {}
    for lit in facts:
        if lit.negated:
            continue
        adjacency.setdefault(lit.subject, []).append(lit)

    out: list[list[Literal]] = []
    queue = deque([(start, [], {start})])
    while queue:
        node, path, visited = queue.popleft()
        if len(path) >= max_hops:
            continue
        for edge in adjacency.get(node, []):
            next_node = edge.object
            next_path = path + [edge]
            if next_node == goal:
                out.append(next_path)
                continue
            if next_node in visited:
                continue
            queue.append((next_node, next_path, visited | {next_node}))
    return out


def bidirectional_candidate_paths(
    facts: Iterable[Literal],
    subject: str,
    object_: str,
    max_hops: int = 4,
    max_paths_per_direction: int = 20,
) -> list[CandidatePath]:
    """Retrieve causal/conflict candidates in both graph directions.

    This function does not declare a path true or causal. It only retrieves candidate paths.
    Semantic validation belongs to the ontology-guided tableau layer.
    """
    materialized = list(facts)
    forward = _bounded_paths(materialized, subject, object_, max_hops)[:max_paths_per_direction]
    reverse = _bounded_paths(materialized, object_, subject, max_hops)[:max_paths_per_direction]
    return [CandidatePath("FORWARD", p) for p in forward] + [CandidatePath("REVERSE", p) for p in reverse]
