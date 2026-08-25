from __future__ import annotations

from dataclasses import dataclass
import re

from .models import CausalEdge


@dataclass(frozen=True)
class EdgeMetrics:
    precision: float
    recall: float
    f1: float


def normalize_service(name: str) -> str:
    """Normalize service identities for OpenRCA2 process evaluation."""
    value = str(name).strip().lower()
    value = re.sub(r"^(?:service[:/]|svc[:/])", "", value)
    if value.startswith("ts-"):
        value = value[3:]
    value = value.replace("-", "").replace("_", "")
    return value


def is_loadgen(name: str) -> bool:
    value = normalize_service(name)
    return "loadgen" in value or "loadgenerator" in value


def _pair_set(edges) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for edge in edges:
        if isinstance(edge, CausalEdge):
            source, target = edge.source, edge.target
        else:
            source, _, target = edge
        if is_loadgen(source) or is_loadgen(target):
            continue
        out.add((normalize_service(source), normalize_service(target)))
    return out


def service_edge_metrics(predicted, gold) -> EdgeMetrics:
    """Directed service-pair F1; relation labels are intentionally ignored."""
    p = _pair_set(predicted)
    g = _pair_set(gold)
    tp = len(p & g)
    precision = tp / len(p) if p else 0.0
    recall = tp / len(g) if g else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return EdgeMetrics(precision, recall, f1)


def edge_metrics(predicted, gold) -> EdgeMetrics:
    return service_edge_metrics(predicted, gold)


def node_metrics(predicted_edges, gold_edges) -> EdgeMetrics:
    p_pairs = _pair_set(predicted_edges)
    g_pairs = _pair_set(gold_edges)
    p = {x for pair in p_pairs for x in pair}
    g = {x for pair in g_pairs for x in pair}
    tp = len(p & g)
    precision = tp / len(p) if p else 0.0
    recall = tp / len(g) if g else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return EdgeMetrics(precision, recall, f1)


def root_hit_at_k(predicted: list[str], gold: list[str], k: int) -> float:
    p = {normalize_service(x) for x in predicted[:k]}
    g = {normalize_service(x) for x in gold}
    return float(bool(p & g))


def exact_root_set(predicted: list[str], gold: list[str]) -> float:
    return float({normalize_service(x) for x in predicted} == {normalize_service(x) for x in gold})


def process_path_reachability(predicted_edges, predicted_roots: list[str], gold_roots: list[str], gold_alarm_nodes: list[str]) -> float:
    """Case-level PR: correct predicted root plus a directed path to a gold alarm."""
    adjacency: dict[str, set[str]] = {}
    for source, target in _pair_set(predicted_edges):
        adjacency.setdefault(source, set()).add(target)

    correct_roots = {normalize_service(x) for x in predicted_roots} & {normalize_service(x) for x in gold_roots}
    alarms = {normalize_service(x) for x in gold_alarm_nodes if not is_loadgen(x)}
    if not correct_roots or not alarms:
        return 0.0

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

    return float(any(reachable(root, alarm) for root in correct_roots for alarm in alarms))


def path_reachability(predicted_edges, roots: list[str], symptoms: list[str]) -> float:
    """Legacy graph-only reachability diagnostic; not the official PR metric."""
    adjacency: dict[str, set[str]] = {}
    for source, target in _pair_set(predicted_edges):
        adjacency.setdefault(source, set()).add(target)

    def reachable(start: str, goal: str) -> bool:
        start, goal = normalize_service(start), normalize_service(goal)
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
