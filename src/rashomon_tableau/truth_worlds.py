from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from math import exp
from typing import Iterable, Mapping, Sequence

from .truth_resolution import AuthorSet, SourceClaim, by_object


@dataclass
class TruthWorld:
    object_id: str
    values: AuthorSet
    posterior: float
    evidence_score: float
    exact_support: float
    observed: bool


def claim_compatibility(claim: AuthorSet, world: AuthorSet) -> float:
    """Compatibility used by both hard and marginal world adjudication.

    A source that omits a co-author can still support a richer world.  A source
    that asserts an author outside the world is penalized through precision.
    """
    if not claim or not world:
        return 0.0
    overlap = len(claim & world)
    precision = overlap / len(claim)
    recall = overlap / len(world)
    return 0.85 * precision + 0.15 * recall


def _clip(x: float, lo: float = 0.05, hi: float = 0.995) -> float:
    return max(lo, min(hi, x))


def candidate_truth_worlds(rows: Sequence[SourceClaim], max_worlds: int = 256, max_atoms: int = 12) -> list[AuthorSet]:
    """Generate candidate truths without consulting gold labels.

    All observed whole claims are retained.  Additional worlds are combinations
    of the most source-supported atomic authors, bounded by the largest observed
    claim cardinality.  This allows a correct world to combine compatible partial
    claims without enumerating the full power set of a noisy author vocabulary.
    """
    if not rows:
        return []
    observed = {row.values for row in rows if row.values}
    atom_support = Counter(atom for row in rows for atom in row.values)
    if not atom_support:
        return sorted(observed, key=lambda x: (len(x), tuple(sorted(x))))

    max_size = max(len(row.values) for row in rows)
    ranked_atoms = [atom for atom, _ in atom_support.most_common(max_atoms)]
    generated: list[tuple[float, AuthorSet]] = []
    for size in range(1, min(max_size, len(ranked_atoms)) + 1):
        for combo in combinations(ranked_atoms, size):
            values = frozenset(combo)
            support = sum(atom_support[a] for a in combo) / max(1, size)
            generated.append((support, values))

    generated.sort(key=lambda item: (item[0], len(item[1]), tuple(sorted(item[1]))), reverse=True)
    candidates = list(sorted(observed, key=lambda x: (len(x), tuple(sorted(x)))))
    seen = set(candidates)
    for _, values in generated:
        if values not in seen:
            candidates.append(values)
            seen.add(values)
        if len(candidates) >= max_worlds:
            break
    return candidates


def score_worlds(
    object_id: str,
    rows: Sequence[SourceClaim],
    candidates: Sequence[AuthorSet],
    reliability: Mapping[str, float],
    temperature: float = 8.0,
) -> list[TruthWorld]:
    if not rows or not candidates:
        return []
    denom = sum(reliability.get(row.source_id, 0.7) for row in rows) or 1.0
    observed = {row.values for row in rows}
    raw = []
    for values in candidates:
        compat = sum(
            reliability.get(row.source_id, 0.7) * claim_compatibility(row.values, values)
            for row in rows
        ) / denom
        exact = sum(
            reliability.get(row.source_id, 0.7) * float(row.values == values)
            for row in rows
        ) / denom
        # Exact support prevents the union of all plausible atoms from always
        # dominating, while compatibility preserves partial-source evidence.
        evidence = 0.80 * compat + 0.20 * exact
        raw.append((values, evidence, exact, values in observed))

    best = max(x[1] for x in raw)
    masses = [exp(temperature * (x[1] - best)) for x in raw]
    z = sum(masses) or 1.0
    worlds = [
        TruthWorld(object_id, values, mass / z, evidence, exact, is_observed)
        for (values, evidence, exact, is_observed), mass in zip(raw, masses)
    ]
    worlds.sort(key=lambda w: (w.posterior, w.evidence_score, len(w.values), tuple(sorted(w.values))), reverse=True)
    return worlds


def _initial_reliability(claims: Sequence[SourceClaim], prior_mean: float) -> dict[str, float]:
    return {source: prior_mean for source in sorted({c.source_id for c in claims})}


def _candidate_map(claims: Sequence[SourceClaim], max_worlds: int) -> dict[str, list[AuthorSet]]:
    return {
        object_id: candidate_truth_worlds(rows, max_worlds=max_worlds)
        for object_id, rows in by_object(claims).items()
    }


def _update_reliability(
    claims: Sequence[SourceClaim],
    world_map: Mapping[str, Sequence[TruthWorld]],
    prior_strength: float,
    prior_mean: float,
    marginal: bool,
) -> dict[str, float]:
    score_sum = defaultdict(float)
    counts = defaultdict(int)
    for claim in claims:
        worlds = world_map.get(claim.object_id, [])
        if not worlds:
            continue
        if marginal:
            score = sum(w.posterior * claim_compatibility(claim.values, w.values) for w in worlds)
        else:
            score = claim_compatibility(claim.values, worlds[0].values)
        score_sum[claim.source_id] += score
        counts[claim.source_id] += 1

    result = {}
    for source in sorted({c.source_id for c in claims}):
        result[source] = _clip(
            (score_sum[source] + prior_strength * prior_mean) /
            (counts[source] + prior_strength)
        )
    return result


def possible_world_truth_resolution(
    claims: Sequence[SourceClaim],
    mode: str = "marginal",
    iterations: int = 12,
    prior_strength: float = 4.0,
    prior_mean: float = 0.70,
    max_worlds: int = 256,
    temperature: float = 8.0,
) -> tuple[dict[str, AuthorSet], dict[str, float], dict[str, list[TruthWorld]], dict[str, list[AuthorSet]]]:
    """Resolve truth using candidate worlds and either hard or marginal reliability.

    mode='uniform': source reliabilities remain equal.
    mode='hard': reliability is updated against the current MAP world.
    mode='marginal': reliability is updated by expected compatibility over all worlds.
    """
    if mode not in {"uniform", "hard", "marginal"}:
        raise ValueError("mode must be uniform, hard, or marginal")

    grouped = by_object(claims)
    candidates = _candidate_map(claims, max_worlds)
    reliability = _initial_reliability(claims, prior_mean)
    world_map: dict[str, list[TruthWorld]] = {}

    rounds = 1 if mode == "uniform" else iterations
    for _ in range(rounds):
        world_map = {
            object_id: score_worlds(
                object_id,
                rows,
                candidates.get(object_id, []),
                reliability,
                temperature=temperature,
            )
            for object_id, rows in grouped.items()
        }
        if mode != "uniform":
            reliability = _update_reliability(
                claims,
                world_map,
                prior_strength,
                prior_mean,
                marginal=(mode == "marginal"),
            )

    # Re-score once with the final reliability estimate.
    if mode != "uniform":
        world_map = {
            object_id: score_worlds(
                object_id,
                rows,
                candidates.get(object_id, []),
                reliability,
                temperature=temperature,
            )
            for object_id, rows in grouped.items()
        }

    prediction = {
        object_id: worlds[0].values
        for object_id, worlds in world_map.items()
        if worlds
    }
    return prediction, reliability, world_map, candidates
