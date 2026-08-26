from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass

import pandas as pd

from .models import (
    CausalEdge,
    RcaCase,
    RelationObservation,
    StructuralHypothesis,
    REL_CALLS,
    REL_DEPLOYED_ON,
    REL_HAS_SERVICE,
    REL_OBSERVED,
    REL_RUNS_ON,
    REL_STRUCTURAL_MASKED,
    REL_USES_DATABASE,
    REL_USES_MESSAGING,
    STRUCTURAL_RELATION_TYPES,
)


# Ontology-level type constraints. They restrict which typed triples are
# admissible; they do not assert that a relation actually exists.
STRUCTURAL_RELATION_SCHEMA: dict[tuple[str, str], tuple[str, ...]] = {
    ("service", "service"): (REL_CALLS,),
    ("service", "pod"): (REL_DEPLOYED_ON,),
    ("pod", "node"): (REL_RUNS_ON,),
    ("service", "database"): (REL_USES_DATABASE,),
    ("service", "messaging"): (REL_USES_MESSAGING,),
    ("system", "service"): (REL_HAS_SERVICE,),
}

# Observation-specific abductive priors. These values only express how strongly
# an evidence pattern supports a *candidate triple*. The final relation may be
# rescored by DeBERTa and PSL; no causal/PAVE gold is used here.
_OBSERVATION_RELATION_PRIOR: dict[str, dict[str, float]] = {
    "trace_parent_child": {REL_CALLS: 0.98},
    "service_pod_cooccurrence": {REL_DEPLOYED_ON: 0.98},
    "pod_node_cooccurrence": {REL_RUNS_ON: 0.98},
    "db_client_context": {REL_USES_DATABASE: 0.95},
    "messaging_context": {REL_USES_MESSAGING: 0.95},
    "system_inventory": {REL_HAS_SERVICE: 1.00},
    # Generic endpoint co-observation deliberately remains weak. It is useful
    # for incomplete-observation experiments without turning co-occurrence into
    # a relation fact by itself.
    "generic_endpoint_cooccurrence": {},
}


def entity(kind: str, value: object) -> str:
    return f"{kind}:{str(value).strip()}"


def entity_kind(value: str) -> str:
    return value.split(":", 1)[0] if ":" in value else "service"


def entity_value(value: str) -> str:
    return value.split(":", 1)[1] if ":" in value else value


def _clean(value: object) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan"}:
        return None
    return text


def _first_column(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def _observation_id(kind: str, source: str, target: str) -> str:
    payload = f"{kind}|{source}|{target}".encode("utf-8")
    return "ro-" + hashlib.sha256(payload).hexdigest()[:16]


def _dedupe_observations(items: list[RelationObservation]) -> list[RelationObservation]:
    """Collapse repeated telemetry rows without losing support count.

    Multiple spans often repeat the same structural fact. Keeping every row
    would make confidence depend mainly on traffic volume. We therefore keep one
    observation per (source, target, evidence_kind), store the row count, and use
    the maximum row-level confidence rather than multiplying duplicate evidence.
    """

    grouped: dict[tuple[str, str, str], list[RelationObservation]] = defaultdict(list)
    for item in items:
        grouped[(item.source, item.target, item.evidence_kind)].append(item)

    out: list[RelationObservation] = []
    for (source, target, kind), rows in grouped.items():
        first = rows[0]
        metadata = dict(first.metadata)
        metadata["observation_count"] = len(rows)
        out.append(
            RelationObservation(
                observation_id=_observation_id(kind, source, target),
                source=source,
                target=target,
                evidence_kind=kind,
                confidence=max(max(0.0, min(1.0, row.confidence)) for row in rows),
                text=first.text,
                metadata=metadata,
            )
        )
    return sorted(out, key=lambda item: (item.source, item.evidence_kind, item.target))


def _service_call_observations(traces: pd.DataFrame) -> list[RelationObservation]:
    needed = {"trace_id", "span_id", "parent_span_id", "service_name"}
    if traces.empty or not needed.issubset(traces.columns):
        return []

    # Normalize join keys to strings. Some parquet readers expose span IDs as
    # integers/objects depending on the system; a type mismatch must not erase
    # otherwise valid parent-child observations.
    frame = traces[["trace_id", "span_id", "parent_span_id", "service_name"]].copy()
    for col in ("trace_id", "span_id", "parent_span_id"):
        frame[col] = frame[col].map(_clean)

    parent = frame[["trace_id", "span_id", "service_name"]].dropna().rename(
        columns={"span_id": "parent_span_id", "service_name": "parent_service"}
    )
    child = frame[["trace_id", "parent_span_id", "service_name"]].dropna().rename(
        columns={"service_name": "child_service"}
    )
    child = child[child["parent_span_id"].astype(str) != ""]
    joined = child.merge(parent, on=["trace_id", "parent_span_id"], how="inner")

    out: list[RelationObservation] = []
    for caller_raw, callee_raw in joined[["parent_service", "child_service"]].itertuples(index=False):
        caller = _clean(caller_raw)
        callee = _clean(callee_raw)
        if caller and callee and caller != callee:
            source = entity("service", caller)
            target = entity("service", callee)
            out.append(
                RelationObservation(
                    _observation_id("trace_parent_child", source, target),
                    source,
                    target,
                    "trace_parent_child",
                    0.98,
                    f"A parent span from {caller} has a child span executed by {callee}.",
                )
            )
    return out


def _deployment_observations(frames: list[pd.DataFrame]) -> list[RelationObservation]:
    pod_names = ("attr.k8s.pod.name", "k8s.pod.name", "resource.k8s.pod.name")
    node_names = (
        "attr.k8s.node.name",
        "k8s.node.name",
        "resource.k8s.node.name",
        "attr.host.name",
        "host.name",
    )
    out: list[RelationObservation] = []
    for df in frames:
        if df.empty:
            continue
        pod_col = _first_column(df, pod_names)
        node_col = _first_column(df, node_names)

        if "service_name" in df.columns and pod_col:
            for service_raw, pod_raw in df[["service_name", pod_col]].drop_duplicates().itertuples(index=False):
                service = _clean(service_raw)
                pod = _clean(pod_raw)
                if service and pod:
                    source = entity("service", service)
                    target = entity("pod", pod)
                    out.append(
                        RelationObservation(
                            _observation_id("service_pod_cooccurrence", source, target),
                            source,
                            target,
                            "service_pod_cooccurrence",
                            0.98,
                            f"Telemetry for {service} is emitted with Kubernetes pod {pod}.",
                        )
                    )

        if pod_col and node_col:
            for pod_raw, node_raw in df[[pod_col, node_col]].drop_duplicates().itertuples(index=False):
                pod = _clean(pod_raw)
                node = _clean(node_raw)
                if pod and node:
                    source = entity("pod", pod)
                    target = entity("node", node)
                    out.append(
                        RelationObservation(
                            _observation_id("pod_node_cooccurrence", source, target),
                            source,
                            target,
                            "pod_node_cooccurrence",
                            0.98,
                            f"Pod {pod} is observed with node/host resource {node}.",
                        )
                    )
    return out


def _database_observations(traces: pd.DataFrame) -> list[RelationObservation]:
    if traces.empty or "service_name" not in traces.columns:
        return []
    system_col = _first_column(
        traces,
        ("attr.db.system", "db.system", "attr.db.system.name", "db.system.name"),
    )
    if not system_col:
        return []
    target_col = _first_column(
        traces,
        (
            "attr.server.address",
            "server.address",
            "attr.net.peer.name",
            "net.peer.name",
            "attr.db.namespace",
            "db.namespace",
            "attr.db.name",
            "db.name",
        ),
    )
    columns = ["service_name", system_col] + ([target_col] if target_col else [])
    out: list[RelationObservation] = []
    for row in traces[columns].drop_duplicates().itertuples(index=False, name=None):
        service = _clean(row[0])
        db_system = _clean(row[1])
        db_target = _clean(row[2]) if target_col else None
        if not service or not db_system:
            continue
        db_id = f"{db_system}:{db_target}" if db_target else db_system
        source = entity("service", service)
        target = entity("database", db_id)
        out.append(
            RelationObservation(
                _observation_id("db_client_context", source, target),
                source,
                target,
                "db_client_context",
                0.95,
                f"A span from {service} carries database system {db_system}"
                + (f" and database/server target {db_target}." if db_target else "."),
            )
        )
    return out


def _messaging_observations(traces: pd.DataFrame) -> list[RelationObservation]:
    if traces.empty or "service_name" not in traces.columns:
        return []
    system_col = _first_column(traces, ("attr.messaging.system", "messaging.system"))
    if not system_col:
        return []
    target_col = _first_column(
        traces,
        (
            "attr.messaging.destination.name",
            "messaging.destination.name",
            "attr.messaging.destination",
            "messaging.destination",
            "attr.server.address",
            "server.address",
        ),
    )
    columns = ["service_name", system_col] + ([target_col] if target_col else [])
    out: list[RelationObservation] = []
    for row in traces[columns].drop_duplicates().itertuples(index=False, name=None):
        service = _clean(row[0])
        messaging_system = _clean(row[1])
        destination = _clean(row[2]) if target_col else None
        if not service or not messaging_system:
            continue
        target_name = f"{messaging_system}:{destination}" if destination else messaging_system
        source = entity("service", service)
        target = entity("messaging", target_name)
        out.append(
            RelationObservation(
                _observation_id("messaging_context", source, target),
                source,
                target,
                "messaging_context",
                0.95,
                f"A span from {service} carries messaging system {messaging_system}"
                + (f" and destination {destination}." if destination else "."),
            )
        )
    return out


def collect_structural_observations(
    traces: pd.DataFrame,
    metrics: pd.DataFrame | None = None,
    logs: pd.DataFrame | None = None,
    system: str | None = None,
) -> list[RelationObservation]:
    """Collect model-visible relation evidence without finalizing relation facts.

    This function is intentionally the telemetry adapter boundary. It may expose
    endpoint co-observation and typed resource evidence, but it never reads PAVE
    causal graphs, injection labels, or gold roots. Final structural triples are
    produced only by the abductive recovery stage below.
    """

    metrics = metrics if metrics is not None else pd.DataFrame()
    logs = logs if logs is not None else pd.DataFrame()
    observations: list[RelationObservation] = []
    observations.extend(_service_call_observations(traces))
    observations.extend(_deployment_observations([traces, metrics, logs]))
    observations.extend(_database_observations(traces))
    observations.extend(_messaging_observations(traces))

    if system:
        services: set[str] = set()
        for frame in (traces, metrics, logs):
            if "service_name" not in frame.columns:
                continue
            services |= {
                value
                for raw in frame["service_name"].dropna().unique().tolist()
                if (value := _clean(raw))
            }
        for service in sorted(services):
            source = entity("system", system)
            target = entity("service", service)
            observations.append(
                RelationObservation(
                    _observation_id("system_inventory", source, target),
                    source,
                    target,
                    "system_inventory",
                    1.0,
                    f"System inventory explicitly places service {service} in system {system}.",
                )
            )

    return _dedupe_observations(observations)


class AbductiveStructuralRelationGenerator:
    """Generate type-compatible structural triple hypotheses from observations.

    The generator never forms a Cartesian product over all graph nodes. Candidate
    endpoints must be grounded in a model-visible RelationObservation, and the
    relation type must be allowed by the ontology schema. This is the Stage-1
    answer to unconstrained relation-hypothesis explosion.
    """

    def __init__(
        self,
        schema: dict[tuple[str, str], tuple[str, ...]] | None = None,
        generic_prior: float = 0.35,
    ):
        if not 0.0 <= generic_prior <= 1.0:
            raise ValueError("generic_prior must be in [0, 1]")
        self.schema = schema or STRUCTURAL_RELATION_SCHEMA
        self.generic_prior = generic_prior

    def generate(self, observations: list[RelationObservation]) -> list[StructuralHypothesis]:
        support: dict[tuple[str, str, str], list[tuple[RelationObservation, float]]] = defaultdict(list)

        for obs in observations:
            allowed = self.schema.get((entity_kind(obs.source), entity_kind(obs.target)), ())
            if not allowed:
                continue
            relation_priors = _OBSERVATION_RELATION_PRIOR.get(obs.evidence_kind, {})
            for relation in allowed:
                evidence_prior = relation_priors.get(relation, self.generic_prior)
                score = max(0.0, min(1.0, obs.confidence * evidence_prior))
                support[(obs.source, relation, obs.target)].append((obs, score))

        hypotheses: list[StructuralHypothesis] = []
        for (source, relation, target), rows in support.items():
            # Noisy-OR combines independent *kinds* of evidence while duplicate
            # telemetry rows were already collapsed by collect_structural_observations.
            by_kind: dict[str, float] = {}
            for obs, score in rows:
                by_kind[obs.evidence_kind] = max(by_kind.get(obs.evidence_kind, 0.0), score)
            residual = 1.0
            for score in by_kind.values():
                residual *= 1.0 - score
            abductive_support = 1.0 - residual
            observation_ids = sorted({obs.observation_id for obs, _ in rows})
            evidence_kinds = sorted({obs.evidence_kind for obs, _ in rows})
            hypotheses.append(
                StructuralHypothesis(
                    edge=CausalEdge(source, relation, target),
                    observation_ids=observation_ids,
                    explanation=(
                        f"Abducted structural relation {source} --{relation}--> {target} "
                        f"from evidence kinds {evidence_kinds}."
                    ),
                    abductive_support=abductive_support,
                )
            )

        return sorted(
            hypotheses,
            key=lambda h: (-h.abductive_support, h.edge.source, h.edge.relation, h.edge.target),
        )


@dataclass
class StructuralRecoveryResult:
    observations: list[RelationObservation]
    hypotheses: list[StructuralHypothesis]
    relations: list[CausalEdge]


class StructuralRelationRecovery:
    """Stage-1 Observation -> Abduction -> Semantic -> PSL recovery pipeline."""

    def __init__(
        self,
        generator: AbductiveStructuralRelationGenerator | None = None,
        semantic_scorer=None,
        global_inference=None,
        relation_threshold: float = 0.5,
    ):
        if not 0.0 <= relation_threshold <= 1.0:
            raise ValueError("relation_threshold must be in [0, 1]")
        self.generator = generator or AbductiveStructuralRelationGenerator()
        self.semantic_scorer = semantic_scorer
        self.global_inference = global_inference
        self.relation_threshold = relation_threshold

    def run(self, observations: list[RelationObservation]) -> StructuralRecoveryResult:
        hypotheses = self.generator.generate(observations)

        if self.semantic_scorer is not None:
            if not hasattr(self.semantic_scorer, "score_structural_many"):
                raise TypeError("structural semantic scorer must implement score_structural_many")
            scores = self.semantic_scorer.score_structural_many(observations, hypotheses)
            if len(scores) != len(hypotheses):
                raise RuntimeError("structural semantic scorer returned a mismatched score count")
            for hypothesis, score in zip(hypotheses, scores):
                hypothesis.semantic_support = score.support
                hypothesis.semantic_contradiction = score.contradiction
                hypothesis.semantic_neutral = score.neutral

        if self.global_inference is not None:
            if not hasattr(self.global_inference, "infer_structural"):
                raise TypeError("structural global inference must implement infer_structural")
            hypotheses = self.global_inference.infer_structural(observations, hypotheses)
        else:
            hypotheses.sort(key=lambda h: h.final_score, reverse=True)

        selected = sorted(
            {h.edge for h in hypotheses if h.final_score >= self.relation_threshold},
            key=lambda edge: edge.key(),
        )
        return StructuralRecoveryResult(list(observations), hypotheses, selected)


def recover_structural_relations(
    traces: pd.DataFrame,
    metrics: pd.DataFrame | None = None,
    logs: pd.DataFrame | None = None,
    system: str | None = None,
    semantic_scorer=None,
    global_inference=None,
    relation_threshold: float = 0.5,
) -> StructuralRecoveryResult:
    observations = collect_structural_observations(traces, metrics, logs, system=system)
    return StructuralRelationRecovery(
        semantic_scorer=semantic_scorer,
        global_inference=global_inference,
        relation_threshold=relation_threshold,
    ).run(observations)


def extract_structural_relations(
    traces: pd.DataFrame,
    metrics: pd.DataFrame | None = None,
    logs: pd.DataFrame | None = None,
    system: str | None = None,
) -> list[CausalEdge]:
    """Backward-compatible wrapper returning Stage-1 recovered relations.

    Older scripts imported this function as a deterministic extractor. The name
    is retained, but the implementation now explicitly goes through relation
    observation and abductive hypothesis generation. Research experiments should
    prefer ``recover_structural_relations`` so hypotheses/scores remain visible.
    """

    return recover_structural_relations(traces, metrics, logs, system=system).relations


def propagation_service_edges(relations: list[CausalEdge]) -> list[CausalEdge]:
    """Project CALLS triples to Stage-2 service propagation candidates.

    CALLS is stored in the natural topology direction ``caller -> callee``.
    For the current synchronous service-level OpenRCA evaluator, a downstream
    failure can propagate to its caller, so the candidate causal direction is
    intentionally reversed: ``callee -> caller``. This projection is an
    eligibility transform, not a causal assertion.
    """

    pairs: set[tuple[str, str]] = set()
    for edge in relations:
        if edge.relation != REL_CALLS:
            continue
        if entity_kind(edge.source) != "service" or entity_kind(edge.target) != "service":
            continue
        caller = entity_value(edge.source)
        callee = entity_value(edge.target)
        if caller and callee and caller != callee:
            pairs.add((callee, caller))
    return [CausalEdge(source, REL_OBSERVED, target) for source, target in sorted(pairs)]


def relation_type_counts(relations: list[CausalEdge]) -> dict[str, int]:
    return dict(sorted(Counter(edge.relation for edge in relations).items()))


def observation_type_counts(observations: list[RelationObservation]) -> dict[str, int]:
    return dict(sorted(Counter(item.evidence_kind for item in observations).items()))


def _mask_rank(case_id: str, seed: int, edge: CausalEdge) -> bytes:
    payload = f"{seed}:{case_id}:{edge.source}|{edge.relation}|{edge.target}"
    return hashlib.sha256(payload.encode("utf-8")).digest()


def mask_structural_relation_types(
    case: RcaCase,
    ratio: float,
    seed: int = 42,
) -> tuple[RcaCase, list[CausalEdge]]:
    """Diagnostic-only typed-relation label masking.

    Endpoint types can reveal predicates (e.g. service->database), so this must
    not be reported as the main structural-recovery experiment. The function is
    retained only for boundary/unit/stress tests.
    """
    if not 0.0 <= ratio <= 1.0:
        raise ValueError("ratio must be in [0, 1]")

    eligible = [
        edge for edge in case.structural_relations if edge.relation in STRUCTURAL_RELATION_TYPES
    ]
    ordered = sorted(eligible, key=lambda edge: _mask_rank(case.case_id, seed, edge))
    n_mask = round(len(ordered) * ratio)
    masked_keys = {edge.key() for edge in ordered[:n_mask]}

    visible_relations: list[CausalEdge] = []
    truth: list[CausalEdge] = []
    for edge in case.structural_relations:
        if edge.key() in masked_keys:
            truth.append(edge)
            visible_relations.append(CausalEdge(edge.source, REL_STRUCTURAL_MASKED, edge.target))
        else:
            visible_relations.append(edge)

    visible = RcaCase(
        case_id=case.case_id,
        symptom_nodes=list(case.symptom_nodes),
        known_edges=list(case.known_edges),
        evidence=list(case.evidence),
        gold_root_causes=list(case.gold_root_causes),
        gold_edges=list(case.gold_edges),
        gold_paths=[list(path) for path in case.gold_paths],
        gold_alarm_nodes=list(case.gold_alarm_nodes),
        metadata={
            **case.metadata,
            "structural_mask_ratio": ratio,
            "structural_mask_seed": seed,
            "structural_mask_policy": "diagnostic_nested_hash_relation_semantics",
        },
        structural_relations=visible_relations,
        relation_observations=list(case.relation_observations),
    )
    return visible, truth


@dataclass(frozen=True)
class StructuralRelationScore:
    precision: float
    recall: float
    f1: float


def structural_relation_metrics(
    predicted: list[CausalEdge],
    truth: list[CausalEdge],
) -> StructuralRelationScore:
    pred = {edge.key() for edge in predicted if edge.relation in STRUCTURAL_RELATION_TYPES}
    gold = {edge.key() for edge in truth if edge.relation in STRUCTURAL_RELATION_TYPES}
    tp = len(pred & gold)
    precision = tp / len(pred) if pred else (1.0 if not gold else 0.0)
    recall = tp / len(gold) if gold else 1.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return StructuralRelationScore(precision, recall, f1)
