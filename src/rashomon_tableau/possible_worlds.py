from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from math import prod
from typing import Iterable, Mapping, Sequence

from .models import Literal
from .tableau import RelationalTableau


@dataclass(frozen=True)
class RelationHypothesis:
    """A defeasible interpretation of a two-hop relation composition."""

    name: str
    left: str
    right: str
    result: str
    confidence: float
    negated_result: bool = False
    origin: str = "candidate"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")

    def derive(self, facts: Iterable[Literal]) -> list[Literal]:
        positives = [fact for fact in facts if not fact.negated]
        derived: list[Literal] = []
        for first in positives:
            if first.predicate != self.left:
                continue
            for second in positives:
                if second.predicate != self.right or first.object != second.subject:
                    continue
                source = first.source if first.source == second.source else None
                perspective = first.perspective if first.perspective == second.perspective else None
                story = first.story if first.story == second.story else None
                derived.append(
                    Literal(self.result, first.subject, second.object, self.negated_result, perspective, story, source)
                )
        return list(dict.fromkeys(derived))


@dataclass(frozen=True)
class PathRelationHypothesis:
    """A defeasible interpretation of one arbitrary multi-hop path pattern.

    ``start``/``end`` bind the hypothesis to the retrieved candidate endpoints so
    the same relation sequence elsewhere in the graph cannot create unrelated
    claims. ``swap_endpoints`` represents a reverse candidate path while deriving
    the proposition in the query's canonical subject/object direction.
    """

    name: str
    relations: tuple[str, ...]
    result: str
    confidence: float
    negated_result: bool = False
    origin: str = "path-candidate"
    start: str | None = None
    end: str | None = None
    swap_endpoints: bool = False

    def __post_init__(self) -> None:
        if not self.relations:
            raise ValueError("relations must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")

    def derive(self, facts: Iterable[Literal]) -> list[Literal]:
        positives = [fact for fact in facts if not fact.negated]
        adjacency: dict[str, list[Literal]] = {}
        for fact in positives:
            adjacency.setdefault(fact.subject, []).append(fact)

        derived: list[Literal] = []

        def walk(path_start: str, node: str, index: int, chain: list[Literal]) -> None:
            if index == len(self.relations):
                if not chain or (self.end is not None and node != self.end):
                    return
                sources = {edge.source for edge in chain if edge.source}
                source = next(iter(sources)) if len(sources) == 1 else None
                subject, object_ = (node, path_start) if self.swap_endpoints else (path_start, node)
                derived.append(Literal(self.result, subject, object_, self.negated_result, source=source))
                return
            expected = self.relations[index]
            for edge in adjacency.get(node, []):
                if edge.predicate == expected:
                    walk(path_start, edge.object, index + 1, [*chain, edge])

        starts = [self.start] if self.start is not None else list(adjacency)
        for path_start in starts:
            if path_start in adjacency:
                walk(path_start, path_start, 0, [])
        return list(dict.fromkeys(derived))


@dataclass(frozen=True)
class WorldChoice:
    hypothesis: RelationHypothesis | PathRelationHypothesis | None
    label: str
    confidence: float

    @staticmethod
    def unresolved(label: str = "UNRESOLVED", confidence: float = 1.0) -> "WorldChoice":
        return WorldChoice(None, label, confidence)


@dataclass
class PossibleWorld:
    world_id: str
    base_facts: list[Literal]
    derived_facts: list[Literal]
    choices: list[WorldChoice]
    satisfiable: bool
    weight: float
    source_support: float
    relation_support: float
    metadata: dict = field(default_factory=dict)

    @property
    def facts(self) -> list[Literal]:
        return list(dict.fromkeys([*self.base_facts, *self.derived_facts]))


@dataclass
class TruthMarginal:
    query: Literal
    support: float
    contradiction: float
    unresolved: float
    both: float
    world_count: int
    winning_status: str
    worlds: list[PossibleWorld] = field(default_factory=list)


def build_possible_worlds(
    base_facts: Iterable[Literal],
    alternative_groups: Sequence[Sequence[WorldChoice]],
    reasoner: RelationalTableau,
    source_reliability: Mapping[str, float] | None = None,
    max_worlds: int = 256,
) -> list[PossibleWorld]:
    facts = list(dict.fromkeys(base_facts))
    source_reliability = source_reliability or {}
    groups = [list(group) for group in alternative_groups if group]
    combinations = product(*groups) if groups else [tuple()]

    worlds: list[PossibleWorld] = []
    for index, selected in enumerate(combinations):
        if index >= max_worlds:
            break
        selected = list(selected)
        derived: list[Literal] = []
        for choice in selected:
            if choice.hypothesis is not None:
                derived.extend(choice.hypothesis.derive([*facts, *derived]))
        derived = list(dict.fromkeys(derived))
        combined = [*facts, *derived]
        tableau_result = reasoner.check(combined)
        if not tableau_result.satisfiable:
            continue

        relation_support = prod(max(1e-9, choice.confidence) for choice in selected) if selected else 1.0
        sources = sorted({fact.source for fact in combined if fact.source})
        if sources:
            source_support = prod(max(1e-9, source_reliability.get(source, 0.5)) for source in sources) ** (1.0 / len(sources))
        else:
            source_support = 1.0
        weight = relation_support * source_support
        worlds.append(
            PossibleWorld(
                world_id=f"W{len(worlds) + 1}",
                base_facts=facts,
                derived_facts=derived,
                choices=selected,
                satisfiable=True,
                weight=weight,
                source_support=source_support,
                relation_support=relation_support,
                metadata={"sources": sources},
            )
        )

    total = sum(world.weight for world in worlds)
    if worlds and total > 0:
        for world in worlds:
            world.weight /= total
    return worlds


def truth_marginal(worlds: Sequence[PossibleWorld], query: Literal, reasoner: RelationalTableau) -> TruthMarginal:
    mass = {"SUPPORTED": 0.0, "CONTRADICTED": 0.0, "UNRESOLVED": 0.0, "BOTH": 0.0}
    for world in worlds:
        status = reasoner.verify(world.facts, query).status
        mass[status] += world.weight
    if not worlds:
        mass["UNRESOLVED"] = 1.0
    winner = max(mass.items(), key=lambda item: item[1])[0]
    return TruthMarginal(
        query=query,
        support=mass["SUPPORTED"],
        contradiction=mass["CONTRADICTED"],
        unresolved=mass["UNRESOLVED"],
        both=mass["BOTH"],
        world_count=len(worlds),
        winning_status=winner,
        worlds=list(worlds),
    )
