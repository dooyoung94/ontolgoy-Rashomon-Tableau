from __future__ import annotations

from dataclasses import dataclass, field
from math import log
from typing import Iterable, Sequence

from .models import Literal
from .ontology import Ontology
from .tableau import RelationalTableau


@dataclass(frozen=True)
class RelationCandidate:
    """One plausible interpretation of a missing relation over one multi-hop path.

    ``score`` is model-agnostic semantic plausibility in [0, 1]. It may come from
    DeBERTa NLI, a KGE model, an LLM, or a calibrated combination. The core method
    never assumes which scorer produced it.
    """

    relation: str
    score: float
    path: tuple[Literal, ...] = ()
    support: float | None = None
    contradiction: float | None = None
    unresolved: float | None = None
    origin: str = "candidate"

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be in [0, 1]")


@dataclass
class RelationWorld:
    """A single (path, relation) completion world checked by Tableau."""

    world_id: str
    head: str
    tail: str
    candidate: RelationCandidate
    candidate_literal: Literal
    satisfiable: bool
    clashes: list[str] = field(default_factory=list)
    weight: float = 0.0

    @property
    def relation(self) -> str:
        return self.candidate.relation

    @property
    def path(self) -> tuple[Literal, ...]:
        return self.candidate.path


@dataclass
class CompletionResult:
    """Rashomon-Tableau result for one missing head-relation-tail query."""

    head: str
    tail: str
    all_candidates: list[RelationCandidate]
    rashomon_candidates: list[RelationCandidate]
    valid_worlds: list[RelationWorld]
    rejected_worlds: list[RelationWorld]
    relation_marginal: dict[str, float]
    entropy: float
    top_relation: str | None

    @property
    def candidate_coverage(self) -> int:
        return len(self.rashomon_candidates)

    @property
    def valid_world_ratio(self) -> float:
        total = len(self.valid_worlds) + len(self.rejected_worlds)
        return len(self.valid_worlds) / total if total else 0.0


def select_rashomon_candidates(
    candidates: Sequence[RelationCandidate],
    *,
    epsilon: float = 0.05,
    min_score: float = 0.0,
) -> list[RelationCandidate]:
    """Retain near-optimal relation interpretations instead of early Top-1 commit.

    R_epsilon(q) = {c : score(c) >= max_score - epsilon and score(c) >= min_score}
    """
    if epsilon < 0:
        raise ValueError("epsilon must be >= 0")
    if not 0.0 <= min_score <= 1.0:
        raise ValueError("min_score must be in [0, 1]")
    if not candidates:
        return []

    best = max(candidate.score for candidate in candidates)
    threshold = max(min_score, best - epsilon)
    retained = [candidate for candidate in candidates if candidate.score >= threshold]
    return sorted(
        retained,
        key=lambda candidate: (-candidate.score, candidate.relation, _path_signature(candidate.path)),
    )


def complete_missing_relation(
    base_facts: Iterable[Literal],
    head: str,
    tail: str,
    candidates: Sequence[RelationCandidate],
    ontology: Ontology,
    *,
    epsilon: float = 0.05,
    min_score: float = 0.0,
) -> CompletionResult:
    """Construct Rashomon worlds, reject inconsistent worlds, and marginalize.

    Each retained candidate creates a world W = G_obs ∪ {(head, relation, tail)}.
    Tableau decides whether O ∪ W is satisfiable. Only satisfiable worlds receive
    posterior mass. Multiple paths supporting the same relation remain separate
    worlds and are marginalized back to relation probability at the end.
    """
    facts = list(dict.fromkeys(base_facts))
    retained = select_rashomon_candidates(candidates, epsilon=epsilon, min_score=min_score)
    reasoner = RelationalTableau(ontology)

    valid: list[RelationWorld] = []
    rejected: list[RelationWorld] = []
    for index, candidate in enumerate(retained, start=1):
        proposed = Literal(candidate.relation, head, tail, False, source="rashomon_completion")
        result = reasoner.check([*facts, proposed])
        world = RelationWorld(
            world_id=f"W{index}",
            head=head,
            tail=tail,
            candidate=candidate,
            candidate_literal=proposed,
            satisfiable=result.satisfiable,
            clashes=[clash.message for clash in result.clashes],
        )
        if result.satisfiable:
            valid.append(world)
        else:
            rejected.append(world)

    _normalize_world_weights(valid)
    marginal: dict[str, float] = {}
    for world in valid:
        marginal[world.relation] = marginal.get(world.relation, 0.0) + world.weight
    marginal = dict(sorted(marginal.items(), key=lambda item: (-item[1], item[0])))

    entropy = -sum(prob * log(prob) for prob in marginal.values() if prob > 0.0)
    top_relation = next(iter(marginal), None)
    return CompletionResult(
        head=head,
        tail=tail,
        all_candidates=list(candidates),
        rashomon_candidates=retained,
        valid_worlds=valid,
        rejected_worlds=rejected,
        relation_marginal=marginal,
        entropy=entropy,
        top_relation=top_relation,
    )


def candidates_from_nli(
    relations: Sequence[str],
    paths: Sequence[Sequence[Literal]],
    scores: Sequence[tuple[float, float, float]],
    *,
    origin: str = "deberta-nli",
) -> list[RelationCandidate]:
    """Build relation candidates from external NLI S/C/U values.

    This helper intentionally accepts scores rather than importing a concrete model.
    DeBERTa remains an interchangeable semantic scorer, not part of the symbolic
    Rashomon-Tableau core.
    """
    if not (len(relations) == len(paths) == len(scores)):
        raise ValueError("relations, paths and scores must have identical lengths")

    out: list[RelationCandidate] = []
    for relation, path, (support, contradiction, unresolved) in zip(relations, paths, scores):
        total = max(1e-12, support + contradiction + unresolved)
        s = support / total
        c = contradiction / total
        u = unresolved / total
        out.append(
            RelationCandidate(
                relation=relation,
                score=s,
                path=tuple(path),
                support=s,
                contradiction=c,
                unresolved=u,
                origin=origin,
            )
        )
    return out


def _normalize_world_weights(worlds: list[RelationWorld]) -> None:
    if not worlds:
        return
    total = sum(max(world.candidate.score, 1e-12) for world in worlds)
    for world in worlds:
        world.weight = max(world.candidate.score, 1e-12) / total


def _path_signature(path: Sequence[Literal]) -> tuple:
    return tuple((lit.subject, lit.predicate, lit.object, lit.negated) for lit in path)
