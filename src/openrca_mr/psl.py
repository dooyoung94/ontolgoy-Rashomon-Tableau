from __future__ import annotations

from collections import defaultdict

from .models import (
    Hypothesis,
    RcaCase,
    RelationObservation,
    StructuralHypothesis,
    CausalEdge,
    REL_CAUSAL,
    REL_HAS_SERVICE,
    REL_NON_CAUSAL,
    REL_RUNS_ON,
)


# Snapshot-level functional constraints that are defensible for the current
# ontology. CALLS, DEPLOYED_ON, USES_DATABASE and USES_MESSAGING are deliberately
# excluded because multiple targets are normal for those relations.
_FUNCTIONAL_BY_SOURCE = frozenset({REL_RUNS_ON})
_FUNCTIONAL_BY_TARGET = frozenset({REL_HAS_SERVICE})


def _visible_functional_conflicts(
    visible_relations: list[CausalEdge],
    hypotheses: list[StructuralHypothesis],
) -> set[tuple[str, str, str]]:
    by_source: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_target: dict[tuple[str, str], set[str]] = defaultdict(set)
    for edge in visible_relations:
        if edge.relation in _FUNCTIONAL_BY_SOURCE:
            by_source[(edge.source, edge.relation)].add(edge.target)
        if edge.relation in _FUNCTIONAL_BY_TARGET:
            by_target[(edge.relation, edge.target)].add(edge.source)

    conflicts: set[tuple[str, str, str]] = set()
    for hypothesis in hypotheses:
        edge = hypothesis.edge
        if edge.relation in _FUNCTIONAL_BY_SOURCE:
            existing_targets = by_source.get((edge.source, edge.relation), set())
            if existing_targets and edge.target not in existing_targets:
                conflicts.add(edge.key())
        if edge.relation in _FUNCTIONAL_BY_TARGET:
            existing_sources = by_target.get((edge.relation, edge.target), set())
            if existing_sources and edge.source not in existing_sources:
                conflicts.add(edge.key())
    return conflicts


class StructuralSoftLogicApproximation:
    """Dependency-free approximation of Stage-1 PSL selection.

    Type compatibility is enforced by the abductive generator before this
    point. This layer combines abductive/semantic support and penalizes mutually
    competing predicates over the same endpoint pair. It is used for tests and
    smoke checks; paper results that claim PSL must use ``PslStructuralInference``.
    """

    def infer_structural(
        self,
        observations: list[RelationObservation],
        hypotheses: list[StructuralHypothesis],
        visible_relations: list[CausalEdge] | None = None,
    ) -> list[StructuralHypothesis]:
        del observations
        if not hypotheses:
            return []

        local: dict[tuple[str, str, str], float] = {}
        visible_conflicts = _visible_functional_conflicts(
            list(visible_relations or []), hypotheses
        )
        by_pair: dict[tuple[str, str], list[StructuralHypothesis]] = defaultdict(list)
        for h in hypotheses:
            if h.semantic_support is None:
                semantic_term = h.abductive_support
            else:
                contradiction = h.semantic_contradiction or 0.0
                margin = h.semantic_support - contradiction
                semantic_term = 0.5 + 0.5 * max(-1.0, min(1.0, margin))
            value = 0.70 * h.abductive_support + 0.30 * semantic_term
            local[h.edge.key()] = max(0.0, min(1.0, value))
            by_pair[(h.edge.source, h.edge.target)].append(h)

        for pair_hypotheses in by_pair.values():
            for h in pair_hypotheses:
                competitors = [
                    local[other.edge.key()]
                    for other in pair_hypotheses
                    if other.edge.relation != h.edge.relation
                ]
                competition = max(competitors, default=0.0)
                h.soft_logic_score = max(
                    0.0,
                    min(
                        1.0,
                        local[h.edge.key()]
                        - 0.15 * competition
                        - (0.65 if h.edge.key() in visible_conflicts else 0.0),
                    ),
                )

        return sorted(
            hypotheses,
            key=lambda h: (
                -(h.soft_logic_score if h.soft_logic_score is not None else 0.0),
                h.edge.source,
                h.edge.relation,
                h.edge.target,
            ),
        )


class PslStructuralInference:
    """PSL inference for Stage-1 structural relation existence.

    The candidate domain is already constrained to telemetry-grounded endpoint
    pairs and ontology-compatible relation types. PSL therefore selects among
    candidates; it never invents new endpoints or relation types.
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

    def infer_structural(
        self,
        observations: list[RelationObservation],
        hypotheses: list[StructuralHypothesis],
        visible_relations: list[CausalEdge] | None = None,
    ) -> list[StructuralHypothesis]:
        del observations
        if not hypotheses:
            return []

        model = self.Model("openrca_structural_relation_recovery")
        prior = self.Predicate("STRUCTPRIOR", size=3)
        relation = self.Predicate("STRUCTREL", size=3)
        competes = self.Predicate("COMPETES", size=4)
        visible_conflict = self.Predicate("VISIBLEFUNCCONFLICT", size=3)
        predicates = [prior, relation, competes, visible_conflict]

        has_semantic = any(h.semantic_support is not None for h in hypotheses)
        if has_semantic:
            semantic = self.Predicate("STRUCTSEMANTIC", size=3)
            contradiction = self.Predicate("STRUCTCONTRA", size=3)
            predicates.extend([semantic, contradiction])
        else:
            semantic = contradiction = None

        for pred in predicates:
            model.add_predicate(pred)

        obs = self.Partition.OBSERVATIONS
        targets = self.Partition.TARGETS
        prior.add_data(
            obs,
            [
                [h.edge.source, h.edge.relation, h.edge.target, h.abductive_support]
                for h in hypotheses
            ],
        )
        relation.add_data(
            targets,
            [[h.edge.source, h.edge.relation, h.edge.target] for h in hypotheses],
        )

        by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
        for h in hypotheses:
            by_pair[(h.edge.source, h.edge.target)].append(h.edge.relation)
        competition_rows: list[list[str | float]] = []
        for (source, target), relations in by_pair.items():
            unique = sorted(set(relations))
            for left in unique:
                for right in unique:
                    if left != right:
                        competition_rows.append([source, left, target, right, 1.0])
        if competition_rows:
            competes.add_data(obs, competition_rows)

        visible_conflicts = _visible_functional_conflicts(
            list(visible_relations or []), hypotheses
        )
        if visible_conflicts:
            visible_conflict.add_data(
                obs,
                [[source, rel, target, 1.0] for source, rel, target in sorted(visible_conflicts)],
            )

        if has_semantic and semantic is not None and contradiction is not None:
            semantic.add_data(
                obs,
                [
                    [h.edge.source, h.edge.relation, h.edge.target, h.semantic_support or 0.0]
                    for h in hypotheses
                ],
            )
            contradiction.add_data(
                obs,
                [
                    [
                        h.edge.source,
                        h.edge.relation,
                        h.edge.target,
                        h.semantic_contradiction or 0.0,
                    ]
                    for h in hypotheses
                ],
            )

        model.add_rule(self.Rule("1.4: STRUCTPRIOR(A, R, B) -> STRUCTREL(A, R, B) ^2"))
        if has_semantic:
            model.add_rule(
                self.Rule("1.1: STRUCTSEMANTIC(A, R, B) -> STRUCTREL(A, R, B) ^2")
            )
            model.add_rule(
                self.Rule("1.2: STRUCTCONTRA(A, R, B) -> !STRUCTREL(A, R, B) ^2")
            )
        model.add_rule(
            self.Rule(
                "0.8: COMPETES(A, R, B, S) & STRUCTREL(A, R, B) -> !STRUCTREL(A, S, B) ^2"
            )
        )
        model.add_rule(
            self.Rule(
                "2.0: VISIBLEFUNCCONFLICT(A, R, B) -> !STRUCTREL(A, R, B) ^2"
            )
        )
        # Sparsity prior: unsupported relations should not survive merely because
        # they are type-compatible candidates.
        model.add_rule(self.Rule("0.20: !STRUCTREL(A, R, B) ^2"))

        inferred = model.infer(psl_options={"runtime.log.level": "ERROR"})
        frame = inferred[relation]
        scores: dict[tuple[str, str, str], float] = {}
        for row in frame.itertuples(index=False):
            values = list(row)
            scores[(str(values[0]), str(values[1]), str(values[2]))] = float(values[-1])

        for h in hypotheses:
            h.soft_logic_score = scores.get(h.edge.key(), 0.0)
        return sorted(
            hypotheses,
            key=lambda h: (
                -(h.soft_logic_score if h.soft_logic_score is not None else 0.0),
                h.edge.source,
                h.edge.relation,
                h.edge.target,
            ),
        )


class SoftLogicApproximation:
    """Dependency-free approximation of the Stage-2 global PSL model for tests."""

    def infer(self, case: RcaCase, hypotheses: list[Hypothesis]) -> list[Hypothesis]:
        if not hypotheses:
            return []

        local: dict[tuple[str, str], float] = {}
        for h in hypotheses:
            semantic = h.semantic_support if h.semantic_support is not None else 0.5
            contradiction = h.semantic_contradiction if h.semantic_contradiction is not None else 0.5
            margin = semantic - contradiction if h.semantic_support is not None else 0.0
            evidence = 0.55 * h.temporal_score + 0.45 * h.anomaly_score + 0.20 * margin
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
            score = 0.82 * local[key] + 0.18 * min(local[key], downstream)
            h.soft_logic_score = max(0.0, min(1.0, score))

        return sorted(
            hypotheses,
            key=lambda h: h.soft_logic_score if h.soft_logic_score is not None else -1.0,
            reverse=True,
        )


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

        model.add_rule(self.Rule("1.2: TEMPORAL(A, B) -> CAUSES(A, B) ^2"))
        model.add_rule(self.Rule("1.1: ANOMALYPAIR(A, B) -> CAUSES(A, B) ^2"))
        model.add_rule(self.Rule("0.8: !TEMPORAL(A, B) -> !CAUSES(A, B) ^2"))
        model.add_rule(self.Rule("1.2: !ANOMALYPAIR(A, B) -> !CAUSES(A, B) ^2"))
        if has_semantic:
            model.add_rule(self.Rule("1.0: SEMANTIC(A, B) -> CAUSES(A, B) ^2"))
            model.add_rule(self.Rule("1.0: CONTRADICTION(A, B) -> !CAUSES(A, B) ^2"))

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
        return sorted(
            hypotheses,
            key=lambda h: h.soft_logic_score if h.soft_logic_score is not None else -1.0,
            reverse=True,
        )
