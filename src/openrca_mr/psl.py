from __future__ import annotations

from collections import defaultdict

from .models import Hypothesis, RcaCase


class SoftLogicApproximation:
    """Dependency-free approximation of the PSL objective for smoke tests.

    The paper experiments should use :class:`PslGlobalInference`. This fallback
    keeps the same score semantics so ablations and unit tests do not require a
    Java/PSL runtime.
    """

    def infer(self, case: RcaCase, hypotheses: list[Hypothesis]) -> list[Hypothesis]:
        outgoing: dict[str, list[Hypothesis]] = defaultdict(list)
        incoming: dict[str, list[Hypothesis]] = defaultdict(list)
        for h in hypotheses:
            outgoing[h.edge.source].append(h)
            incoming[h.edge.target].append(h)

        symptoms = set(case.symptom_nodes)
        for h in hypotheses:
            local = 0.45 * h.abductive_score + 0.45 * h.semantic_support - 0.35 * h.semantic_contradiction
            # Global consistency reward: edges that can participate in an
            # evidence-supported chain toward a symptom receive extra mass.
            chain = 0.0
            if h.edge.target in symptoms:
                chain += 0.15
            if outgoing.get(h.edge.target):
                chain += 0.10 * max(x.semantic_support for x in outgoing[h.edge.target])
            if incoming.get(h.edge.source):
                chain += 0.05 * max(x.semantic_support for x in incoming[h.edge.source])
            h.soft_logic_score = max(0.0, min(1.0, local + chain))

        return sorted(hypotheses, key=lambda h: h.soft_logic_score, reverse=True)


class PslGlobalInference:
    """Probabilistic Soft Logic inference over candidate causal relations.

    Predicates are soft observations derived from structure, temporal alignment,
    anomaly strength and DeBERTa support. ``CAUSES`` is the open predicate. The
    resulting truth values become the final candidate-edge scores.
    """

    def __init__(self):
        try:
            from pslpython.model import Model
            from pslpython.partition import Partition
            from pslpython.predicate import Predicate
            from pslpython.rule import Rule
        except ImportError as exc:
            raise RuntimeError("Install the PSL extra: pip install -e '.[psl]'") from exc
        self.Model = Model
        self.Partition = Partition
        self.Predicate = Predicate
        self.Rule = Rule

    def infer(self, case: RcaCase, hypotheses: list[Hypothesis]) -> list[Hypothesis]:
        if not hypotheses:
            return []

        model = self.Model("openrca_missing_relation")
        structural = self.Predicate("STRUCTURAL", closed=True, size=2)
        temporal = self.Predicate("TEMPORAL", closed=True, size=2)
        anomaly = self.Predicate("ANOMALYPAIR", closed=True, size=2)
        semantic = self.Predicate("SEMANTIC", closed=True, size=2)
        contradiction = self.Predicate("CONTRADICTION", closed=True, size=2)
        causes = self.Predicate("CAUSES", closed=False, size=2)
        for pred in [structural, temporal, anomaly, semantic, contradiction, causes]:
            model.add_predicate(pred)

        obs = self.Partition.OBSERVATIONS
        targets = self.Partition.TARGETS
        structural.add_data(obs, [[h.edge.source, h.edge.target, h.structural_score] for h in hypotheses])
        temporal.add_data(obs, [[h.edge.source, h.edge.target, h.temporal_score] for h in hypotheses])
        anomaly.add_data(obs, [[h.edge.source, h.edge.target, h.anomaly_score] for h in hypotheses])
        semantic.add_data(obs, [[h.edge.source, h.edge.target, h.semantic_support] for h in hypotheses])
        contradiction.add_data(obs, [[h.edge.source, h.edge.target, h.semantic_contradiction] for h in hypotheses])
        causes.add_data(targets, [[h.edge.source, h.edge.target] for h in hypotheses])

        # Weights are development-set hyperparameters, never test-set tuned.
        model.add_rule(self.Rule("1.0: STRUCTURAL(A,B) -> CAUSES(A,B) ^2"))
        model.add_rule(self.Rule("1.2: TEMPORAL(A,B) -> CAUSES(A,B) ^2"))
        model.add_rule(self.Rule("1.2: ANOMALYPAIR(A,B) -> CAUSES(A,B) ^2"))
        model.add_rule(self.Rule("2.0: SEMANTIC(A,B) -> CAUSES(A,B) ^2"))
        model.add_rule(self.Rule("2.0: CONTRADICTION(A,B) -> ~CAUSES(A,B) ^2"))

        inferred = model.infer()
        frame = inferred[causes]
        scores: dict[tuple[str, str], float] = {}
        for row in frame.itertuples(index=False):
            values = list(row)
            scores[(str(values[0]), str(values[1]))] = float(values[-1])

        for h in hypotheses:
            h.soft_logic_score = scores.get((h.edge.source, h.edge.target), 0.0)
        return sorted(hypotheses, key=lambda h: h.soft_logic_score, reverse=True)
