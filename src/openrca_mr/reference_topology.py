from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from .models import CausalEdge, RcaCase, STRUCTURAL_RELATION_TYPES
from .openrca2 import load_normalized_cases
from .research_protocol import REFERENCE_PROVENANCE_KEY, topology_group_id


REFERENCE_SCHEMA_VERSION = "1.0"


class ReferenceStatus(str, Enum):
    """Auditable state of a candidate topology relation.

    Absence from the artifact is deliberately interpreted as ``UNKNOWN``. This
    open-world rule prevents an unreviewed relation from becoming a false
    negative fact merely because no independent source could verify it.
    """

    VERIFIED_POSITIVE = "VERIFIED_POSITIVE"
    VERIFIED_NEGATIVE = "VERIFIED_NEGATIVE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ReferenceProvenance:
    source_type: str
    source: str
    version: str
    locator: str
    independent_of_model_observations: bool
    evaluator_only: bool
    verification_level: str

    @classmethod
    def from_dict(cls, value: Mapping[str, object] | None) -> "ReferenceProvenance":
        row = value or {}
        return cls(
            source_type=str(row.get("source_type", "")),
            source=str(row.get("source", "")),
            version=str(row.get("version", "")),
            locator=str(row.get("locator", "")),
            independent_of_model_observations=row.get(
                "independent_of_model_observations", False
            ),
            evaluator_only=row.get("evaluator_only", False),
            verification_level=str(row.get("verification_level", "")),
        )

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "source": self.source,
            "version": self.version,
            "locator": self.locator,
            "independent_of_model_observations": self.independent_of_model_observations,
            "evaluator_only": self.evaluator_only,
            "verification_level": self.verification_level,
        }


@dataclass(frozen=True)
class ReferenceEntity:
    entity_id: str
    entity_type: str

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ReferenceEntity":
        return cls(
            entity_id=str(value.get("id", "")),
            entity_type=str(value.get("type", "")),
        )

    def to_dict(self) -> dict:
        return {"id": self.entity_id, "type": self.entity_type}


@dataclass(frozen=True)
class ReferenceRelation:
    source: str
    relation: str
    target: str
    status: ReferenceStatus
    provenance: ReferenceProvenance

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ReferenceRelation":
        raw_status = str(value.get("status", ""))
        try:
            status = ReferenceStatus(raw_status)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in ReferenceStatus)
            raise ValueError(
                f"invalid reference relation status {raw_status!r}; expected one of {allowed}"
            ) from exc
        raw_provenance = value.get("provenance")
        provenance = ReferenceProvenance.from_dict(
            raw_provenance if isinstance(raw_provenance, Mapping) else None
        )
        return cls(
            source=str(value.get("source", "")),
            relation=str(value.get("relation", "")),
            target=str(value.get("target", "")),
            status=status,
            provenance=provenance,
        )

    def key(self) -> tuple[str, str, str]:
        return self.source, self.relation, self.target

    def edge(self) -> CausalEdge:
        return CausalEdge(self.source, self.relation, self.target)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
            "status": self.status.value,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class ReferenceTopology:
    schema_version: str
    topology_id: str
    system: str
    version: str
    valid_from: str
    valid_to: str | None
    provenance: ReferenceProvenance
    entities: tuple[ReferenceEntity, ...]
    relations: tuple[ReferenceRelation, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ReferenceTopology":
        raw_entities = value.get("entities", [])
        raw_relations = value.get("relations", [])
        if not isinstance(raw_entities, list):
            raise ValueError("reference topology entities must be a list")
        if not isinstance(raw_relations, list):
            raise ValueError("reference topology relations must be a list")
        if not all(isinstance(row, Mapping) for row in raw_entities):
            raise ValueError("each reference entity must be an object")
        if not all(isinstance(row, Mapping) for row in raw_relations):
            raise ValueError("each reference relation must be an object")
        raw_provenance = value.get("provenance")
        return cls(
            schema_version=str(value.get("schema_version", "")),
            topology_id=str(value.get("topology_id", "")),
            system=str(value.get("system", "")),
            version=str(value.get("version", "")),
            valid_from=str(value.get("valid_from", "")),
            valid_to=(
                str(value["valid_to"])
                if value.get("valid_to") is not None
                else None
            ),
            provenance=ReferenceProvenance.from_dict(
                raw_provenance if isinstance(raw_provenance, Mapping) else None
            ),
            entities=tuple(ReferenceEntity.from_dict(row) for row in raw_entities),
            relations=tuple(ReferenceRelation.from_dict(row) for row in raw_relations),
        )

    def positive_edges(self) -> list[CausalEdge]:
        return [
            item.edge()
            for item in self.relations
            if item.status is ReferenceStatus.VERIFIED_POSITIVE
        ]

    def status_index(self) -> dict[tuple[str, str, str], ReferenceStatus]:
        return {item.key(): item.status for item in self.relations}

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "topology_id": self.topology_id,
            "system": self.system,
            "version": self.version,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "provenance": self.provenance.to_dict(),
            "entities": [item.to_dict() for item in self.entities],
            "relations": [item.to_dict() for item in self.relations],
        }


@dataclass(frozen=True)
class RelationReferenceScore:
    tp_keys: frozenset[tuple[str, str, str]]
    fp_keys: frozenset[tuple[str, str, str]]
    fn_keys: frozenset[tuple[str, str, str]]
    unknown_keys: frozenset[tuple[str, str, str]]
    non_target_positive_keys: frozenset[tuple[str, str, str]]

    @property
    def tp(self) -> int:
        return len(self.tp_keys)

    @property
    def fp(self) -> int:
        return len(self.fp_keys)

    @property
    def fn(self) -> int:
        return len(self.fn_keys)

    @property
    def unknown(self) -> int:
        return len(self.unknown_keys)

    @property
    def precision(self) -> float:
        denominator = self.tp + self.fp
        return self.tp / denominator if denominator else (1.0 if self.fn == 0 else 0.0)

    @property
    def recall(self) -> float:
        denominator = self.tp + self.fn
        return self.tp / denominator if denominator else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2.0 * p * r / (p + r) if p + r else 0.0


def score_reference_relations(
    predicted: Iterable[CausalEdge],
    positive_truth: Iterable[CausalEdge],
    status_index: Mapping[tuple[str, str, str], ReferenceStatus] | None = None,
) -> RelationReferenceScore:
    """Score predictions under either closed- or open-world reference semantics.

    Legacy normalized-case references pass ``status_index=None`` and retain the
    historical closed-world behavior. Contract-v1 artifacts pass their status
    index: only ``VERIFIED_NEGATIVE`` predictions count as false positives;
    unreviewed or explicit ``UNKNOWN`` predictions are reported separately.
    """

    pred = {
        edge.key()
        for edge in predicted
        if edge.relation in STRUCTURAL_RELATION_TYPES
    }
    gold = {
        edge.key()
        for edge in positive_truth
        if edge.relation in STRUCTURAL_RELATION_TYPES
    }
    tp = pred & gold
    fn = gold - pred
    remaining = pred - gold
    if status_index is None:
        fp = remaining
        unknown: set[tuple[str, str, str]] = set()
        non_target_positive: set[tuple[str, str, str]] = set()
    else:
        fp = {
            key
            for key in remaining
            if status_index.get(key, ReferenceStatus.UNKNOWN)
            is ReferenceStatus.VERIFIED_NEGATIVE
        }
        non_target_positive = {
            key
            for key in remaining
            if status_index.get(key) is ReferenceStatus.VERIFIED_POSITIVE
        }
        unknown = remaining - fp - non_target_positive
    return RelationReferenceScore(
        tp_keys=frozenset(tp),
        fp_keys=frozenset(fp),
        fn_keys=frozenset(fn),
        unknown_keys=frozenset(unknown),
        non_target_positive_keys=frozenset(non_target_positive),
    )


def load_reference_topologies(path: str | Path) -> list[ReferenceTopology]:
    source = Path(path)
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        return []

    try:
        decoded = json.loads(text)
        rows = _topology_rows(decoded)
    except json.JSONDecodeError:
        rows = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON on reference topology line {line_number}: {exc}"
                ) from exc
            if not isinstance(row, Mapping):
                raise ValueError(
                    f"reference topology line {line_number} must contain an object"
                )
            rows.append(row)
    return [ReferenceTopology.from_dict(row) for row in rows]


def _topology_rows(decoded: object) -> list[Mapping[str, object]]:
    if isinstance(decoded, Mapping):
        if "topologies" in decoded:
            raw_rows = decoded["topologies"]
            if not isinstance(raw_rows, list):
                raise ValueError("manifest topologies must be a list")
            rows = raw_rows
        else:
            rows = [decoded]
    elif isinstance(decoded, list):
        rows = decoded
    else:
        raise ValueError("reference topology artifact must contain an object or list")
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("each reference topology must be an object")
    return list(rows)


def dump_reference_topologies(
    topologies: Iterable[ReferenceTopology], path: str | Path
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for topology in topologies:
            handle.write(json.dumps(topology.to_dict(), ensure_ascii=False) + "\n")


def is_reference_topology_artifact(path: str | Path) -> bool:
    text = Path(path).read_text(encoding="utf-8").lstrip()
    if not text:
        return False
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        first_line = next((line for line in text.splitlines() if line.strip()), "")
        try:
            decoded = json.loads(first_line)
        except json.JSONDecodeError:
            return False
    if isinstance(decoded, Mapping) and "topologies" in decoded:
        return True
    if isinstance(decoded, list):
        return bool(decoded) and isinstance(decoded[0], Mapping) and "topology_id" in decoded[0]
    return (
        isinstance(decoded, Mapping)
        and "topology_id" in decoded
        and "relations" in decoded
        and "case_id" not in decoded
    )


@dataclass(frozen=True)
class EvaluationReference:
    cases_by_id: dict[str, RcaCase]
    status_by_case: dict[
        str, dict[tuple[str, str, str], ReferenceStatus]
    ]
    topology_id_by_case: dict[str, str]
    artifact_kind: str
    validation: dict | None

    @property
    def open_world(self) -> bool:
        return self.artifact_kind == "reference_topology_contract_v1"


def load_evaluation_reference(
    input_cases: list[RcaCase], reference_data: str | None
) -> EvaluationReference:
    """Load either the contract-v1 artifact or the legacy case-level format."""

    if not reference_data or not is_reference_topology_artifact(reference_data):
        reference_cases = (
            load_normalized_cases(reference_data) if reference_data else input_cases
        )
        case_map = _unique_case_map(reference_cases, "reference data")
        return EvaluationReference(
            cases_by_id=case_map,
            status_by_case={},
            topology_id_by_case={
                case.case_id: topology_group_id(case) for case in input_cases
            },
            artifact_kind=(
                "legacy_normalized_cases" if reference_data else "embedded_cases"
            ),
            validation=None,
        )

    topologies = load_reference_topologies(reference_data)
    from .reference_validation import validate_reference_topologies

    validation = validate_reference_topologies(topologies)
    if not validation.valid:
        preview = "; ".join(
            f"{issue.code}: {issue.message}" for issue in validation.errors[:8]
        )
        if len(validation.errors) > 8:
            preview += f"; ... ({len(validation.errors) - 8} more)"
        raise ValueError(f"reference topology validation failed: {preview}")

    by_id = {topology.topology_id: topology for topology in topologies}
    by_system: dict[str, list[ReferenceTopology]] = {}
    for topology in topologies:
        by_system.setdefault(topology.system, []).append(topology)

    cases_by_id: dict[str, RcaCase] = {}
    statuses: dict[str, dict[tuple[str, str, str], ReferenceStatus]] = {}
    topology_ids: dict[str, str] = {}
    for case in input_cases:
        explicit_topology_id = str(case.metadata.get("topology_id", "")).strip()
        if explicit_topology_id:
            topology = by_id.get(explicit_topology_id)
            if topology is None:
                raise ValueError(
                    f"case {case.case_id}: topology_id {explicit_topology_id!r} "
                    "is missing from reference artifact"
                )
            binding_method = "explicit_topology_id"
        else:
            system = str(case.metadata.get("system", "")).strip()
            candidates = by_system.get(system, [])
            if len(candidates) != 1:
                raise ValueError(
                    f"case {case.case_id}: expected exactly one reference topology "
                    f"for system {system!r}, found {len(candidates)}; set metadata.topology_id"
                )
            topology = candidates[0]
            binding_method = "unique_system_diagnostic_fallback"

        metadata = dict(case.metadata)
        metadata["topology_id"] = topology.topology_id
        metadata[REFERENCE_PROVENANCE_KEY] = {
            "source": topology.provenance.source,
            "version": topology.version,
            "independent_of_model_observations": (
                topology.provenance.independent_of_model_observations
            ),
            "evaluator_only": topology.provenance.evaluator_only,
            "contract_schema_version": topology.schema_version,
            "binding_method": binding_method,
        }
        cases_by_id[case.case_id] = replace(
            case,
            structural_relations=topology.positive_edges(),
            metadata=metadata,
        )
        statuses[case.case_id] = topology.status_index()
        topology_ids[case.case_id] = topology.topology_id

    return EvaluationReference(
        cases_by_id=cases_by_id,
        status_by_case=statuses,
        topology_id_by_case=topology_ids,
        artifact_kind="reference_topology_contract_v1",
        validation=validation.to_dict(),
    )


def _unique_case_map(cases: Iterable[RcaCase], label: str) -> dict[str, RcaCase]:
    out: dict[str, RcaCase] = {}
    duplicates: set[str] = set()
    for case in cases:
        if case.case_id in out:
            duplicates.add(case.case_id)
        out[case.case_id] = case
    if duplicates:
        raise ValueError(f"duplicate case_id values in {label}: {sorted(duplicates)}")
    return out
