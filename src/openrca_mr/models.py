from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
        return (self.structural_score + self.temporal_score + self.anomaly_score) / 3.0

    @property
    def final_score(self) -> float:
        if self.soft_logic_score is not None:
            return self.soft_logic_score
        if self.semantic_support is not None:
            return 0.55 * self.semantic_support + 0.45 * self.abductive_score
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
