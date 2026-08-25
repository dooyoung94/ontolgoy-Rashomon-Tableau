from __future__ import annotations

from .models import Hypothesis, RcaCase, REL_CAUSAL, REL_NON_CAUSAL


class SoftLogicApproximation:
    """Dependency-free approximation of the global PSL model for tests."""

    def infer(self, case: RcaCase, hypotheses: list[Hypothesis]) -> list[Hypothesis]:
        if not hypotheses:
            return []

        local: dict[tuple[str, str], float] = {}
        for h in hypotheses:
            semantic = h.semantic_support if h.semantic_support is not None else 0.5
            contradiction = h.semantic_contradiction if h.semantic_contradiction is not None else 0.5
            margin = semantic - contradiction if h.semantic_support is not None else 0.0
            evidence = 0.55 * h.temporal_score + 0.45 * h.anomaly_score + 0.20 * margin
            # Lack of endpoint anomaly/temporal order is negative evidence in a
            # causal-propagation task, not just absence of positive support.
            negative = 0.30 * (1.0 - h.anomaly_score) + 0.15 * (1.0 - h.temporal_score)
            local[(h.edge.source, h.edge.target)] = max(0.0, min(1.0, evidence - negative))

        reaches = {node: 1.0 for node in case.symptom_nodes}
        hard_causal = [(e.source, e.target) for e in case.known_edges if e.relation == REL_CAUSAL]
        nodes = {x.edge.source for x in hypotheses} | {x.edge.target for x in hypotheses}
        nodes |= {x for pair in hard_causal for x in pair}
        for node in nodes:
            reaches.setdefault(node, 0.0)

        for _ in range(max(2, len(nodes))):
            changed = 0.0
            next_reaches = dict(reaches)
            for source, target in hard_causal:
                value = max(next_reaches.get(source, 0.0), reaches.get(target, 0.0))
                changed = max(changed, abs(value - next_reaches.get(source, 0.0)))
                next_reaches[source] = value
            for h in hypotheses:
                key = (h.edge.source, h.edge.target)
                propagated = local[key] * reaches.get(h.edge.target, 0.0)
                value = max(next_reaches.get(h.edge.source, 0.0), propagated)
                changed = max(changed, abs(value - next_reaches.get(h.edge.source, 0.0)))
                next_reaches[h.edge.source] = value
            reaches = next_reaches
            if changed < 1e-6:
                break

        for h in hypotheses:
            key = (h.edge.source, h.edge.target)
            downstream = reaches.get(h.edge.target, 0.0)
            # Global reachability may support a locally plausible edge, but it
            # cannot turn a locally unsupported dependency into causal by itself.
            score = 0.82 * local[key] + 0.18 * min(local[key], downstream)
            h.soft_logic_score = max(0.0, min(1.0, score))

        return sorted(hypotheses, key=lambda h: h.soft_logic_score if h.soft_logic_score is not None else -1.0, reverse=True)


class PslGlobalInference:
    """PSL joint inference for masked incident-specific causal relations.

    Structural connectivity is already observed and only constrains the candidate
    domain; it is deliberately *not* a causal rule. Positive/negative telemetry,
    visible relation labels, and path coherence decide CAUSES.
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

        model = self.Model("openrca_relation_mask_global")
        temporal = self.Predicate("TEMPORAL", size=2)
        anomaly = self.Predicate("ANOMALYPAIR", size=2)
        causes = self.Predicate("CAUSES", size=2)
        reaches = self.Predicate("REACHES", size=1)

        predicates = [temporal, anomaly, causes, reaches]
        has_semantic = any(h.semantic_support is not None for h in hypotheses)
        if has_semantic:
            semantic = self.Predicate("SEMANTIC", size=2)
            contradiction = self.Predicate("CONTRADICTION", size=2)
            predicates.extend([semantic, contradiction])
        else:
            semantic = contradiction = None

        for pred in predicates:
            model.add_predicate(pred)

        obs = self.Partition.OBSERVATIONS
        targets = self.Partition.TARGETS
        temporal.add_data(obs, [[h.edge.source, h.edge.target, h.temporal_score] for h in hypotheses])
        anomaly.add_data(obs, [[h.edge.source, h.edge.target, h.anomaly_score] for h in hypotheses])

        known_causal = [e for e in case.known_edges if e.relation == REL_CAUSAL]
        known_noncausal = [e for e in case.known_edges if e.relation == REL_NON_CAUSAL]
        if known_causal:
            causes.add_data(obs, [[e.source, e.target, 1.0] for e in known_causal])
        if known_noncausal:
            causes.add_data(obs, [[e.source, e.target, 0.0] for e in known_noncausal])
        causes.add_data(targets, [[h.edge.source, h.edge.target] for h in hypotheses])

        if has_semantic and semantic is not None and contradiction is not None:
            semantic.add_data(obs, [[h.edge.source, h.edge.target, h.semantic_support or 0.0] for h in hypotheses])
            contradiction.add_data(obs, [[h.edge.source, h.edge.target, h.semantic_contradiction or 0.0] for h in hypotheses])

        nodes = sorted(
            {h.edge.source for h in hypotheses}
            | {h.edge.target for h in hypotheses}
            | {e.source for e in case.known_edges}
            | {e.target for e in case.known_edges}
        )
        symptoms = set(case.symptom_nodes)
        if symptoms:
            reaches.add_data(obs, [[node, 1.0] for node in sorted(symptoms)])
        non_symptoms = [node for node in nodes if node not in symptoms]
        if non_symptoms:
            reaches.add_data(targets, [[node] for node in non_symptoms])

        # Incident-local evidence. Structure is omitted on purpose: all targets
        # are already observed dependencies, so it cannot distinguish causality.
        model.add_rule(self.Rule("1.2: TEMPORAL(A, B) -> CAUSES(A, B) ^2"))
        model.add_rule(self.Rule("1.1: ANOMALYPAIR(A, B) -> CAUSES(A, B) ^2"))
        model.add_rule(self.Rule("0.8: !TEMPORAL(A, B) -> !CAUSES(A, B) ^2"))
        model.add_rule(self.Rule("1.2: !ANOMALYPAIR(A, B) -> !CAUSES(A, B) ^2"))
        if has_semantic:
            # Contrastive DeBERTa produces complementary soft evidence. Equal
            # 0.5/0.5 scores cancel rather than introducing a causal bias.
            model.add_rule(self.Rule("1.0: SEMANTIC(A, B) -> CAUSES(A, B) ^2"))
            model.add_rule(self.Rule("1.0: CONTRADICTION(A, B) -> !CAUSES(A, B) ^2"))

        # Global path coherence only reinforces edges that also have local
        # evidence; known causal relations seed REACHES through CAUSES facts.
        model.add_rule(self.Rule("1.6: CAUSES(A, B) & REACHES(B) -> REACHES(A) ^2"))
        model.add_rule(self.Rule("0.8: TEMPORAL(A, B) & REACHES(B) -> CAUSES(A, B) ^2"))
        model.add_rule(self.Rule("0.5: CAUSES(A, B) -> !CAUSES(B, A) ^2"))
        model.add_rule(self.Rule("0.25: !CAUSES(A, B) ^2"))

        inferred = model.infer(psl_options={"runtime.log.level": "ERROR"})
        frame = inferred[causes]
        scores: dict[tuple[str, str], float] = {}
        for row in frame.itertuples(index=False):
            values = list(row)
            scores[(str(values[0]), str(values[1]))] = float(values[-1])

        for h in hypotheses:
            h.soft_logic_score = scores.get((h.edge.source, h.edge.target), 0.0)
        return sorted(hypotheses, key=lambda h: h.soft_logic_score if h.soft_logic_score is not None else -1.0, reverse=True)
