from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


REL_CAUSAL = "causal_propagates_to"
REL_NON_CAUSAL = "non_causal_dependency"
REL_MASKED = "__MASKED_RELATION__"
REL_OBSERVED = "dependency_propagates_to"


@dataclass(frozen=True)
class CausalEdge:
    source: str
    relation: str
    target: str

    def key(self) -> tuple[str, str, str]:
        return self.source, self.relation, self.target


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    node: str
    kind: str
    signal: str
    abnormality: float
    timestamp: float | None = None
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_anomalous(self) -> bool:
        return self.abnormality >= 0.5


@dataclass
class Hypothesis:
    edge: CausalEdge
    evidence_ids: list[str]
    explanation: str
    structural_score: float = 0.0
    temporal_score: float = 0.0
    anomaly_score: float = 0.0
    semantic_support: float | None = None
    semantic_contradiction: float | None = None
    soft_logic_score: float | None = None

    @property
    def abductive_score(self) -> float:
        # In the main relation-masking task, connectivity is already observed by
        # the collector and therefore is eligibility, not evidence of causality.
        # Causal support must come from incident-specific temporal/anomaly data.
        return 0.55 * self.temporal_score + 0.45 * self.anomaly_score

    @property
    def final_score(self) -> float:
        if self.soft_logic_score is not None:
            return self.soft_logic_score
        if self.semantic_support is not None:
            # Neutral-preserving semantic correction. DeBERTa can only move the
            # telemetry prior through a causal-vs-noncausal preference margin.
            contradiction = self.semantic_contradiction or 0.0
            margin = self.semantic_support - contradiction
            return max(0.0, min(1.0, self.abductive_score + 0.25 * margin))
        return self.abductive_score


@dataclass
class RcaCase:
    case_id: str
    symptom_nodes: list[str]
    known_edges: list[CausalEdge]
    evidence: list[Evidence]
    gold_root_causes: list[str] = field(default_factory=list)
    gold_edges: list[CausalEdge] = field(default_factory=list)
    gold_paths: list[list[str]] = field(default_factory=list)
    gold_alarm_nodes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def evidence_by_node(self) -> dict[str, list[Evidence]]:
        out: dict[str, list[Evidence]] = {}
        for item in self.evidence:
            out.setdefault(item.node, []).append(item)
        return out
