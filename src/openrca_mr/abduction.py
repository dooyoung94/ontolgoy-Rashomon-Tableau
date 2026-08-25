from __future__ import annotations

from collections import defaultdict, deque

from .models import CausalEdge, Evidence, Hypothesis, RcaCase


class AbductiveRelationGenerator:
    """Generate missing causal-edge hypotheses without reading gold labels.

    Candidate generation uses only observable structure and telemetry:
    structural proximity, anomaly strength, and upstream-to-downstream timing.
    It intentionally generates multiple competing hypotheses instead of making
    an early single-cause commitment.
    """

    def __init__(self, max_structural_hops: int = 2, max_candidates: int = 128):
        self.max_structural_hops = max_structural_hops
        self.max_candidates = max_candidates

    def generate(self, case: RcaCase) -> list[Hypothesis]:
        nodes = sorted({e.node for e in case.evidence} | set(case.symptom_nodes))
        by_node = case.evidence_by_node()
        known = {(e.source, e.target) for e in case.known_edges}
        distances = self._distances(case.known_edges, nodes)
        hypotheses: list[Hypothesis] = []

        for source in nodes:
            src_ev = by_node.get(source, [])
            if not src_ev:
                continue
            for target in nodes:
                if source == target or (source, target) in known:
                    continue
                tgt_ev = by_node.get(target, [])
                if not tgt_ev:
                    continue

                structural = self._structural_score(source, target, distances)
                temporal = self._temporal_score(src_ev, tgt_ev)
                anomaly = self._anomaly_score(src_ev, tgt_ev)
                # At least one independent clue is required. This avoids
                # manufacturing a complete graph from unrelated observations.
                if max(structural, temporal, anomaly) < 0.5:
                    continue

                evidence_ids = sorted({x.evidence_id for x in [*src_ev, *tgt_ev]})
                explanation = (
                    f"Observed evidence suggests a possible causal propagation "
                    f"from {source} to {target}; structure={structural:.2f}, "
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
            # Structural dependency can be traversed both ways while generating
            # hypotheses; direction is recovered from temporal evidence later.
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

    def _structural_score(self, source: str, target: str, distances: dict[tuple[str, str], int]) -> float:
        distance = distances.get((source, target))
        if distance is None:
            return 0.0
        return 1.0 if distance == 1 else 0.65

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
