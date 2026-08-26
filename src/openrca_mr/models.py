from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Incident-specific causal semantics (Stage 2).
REL_CAUSAL = "causal_propagates_to"
REL_NON_CAUSAL = "non_causal_dependency"
REL_MASKED = "__MASKED_RELATION__"
REL_OBSERVED = "dependency_propagates_to"

# Operational / ontology-like structural semantics (Stage 1).
REL_CALLS = "calls"
REL_DEPLOYED_ON = "deployed_on"
REL_RUNS_ON = "runs_on"
REL_USES_DATABASE = "uses_database"
REL_USES_MESSAGING = "uses_messaging"
REL_HAS_SERVICE = "has_service"
REL_STRUCTURAL_MASKED = "__MASKED_STRUCTURAL_RELATION__"

STRUCTURAL_RELATION_TYPES = frozenset(
    {
        REL_CALLS,
        REL_DEPLOYED_ON,
        REL_RUNS_ON,
        REL_USES_DATABASE,
        REL_USES_MESSAGING,
        REL_HAS_SERVICE,
    }
)


@dataclass(frozen=True)
class CausalEdge:
    """Generic relation triple retained under the historical public name.

    Stage 1 uses it for typed operational triples such as ``CALLS`` and
    ``DEPLOYED_ON``. Stage 2 uses it for incident-specific causal semantics.
    Renaming the class would invalidate existing experiment artifacts, so the
    public name is intentionally preserved for backward compatibility.
    """

    source: str
    relation: str
    target: str

    def key(self) -> tuple[str, str, str]:
        return self.source, self.relation, self.target


@dataclass(frozen=True)
class RelationObservation:
    """Model-visible evidence that constrains a possible structural relation.

    The observation deliberately stores *evidence kind* rather than a gold
    relation label. A downstream abductive generator converts observations into
    candidate structural triples under the ontology schema. This prevents the
    telemetry adapter from silently becoming the final relation classifier.
    """

    observation_id: str
    source: str
    target: str
    evidence_kind: str
    confidence: float = 1.0
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


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
class StructuralHypothesis:
    """Candidate typed operational relation produced by Stage-1 abduction."""

    edge: CausalEdge
    observation_ids: list[str]
    explanation: str
    abductive_support: float = 0.0
    semantic_support: float | None = None
    semantic_contradiction: float | None = None
    semantic_neutral: float | None = None
    soft_logic_score: float | None = None

    @property
    def final_score(self) -> float:
        if self.soft_logic_score is not None:
            return max(0.0, min(1.0, self.soft_logic_score))
        if self.semantic_support is not None:
            contradiction = self.semantic_contradiction or 0.0
            margin = self.semantic_support - contradiction
            return max(0.0, min(1.0, self.abductive_support + 0.25 * margin))
        return max(0.0, min(1.0, self.abductive_support))


@dataclass
class Hypothesis:
    """Stage-2 incident-specific causal hypothesis."""

    edge: CausalEdge
    evidence_ids: list[str]
    explanation: str
    structural_score: float = 0.0
    temporal_score: float = 0.0
    anomaly_score: float = 0.0
    semantic_support: float | None = None
    semantic_contradiction: float | None = None
    semantic_neutral: float | None = None
    soft_logic_score: float | None = None

    @property
    def abductive_score(self) -> float:
        # Structural connectivity is eligibility, not evidence that this
        # incident propagated over the dependency.
        return 0.55 * self.temporal_score + 0.45 * self.anomaly_score

    @property
    def final_score(self) -> float:
        if self.soft_logic_score is not None:
            return self.soft_logic_score
        if self.semantic_support is not None:
            contradiction = (
                self.semantic_contradiction
                if self.semantic_contradiction is not None
                else 0.0
            )
            margin = self.semantic_support - contradiction
            return max(0.0, min(1.0, self.abductive_score + 0.25 * margin))
        return self.abductive_score


@dataclass
class RcaCase:
    case_id: str
    symptom_nodes: list[str]
    # Stage-2 propagation-oriented service pairs. These are observations/candidates,
    # not automatically causal facts.
    known_edges: list[CausalEdge]
    evidence: list[Evidence]
    gold_root_causes: list[str] = field(default_factory=list)
    gold_edges: list[CausalEdge] = field(default_factory=list)
    gold_paths: list[list[str]] = field(default_factory=list)
    gold_alarm_nodes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Stage-1 recovered typed operational relations in their natural direction.
    # Kept near the end to preserve the historical positional constructor.
    structural_relations: list[CausalEdge] = field(default_factory=list)
    # Raw model-visible Stage-1 relation evidence. Appended after
    # ``structural_relations`` for backward-compatible positional construction.
    relation_observations: list[RelationObservation] = field(default_factory=list)

    def evidence_by_node(self) -> dict[str, list[Evidence]]:
        out: dict[str, list[Evidence]] = {}
        for item in self.evidence:
            out.setdefault(item.node, []).append(item)
        return out
