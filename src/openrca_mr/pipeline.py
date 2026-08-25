from __future__ import annotations

from dataclasses import dataclass

from .abduction import AbductiveRelationGenerator
from .models import Hypothesis, RcaCase
from .semantic import apply_semantic_scores


@dataclass
class RcaPrediction:
    case_id: str
    ranked_hypotheses: list[Hypothesis]
    predicted_root_causes: list[str]
    predicted_edges: list[tuple[str, str, str]]


class MissingRelationRCA:
    """Composable RCA pipeline used by all ablations."""

    def __init__(
        self,
        generator: AbductiveRelationGenerator | None = None,
        semantic_scorer=None,
        global_inference=None,
        edge_threshold: float = 0.5,
        max_root_causes: int = 3,
    ):
        self.generator = generator or AbductiveRelationGenerator()
        self.semantic_scorer = semantic_scorer
        self.global_inference = global_inference
        self.edge_threshold = edge_threshold
        self.max_root_causes = max_root_causes

    def run(self, case: RcaCase) -> RcaPrediction:
        hypotheses = self.generator.generate(case)
        if self.semantic_scorer is not None:
            hypotheses = apply_semantic_scores(case, hypotheses, self.semantic_scorer)
        if self.global_inference is not None:
            hypotheses = self.global_inference.infer(case, hypotheses)
        else:
            hypotheses.sort(key=lambda h: h.final_score, reverse=True)

        selected = [h for h in hypotheses if h.final_score >= self.edge_threshold]
        predicted_edges = [h.edge.key() for h in selected]
        roots = self._rank_roots(case, selected)
        return RcaPrediction(
            case_id=case.case_id,
            ranked_hypotheses=hypotheses,
            predicted_root_causes=roots[: self.max_root_causes],
            predicted_edges=predicted_edges,
        )

    @staticmethod
    def _rank_roots(case: RcaCase, hypotheses: list[Hypothesis]) -> list[str]:
        """Rank root-like source nodes without using gold labels.

        A plausible root is anomalous early, has strong outgoing causal mass,
        and has little incoming causal support. This avoids ranking every middle
        node of a high-scoring path as an equally likely root.
        """
        symptoms = set(case.symptom_nodes)
        by_node = case.evidence_by_node()
        nodes = {h.edge.source for h in hypotheses if h.edge.source not in symptoms}
        if not nodes:
            return []

        outgoing: dict[str, float] = {node: 0.0 for node in nodes}
        incoming: dict[str, float] = {node: 0.0 for node in nodes}
        for h in hypotheses:
            score = h.final_score
            if h.edge.source in nodes:
                outgoing[h.edge.source] = max(outgoing[h.edge.source], score)
            if h.edge.target in nodes:
                incoming[h.edge.target] = max(incoming[h.edge.target], score)

        first_times: dict[str, float] = {}
        anomaly: dict[str, float] = {}
        for node in nodes:
            items = by_node.get(node, [])
            anomaly[node] = max((e.abnormality for e in items), default=0.0)
            times = [e.timestamp for e in items if e.timestamp is not None and e.is_anomalous]
            if times:
                first_times[node] = min(times)

        if first_times:
            lo, hi = min(first_times.values()), max(first_times.values())
            span = max(hi - lo, 1e-9)
        else:
            lo, span = 0.0, 1.0

        ranked: list[tuple[str, float]] = []
        for node in nodes:
            early = 1.0 - ((first_times[node] - lo) / span) if node in first_times else 0.0
            rootness = (
                0.38 * outgoing[node]
                + 0.30 * anomaly[node]
                + 0.20 * early
                + 0.12 * (1.0 - incoming[node])
            )
            ranked.append((node, rootness))
        ranked.sort(key=lambda x: (-x[1], x[0]))
        return [node for node, _ in ranked]
