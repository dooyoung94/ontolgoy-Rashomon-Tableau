from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass

import pandas as pd

from .models import (
    CausalEdge,
    RcaCase,
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


def _service_call_relations(traces: pd.DataFrame) -> set[CausalEdge]:
    needed = {"trace_id", "span_id", "parent_span_id", "service_name"}
    if not needed.issubset(traces.columns):
        return set()

    parent = traces[["trace_id", "span_id", "service_name"]].dropna().rename(
        columns={"span_id": "parent_span_id", "service_name": "parent_service"}
    )
    child = traces[["trace_id", "parent_span_id", "service_name"]].dropna().rename(
        columns={"service_name": "child_service"}
    )
    child = child[child["parent_span_id"].astype(str) != ""]
    joined = child.merge(parent, on=["trace_id", "parent_span_id"], how="inner")

    out: set[CausalEdge] = set()
    for caller_raw, callee_raw in joined[["parent_service", "child_service"]].itertuples(index=False):
        caller = _clean(caller_raw)
        callee = _clean(callee_raw)
        if caller and callee and caller != callee:
            # Natural operational direction: caller -> callee.
            out.add(CausalEdge(entity("service", caller), REL_CALLS, entity("service", callee)))
    return out


def _deployment_relations(frames: list[pd.DataFrame]) -> set[CausalEdge]:
    pod_names = ("attr.k8s.pod.name", "k8s.pod.name", "resource.k8s.pod.name")
    node_names = (
        "attr.k8s.node.name",
        "k8s.node.name",
        "resource.k8s.node.name",
        "attr.host.name",
        "host.name",
    )
    out: set[CausalEdge] = set()
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
                    out.add(
                        CausalEdge(
                            entity("service", service),
                            REL_DEPLOYED_ON,
                            entity("pod", pod),
                        )
                    )

        if pod_col and node_col:
            for pod_raw, node_raw in df[[pod_col, node_col]].drop_duplicates().itertuples(index=False):
                pod = _clean(pod_raw)
                node = _clean(node_raw)
                if pod and node:
                    out.add(CausalEdge(entity("pod", pod), REL_RUNS_ON, entity("node", node)))
    return out


def _database_relations(traces: pd.DataFrame) -> set[CausalEdge]:
    if traces.empty or "service_name" not in traces.columns:
        return set()
    system_col = _first_column(
        traces,
        ("attr.db.system", "db.system", "attr.db.system.name", "db.system.name"),
    )
    if not system_col:
        return set()
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
    out: set[CausalEdge] = set()
    for row in traces[columns].drop_duplicates().itertuples(index=False, name=None):
        service = _clean(row[0])
        db_system = _clean(row[1])
        db_target = _clean(row[2]) if target_col else None
        if not service or not db_system:
            continue
        db_id = f"{db_system}:{db_target}" if db_target else db_system
        out.add(CausalEdge(entity("service", service), REL_USES_DATABASE, entity("database", db_id)))
    return out


def _messaging_relations(traces: pd.DataFrame) -> set[CausalEdge]:
    if traces.empty or "service_name" not in traces.columns:
        return set()
    system_col = _first_column(traces, ("attr.messaging.system", "messaging.system"))
    if not system_col:
        return set()
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
    out: set[CausalEdge] = set()
    for row in traces[columns].drop_duplicates().itertuples(index=False, name=None):
        service = _clean(row[0])
        messaging_system = _clean(row[1])
        destination = _clean(row[2]) if target_col else None
        if not service or not messaging_system:
            continue
        target = f"{messaging_system}:{destination}" if destination else messaging_system
        out.add(
            CausalEdge(
                entity("service", service),
                REL_USES_MESSAGING,
                entity("messaging", target),
            )
        )
    return out


def extract_structural_relations(
    traces: pd.DataFrame,
    metrics: pd.DataFrame | None = None,
    logs: pd.DataFrame | None = None,
    system: str | None = None,
) -> list[CausalEdge]:
    """Induce typed operational relations from model-visible telemetry only.

    Relation types are emitted only when the released telemetry exposes the
    corresponding evidence. PAVE causal edges and injection labels are never
    consulted by this extractor.
    """
    metrics = metrics if metrics is not None else pd.DataFrame()
    logs = logs if logs is not None else pd.DataFrame()

    relations: set[CausalEdge] = set()
    relations |= _service_call_relations(traces)
    relations |= _deployment_relations([traces, metrics, logs])
    relations |= _database_relations(traces)
    relations |= _messaging_relations(traces)

    if system:
        services = {
            entity_value(edge.source)
            for edge in relations
            if entity_kind(edge.source) == "service"
        } | {
            entity_value(edge.target)
            for edge in relations
            if entity_kind(edge.target) == "service"
        }
        for frame in (traces, metrics, logs):
            if "service_name" in frame.columns:
                services |= {
                    value
                    for raw in frame["service_name"].dropna().unique().tolist()
                    if (value := _clean(raw))
                }
        for service in services:
            relations.add(
                CausalEdge(entity("system", system), REL_HAS_SERVICE, entity("service", service))
            )

    return sorted(relations, key=lambda edge: edge.key())


def propagation_service_edges(relations: list[CausalEdge]) -> list[CausalEdge]:
    """Project typed CALLS relations to Stage-2 service propagation candidates.

    CALLS is stored in the natural topology direction ``caller -> callee``.
    Downstream service failures typically propagate upstream to callers, so the
    candidate causal direction used by the current service-only evaluator is
    intentionally reversed: ``callee -> caller``.

    Heterogeneous relations remain available in ``RcaCase.structural_relations``
    but are not silently collapsed into service-only causal edges.
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


def _mask_rank(case_id: str, seed: int, edge: CausalEdge) -> bytes:
    payload = f"{seed}:{case_id}:{edge.source}|{edge.relation}|{edge.target}"
    return hashlib.sha256(payload.encode("utf-8")).digest()


def mask_structural_relation_types(
    case: RcaCase,
    ratio: float,
    seed: int = 42,
) -> tuple[RcaCase, list[CausalEdge]]:
    """Mask Stage-1 typed relation semantics while preserving endpoint pairs.

    Stable hash ordering makes the 20/40/60% masks nested for the same case and
    seed. This is deliberately separate from Stage-2 causal/non-causal masking.
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
        structural_relations=visible_relations,
        gold_root_causes=list(case.gold_root_causes),
        gold_edges=list(case.gold_edges),
        gold_paths=[list(path) for path in case.gold_paths],
        gold_alarm_nodes=list(case.gold_alarm_nodes),
        metadata={
            **case.metadata,
            "structural_mask_ratio": ratio,
            "structural_mask_seed": seed,
            "structural_mask_policy": "nested_hash_relation_semantics",
        },
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
