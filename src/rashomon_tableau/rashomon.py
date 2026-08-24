from __future__ import annotations

from itertools import combinations
from typing import Iterable

from .models import Literal
from .tableau import RelationalTableau


def minimal_unsat_subsets(facts: Iterable[Literal], reasoner: RelationalTableau, max_size: int = 4, top_k: int = 10) -> list[list[Literal]]:
    uniq = list(dict.fromkeys(facts))
    muses: list[list[Literal]] = []
    upper = min(max_size, len(uniq))
    for size in range(1, upper + 1):
        for combo in combinations(uniq, size):
            combo_set = set(combo)
            if any(set(m).issubset(combo_set) for m in muses):
                continue
            if reasoner.check(combo).satisfiable:
                continue
            minimal = True
            for idx in range(len(combo)):
                reduced = combo[:idx] + combo[idx + 1:]
                if reduced and not reasoner.check(reduced).satisfiable:
                    minimal = False
                    break
            if minimal:
                muses.append(list(combo))
                if len(muses) >= top_k:
                    return muses
    return muses


def explanation_score(mus: list[Literal]) -> float:
    perspectives = len({x.perspective for x in mus if x.perspective})
    return (1.0 / max(1, len(mus))) + 0.05 * perspectives


def rashomon_explanations(facts: Iterable[Literal], reasoner: RelationalTableau, epsilon: float = 0.1, top_k: int = 10) -> list[dict]:
    muses = minimal_unsat_subsets(facts, reasoner, top_k=top_k)
    if not muses:
        return []
    scored = [(m, explanation_score(m)) for m in muses]
    best = max(score for _, score in scored)
    keep = [(m, score) for m, score in scored if score >= best - epsilon]
    keep.sort(key=lambda x: (-x[1], len(x[0])))
    return [{"score": score, "facts": [lit.text() for lit in mus], "perspectives": sorted({lit.perspective for lit in mus if lit.perspective})} for mus, score in keep[:top_k]]
