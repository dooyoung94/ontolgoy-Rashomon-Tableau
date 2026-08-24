from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
import unicodedata
from typing import Dict, Iterable, Mapping, Sequence


AuthorSet = frozenset[str]


@dataclass(frozen=True)
class SourceClaim:
    object_id: str
    source_id: str
    values: AuthorSet


def _ascii(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def canonical_person(name: str) -> str:
    """Return a coarse identity key that is robust to 'Last, First' vs 'First Last'.

    The key deliberately uses surname + first initial.  It is a benchmark-side entity
    normalization rule, not a learned component, and is applied equally to every method.
    """
    raw = _ascii(name).lower().strip()
    if not raw:
        return ""
    raw = re.sub(r"\b(jr|sr|ii|iii|iv|phd|md|dr|prof)\.?\b", " ", raw)
    if raw in {"not available", "unknown", "n/a", "na", "none", "null"}:
        return ""

    if "," in raw:
        surname_part, given_part = raw.split(",", 1)
        surname_tokens = re.findall(r"[a-z0-9]+", surname_part)
        given_tokens = re.findall(r"[a-z0-9]+", given_part)
        surname = "".join(surname_tokens)
        first_initial = given_tokens[0][0] if given_tokens else "*"
    else:
        tokens = re.findall(r"[a-z0-9]+", raw)
        if not tokens:
            return ""
        if len(tokens) == 1:
            return f"{tokens[0]}|*"
        surname = tokens[-1]
        first_initial = tokens[0][0]

    if not surname:
        return ""
    return f"{surname}|{first_initial}"


def parse_multivalue(value: str) -> AuthorSet:
    people = []
    for part in value.split(";"):
        key = canonical_person(part)
        if key:
            people.append(key)
    return frozenset(people)


def collapse_source_object_claims(claims: Iterable[SourceClaim]) -> list[SourceClaim]:
    """Prevent one source from voting multiple times for the same object.

    If a source emitted duplicate or inconsistent rows for one object, the modal value is
    retained.  Ties prefer the more informative (larger) set and then lexical order.
    """
    grouped: dict[tuple[str, str], list[AuthorSet]] = defaultdict(list)
    for claim in claims:
        if claim.values:
            grouped[(claim.object_id, claim.source_id)].append(claim.values)

    collapsed: list[SourceClaim] = []
    for (object_id, source_id), values in grouped.items():
        counts = Counter(values)
        chosen = max(
            counts,
            key=lambda v: (counts[v], len(v), tuple(sorted(v))),
        )
        collapsed.append(SourceClaim(object_id, source_id, chosen))
    return collapsed


def by_object(claims: Iterable[SourceClaim]) -> dict[str, list[SourceClaim]]:
    out: dict[str, list[SourceClaim]] = defaultdict(list)
    for claim in claims:
        out[claim.object_id].append(claim)
    return dict(out)


def majority_set_vote(claims: Sequence[SourceClaim]) -> dict[str, AuthorSet]:
    result: dict[str, AuthorSet] = {}
    for object_id, rows in by_object(claims).items():
        counts = Counter(row.values for row in rows)
        result[object_id] = max(
            counts,
            key=lambda v: (counts[v], len(v), tuple(sorted(v))),
        )
    return result


def _clip(x: float, lo: float = 0.05, hi: float = 0.995) -> float:
    return max(lo, min(hi, x))


def reliability_weighted_set_vote(
    claims: Sequence[SourceClaim],
    iterations: int = 12,
    prior_strength: float = 4.0,
    prior_mean: float = 0.70,
) -> tuple[dict[str, AuthorSet], dict[str, float]]:
    """Iterative source-reliability baseline operating on whole claim sets.

    This is intentionally described as a reliability-weighted vote rather than as an exact
    reimplementation of TruthFinder.  A source receives credit only when its whole set equals
    the currently selected value, so partial-but-compatible multi-valued claims remain split.
    """
    source_ids = sorted({c.source_id for c in claims})
    reliability = {s: prior_mean for s in source_ids}
    grouped = by_object(claims)
    prediction: dict[str, AuthorSet] = {}

    for _ in range(iterations):
        prediction = {}
        for object_id, rows in grouped.items():
            denom = sum(reliability[r.source_id] for r in rows) or 1.0
            candidate_score: dict[AuthorSet, float] = defaultdict(float)
            for row in rows:
                candidate_score[row.values] += reliability[row.source_id] / denom
            prediction[object_id] = max(
                candidate_score,
                key=lambda v: (candidate_score[v], len(v), tuple(sorted(v))),
            )

        numer = defaultdict(float)
        count = defaultdict(int)
        for row in claims:
            numer[row.source_id] += float(row.values == prediction.get(row.object_id, frozenset()))
            count[row.source_id] += 1
        for s in source_ids:
            reliability[s] = _clip(
                (numer[s] + prior_strength * prior_mean) / (count[s] + prior_strength)
            )

    return prediction, reliability


def _claim_compatibility(claim: AuthorSet, truth: AuthorSet) -> float:
    if not claim or not truth:
        return 0.0
    overlap = len(claim & truth)
    precision = overlap / len(claim)
    recall = overlap / len(truth)
    # Missing a co-author is treated as weaker evidence, not as direct contradiction.
    return 0.85 * precision + 0.15 * recall


def logic_aware_truth_resolution(
    claims: Sequence[SourceClaim],
    relative_threshold: float = 0.35,
    iterations: int = 12,
    prior_strength: float = 4.0,
    prior_mean: float = 0.70,
) -> tuple[dict[str, AuthorSet], dict[str, float], dict[str, dict[str, float]]]:
    """Resolve multi-valued truth from provenance-preserving atomic support.

    Each claim set is interpreted as a conjunction of atomic propositions.  A subset claim is
    compatible with a richer truth rather than automatically conflicting with it.  Source
    reliability and atom confidence are estimated iteratively.  The returned atom scores are
    also an explanation trace: each selected truth can be linked back to supporting sources.
    """
    grouped = by_object(claims)
    source_ids = sorted({c.source_id for c in claims})
    reliability = {s: prior_mean for s in source_ids}
    prediction: dict[str, AuthorSet] = {}
    atom_scores: dict[str, dict[str, float]] = {}

    for _ in range(iterations):
        prediction = {}
        atom_scores = {}
        for object_id, rows in grouped.items():
            total_weight = sum(reliability[r.source_id] for r in rows) or 1.0
            support: dict[str, float] = defaultdict(float)
            max_claim_size = max((len(r.values) for r in rows), default=1)
            for row in rows:
                w = reliability[row.source_id]
                for atom in row.values:
                    support[atom] += w
            scores = {atom: val / total_weight for atom, val in support.items()}
            atom_scores[object_id] = scores
            if not scores:
                prediction[object_id] = frozenset()
                continue
            top = max(scores.values())
            cutoff = relative_threshold * top
            ranked = sorted(scores, key=lambda a: (scores[a], a), reverse=True)
            selected = [a for a in ranked if scores[a] + 1e-12 >= cutoff]
            # The largest observed claim is a conservative evidence-based cardinality cap.
            selected = selected[: max(1, max_claim_size)]
            prediction[object_id] = frozenset(selected)

        score_sum = defaultdict(float)
        count = defaultdict(int)
        for row in claims:
            truth = prediction.get(row.object_id, frozenset())
            score_sum[row.source_id] += _claim_compatibility(row.values, truth)
            count[row.source_id] += 1
        for s in source_ids:
            reliability[s] = _clip(
                (score_sum[s] + prior_strength * prior_mean) / (count[s] + prior_strength)
            )

    return prediction, reliability, atom_scores


def relation_label(claim: AuthorSet, truth: AuthorSet) -> str:
    """Classify a source claim relative to a candidate truth.

    exact: same proposition set
    partial: all asserted atoms are true, but some truth atoms are omitted
    conflict: at least one asserted atom lies outside the candidate truth
    """
    if claim == truth:
        return "exact"
    if claim and claim < truth:
        return "partial"
    return "conflict"


def set_prf(pred: AuthorSet, gold: AuthorSet) -> tuple[float, float, float]:
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    overlap = len(pred & gold)
    precision = overlap / len(pred) if pred else 0.0
    recall = overlap / len(gold) if gold else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def classification_macro_f1(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str]) -> float:
    f1s = []
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, pred))
        fp = sum(g != label and p == label for g, p in zip(gold, pred))
        fn = sum(g == label and p != label for g, p in zip(gold, pred))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        f1s.append(f1)
    return sum(f1s) / len(f1s) if f1s else 0.0
