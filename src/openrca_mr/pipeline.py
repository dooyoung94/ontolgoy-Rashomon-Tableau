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
    """Composable pipeline used by all ablations.

    Stages can be independently disabled so candidate generation is kept fixed
    when measuring the contribution of semantic scoring and global inference.
    """

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
        else:
            for h in hypotheses:
                h.semantic_support = h.abductive_score
                h.semantic_contradiction = 0.0

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
        symptoms = set(case.symptom_nodes)
        scores: dict[str, float] = {}
        for h in hypotheses:
            if h.edge.source in symptoms:
                continue
            scores[h.edge.source] = max(scores.get(h.edge.source, 0.0), h.final_score)
        return [node for node, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
