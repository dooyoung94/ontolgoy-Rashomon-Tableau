from __future__ import annotations

from dataclasses import dataclass

from .abduction import AbductiveCausalRelationGenerator
from .models import Hypothesis, RcaCase, REL_CAUSAL
from .semantic import apply_semantic_scores


@dataclass
class RcaPrediction:
    case_id: str
    ranked_hypotheses: list[Hypothesis]
    predicted_root_causes: list[str]
    predicted_edges: list[tuple[str, str, str]]


class IncidentCausalRCA:
    """Stage-2 incident causal qualification and RCA pipeline.

    Stage 1 structural recovery is intentionally outside this class. Input
    ``RcaCase.known_edges`` contains grounded service-level propagation
    candidates (or controlled masked pairs), and this pipeline decides which of
    them participated in the current incident before ranking roots and paths.
    """

    def __init__(
        self,
        generator: AbductiveCausalRelationGenerator | None = None,
        semantic_scorer=None,
        global_inference=None,
        edge_threshold: float = 0.5,
        max_root_causes: int = 3,
    ):
        if not 0.0 <= edge_threshold <= 1.0:
            raise ValueError("edge_threshold must be in [0, 1]")
        if max_root_causes <= 0:
            raise ValueError("max_root_causes must be positive")
        self.generator = generator or AbductiveCausalRelationGenerator()
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

        known_causal = [edge for edge in case.known_edges if edge.relation == REL_CAUSAL]
        predicted_edges = [edge.key() for edge in known_causal]
        predicted_edges.extend(h.edge.key() for h in selected)
        # Stable deduplication is important when a visible causal edge and a
        # generated candidate converge to the same normalized triple.
        predicted_edges = list(dict.fromkeys(predicted_edges))

        root_hypotheses = list(selected)
        for edge in known_causal:
            root_hypotheses.append(
                Hypothesis(
                    edge=edge,
                    evidence_ids=[],
                    explanation="Known unmasked causal relation.",
                    structural_score=1.0,
                    temporal_score=1.0,
                    anomaly_score=1.0,
                    soft_logic_score=1.0,
                )
            )

        # A standard OpenRCA agent must still name a root cause when no causal
        # candidate crosses the fixed threshold. The fallback reads model-visible
        # telemetry only and therefore introduces no topology/gold leakage.
        if root_hypotheses:
            roots = self._rank_roots(case, root_hypotheses)
        else:
            roots = self._rank_evidence_only_roots(case)

        return RcaPrediction(
            case_id=case.case_id,
            ranked_hypotheses=hypotheses,
            predicted_root_causes=roots[: self.max_root_causes],
            predicted_edges=predicted_edges,
        )

    @staticmethod
    def _rank_roots(case: RcaCase, hypotheses: list[Hypothesis]) -> list[str]:
        """Rank root-like source nodes without using gold labels."""
        symptoms = set(case.symptom_nodes)
        by_node = case.evidence_by_node()
        nodes = {h.edge.source for h in hypotheses if h.edge.source not in symptoms}
        if not nodes:
            return IncidentCausalRCA._rank_evidence_only_roots(case)

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

    @staticmethod
    def _rank_evidence_only_roots(case: RcaCase) -> list[str]:
        """Telemetry-only fallback when no causal edge is selected."""
        symptoms = set(case.symptom_nodes)
        by_node = case.evidence_by_node()
        nodes = [node for node in by_node if node not in symptoms]
        if not nodes:
            nodes = list(by_node)
        if not nodes:
            return []

        anomaly: dict[str, float] = {}
        first_times: dict[str, float] = {}
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
            score = 0.75 * anomaly[node] + 0.25 * early
            ranked.append((node, score))
        ranked.sort(key=lambda x: (-x[1], x[0]))
        return [node for node, _ in ranked]


# Historical public class name retained for old scripts and experiment artifacts.
MissingRelationRCA = IncidentCausalRCA
