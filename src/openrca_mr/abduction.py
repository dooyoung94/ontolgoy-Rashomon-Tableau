from __future__ import annotations

from .models import (
    CausalEdge,
    Hypothesis,
    RcaCase,
    REL_CAUSAL,
    REL_MASKED,
    REL_NON_CAUSAL,
    REL_OBSERVED,
)


class AbductiveRelationGenerator:
    """Generate causal-relation hypotheses only for observed endpoint pairs.

    Main-track assumption: collectors/traces already reveal the structural edge;
    the missing information is whether that dependency participated in causal
    propagation for this incident. Connectivity is candidate eligibility only,
    never positive causal evidence.
    """

    def __init__(self, max_candidates: int = 64):
        self.max_candidates = max_candidates

    def generate(self, case: RcaCase) -> list[Hypothesis]:
        by_node = case.evidence_by_node()
        hypotheses: list[Hypothesis] = []
        seen: set[tuple[str, str]] = set()

        for observed in case.known_edges:
            if observed.relation in {REL_CAUSAL, REL_NON_CAUSAL}:
                continue
            if observed.relation not in {REL_MASKED, REL_OBSERVED, "dependency_propagates_to"}:
                continue
            pair = (observed.source, observed.target)
            if pair in seen:
                continue
            seen.add(pair)

            src_ev = by_node.get(observed.source, [])
            tgt_ev = by_node.get(observed.target, [])
            if not src_ev or not tgt_ev:
                continue

            temporal = self._temporal_score(src_ev, tgt_ev)
            anomaly = self._anomaly_score(src_ev, tgt_ev)
            evidence_ids = sorted({x.evidence_id for x in [*src_ev, *tgt_ev]})
            explanation = (
                f"Observed dependency {observed.source} -> {observed.target}; "
                f"candidate relation={REL_CAUSAL}, temporal={temporal:.2f}, "
                f"endpoint_anomaly={anomaly:.2f}."
            )
            hypotheses.append(
                Hypothesis(
                    edge=CausalEdge(observed.source, REL_CAUSAL, observed.target),
                    evidence_ids=evidence_ids,
                    explanation=explanation,
                    structural_score=0.0,
                    temporal_score=temporal,
                    anomaly_score=anomaly,
                )
            )

        hypotheses.sort(key=lambda h: h.abductive_score, reverse=True)
        return hypotheses[: self.max_candidates]

    @staticmethod
    def _temporal_score(source, target) -> float:
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
    def _anomaly_score(source, target) -> float:
        src = max((x.abnormality for x in source), default=0.0)
        tgt = max((x.abnormality for x in target), default=0.0)
        return min(src, tgt)
