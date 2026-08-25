from __future__ import annotations

from dataclasses import dataclass

from .models import CausalEdge


@dataclass(frozen=True)
class EdgeMetrics:
    precision: float
    recall: float
    f1: float


def edge_metrics(predicted: list[tuple[str, str, str]], gold: list[CausalEdge]) -> EdgeMetrics:
    p = set(predicted)
    g = {edge.key() for edge in gold}
    tp = len(p & g)
    precision = tp / len(p) if p else 0.0
    recall = tp / len(g) if g else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return EdgeMetrics(precision, recall, f1)


def root_hit_at_k(predicted: list[str], gold: list[str], k: int) -> float:
    return float(bool(set(predicted[:k]) & set(gold)))


def exact_root_set(predicted: list[str], gold: list[str]) -> float:
    return float(set(predicted) == set(gold))


def path_reachability(predicted_edges: list[tuple[str, str, str]], roots: list[str], symptoms: list[str]) -> float:
    adjacency: dict[str, set[str]] = {}
    for source, _, target in predicted_edges:
        adjacency.setdefault(source, set()).add(target)

    def reachable(start: str, goal: str) -> bool:
        stack = [start]
        seen = {start}
        while stack:
            node = stack.pop()
            if node == goal:
                return True
            for nxt in adjacency.get(node, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False

    if not roots or not symptoms:
        return 0.0
    checks = [reachable(root, symptom) for root in roots for symptom in symptoms]
    return sum(checks) / len(checks)
