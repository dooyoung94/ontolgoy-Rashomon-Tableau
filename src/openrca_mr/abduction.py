from __future__ import annotations

from collections import defaultdict, deque

from .models import CausalEdge, Evidence, Hypothesis, RcaCase


class AbductiveRelationGenerator:
    """Generate competing causal-edge hypotheses from observable telemetry only.

    Existing trace/dependency edges are *not* skipped: they still need to be
    judged as causal propagation candidates. Missing relations can also be
    proposed when strong temporal+anomaly evidence bridges a structural gap.
    Gold RCA labels are never read here.
    """

    def __init__(self, max_structural_hops: int = 2, max_candidates: int = 128):
        self.max_structural_hops = max_structural_hops
        self.max_candidates = max_candidates

    def generate(self, case: RcaCase) -> list[Hypothesis]:
        nodes = sorted({e.node for e in case.evidence} | set(case.symptom_nodes))
        by_node = case.evidence_by_node()
        observed_pairs = {(e.source, e.target) for e in case.known_edges}
        distances = self._distances(case.known_edges, nodes)
        hypotheses: list[Hypothesis] = []

        for source in nodes:
            src_ev = by_node.get(source, [])
            if not src_ev:
                continue
            for target in nodes:
                if source == target:
                    continue
                tgt_ev = by_node.get(target, [])
                if not tgt_ev:
                    continue

                structural = self._structural_score(source, target, distances)
                temporal = self._temporal_score(src_ev, tgt_ev)
                anomaly = self._anomaly_score(src_ev, tgt_ev)

                # Structural vicinity is the normal candidate channel. When a
                # relation was masked/missing, allow a bridge only with both
                # strong temporal ordering and strong endpoint anomalies.
                structurally_plausible = structural >= 0.65
                evidence_bridge = temporal >= 0.8 and anomaly >= 0.7
                if not (structurally_plausible or evidence_bridge):
                    continue

                evidence_ids = sorted({x.evidence_id for x in [*src_ev, *tgt_ev]})
                observed = (source, target) in observed_pairs or (target, source) in observed_pairs
                explanation = (
                    f"Possible causal propagation from {source} to {target}; "
                    f"observed_dependency={observed}, structure={structural:.2f}, "
                    f"temporal={temporal:.2f}, anomaly={anomaly:.2f}."
                )
                hypotheses.append(
                    Hypothesis(
                        edge=CausalEdge(source, "causal_propagates_to", target),
                        evidence_ids=evidence_ids,
                        explanation=explanation,
                        structural_score=structural,
                        temporal_score=temporal,
                        anomaly_score=anomaly,
                    )
                )

        hypotheses.sort(key=lambda h: h.abductive_score, reverse=True)
        return hypotheses[: self.max_candidates]

    def _distances(self, edges: list[CausalEdge], nodes: list[str]) -> dict[tuple[str, str], int]:
        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            # Dependency adjacency is undirected for candidate discovery because
            # fault propagation can run opposite to the request/call direction.
            adjacency[edge.source].add(edge.target)
            adjacency[edge.target].add(edge.source)

        out: dict[tuple[str, str], int] = {}
        for start in nodes:
            queue = deque([(start, 0)])
            seen = {start}
            while queue:
                node, depth = queue.popleft()
                if depth >= self.max_structural_hops:
                    continue
                for nxt in adjacency.get(node, set()):
                    if nxt in seen:
                        continue
                    seen.add(nxt)
                    out[(start, nxt)] = depth + 1
                    queue.append((nxt, depth + 1))
        return out

    @staticmethod
    def _structural_score(source: str, target: str, distances: dict[tuple[str, str], int]) -> float:
        distance = distances.get((source, target))
        if distance is None:
            return 0.0
        if distance == 1:
            return 1.0
        if distance == 2:
            return 0.65
        return 0.0

    @staticmethod
    def _temporal_score(source: list[Evidence], target: list[Evidence]) -> float:
        src = [x.timestamp for x in source if x.timestamp is not None and x.is_anomalous]
        tgt = [x.timestamp for x in target if x.timestamp is not None and x.is_anomalous]
        if not src or not tgt:
            return 0.0
        delta = min(tgt) - min(src)
        if delta < 0:
            return 0.0
        if delta <= 5:
            return 1.0
        if delta <= 30:
            return 0.8
        if delta <= 120:
            return 0.55
        return 0.2

    @staticmethod
    def _anomaly_score(source: list[Evidence], target: list[Evidence]) -> float:
        src = max((x.abnormality for x in source), default=0.0)
        tgt = max((x.abnormality for x in target), default=0.0)
        return min(src, tgt)
