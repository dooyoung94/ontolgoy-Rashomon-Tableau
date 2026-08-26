from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .models import STRUCTURAL_RELATION_TYPES
from .reference_topology import (
    REFERENCE_SCHEMA_VERSION,
    ReferenceProvenance,
    ReferenceStatus,
    ReferenceTopology,
)
from .structural import STRUCTURAL_RELATION_SCHEMA


_ENTITY_TYPES = frozenset(
    kind for pair in STRUCTURAL_RELATION_SCHEMA for kind in pair
)
_VERIFICATION_LEVELS = frozenset({"automated", "reviewed", "manual"})
_DERIVED_SOURCE_MARKERS = (
    "observation_abduction",
    "telemetry_observation",
    "collector_observation",
    "recover_structural_relations",
)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ReferenceValidationReport:
    valid: bool
    errors: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]
    topology_count: int
    entity_count: int
    relation_count: int
    relation_status_counts: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [asdict(issue) for issue in self.errors],
            "warnings": [asdict(issue) for issue in self.warnings],
            "topology_count": self.topology_count,
            "entity_count": self.entity_count,
            "relation_count": self.relation_count,
            "relation_status_counts": dict(self.relation_status_counts),
        }


def validate_reference_topologies(
    topologies: list[ReferenceTopology],
) -> ReferenceValidationReport:
    issues: list[ValidationIssue] = []
    status_counts: Counter[str] = Counter()

    if not topologies:
        issues.append(
            ValidationIssue(
                "error",
                "EMPTY_ARTIFACT",
                "$",
                "reference topology artifact contains no topologies",
            )
        )

    seen_topology_ids: set[str] = set()
    intervals_by_system: dict[
        str, list[tuple[datetime, datetime | None, str]]
    ] = {}
    for topology_index, topology in enumerate(topologies):
        base = f"topologies[{topology_index}]"
        _required_text(
            issues, topology.schema_version, "SCHEMA_VERSION_REQUIRED", f"{base}.schema_version"
        )
        if topology.schema_version and topology.schema_version != REFERENCE_SCHEMA_VERSION:
            _error(
                issues,
                "UNSUPPORTED_SCHEMA_VERSION",
                f"{base}.schema_version",
                f"expected {REFERENCE_SCHEMA_VERSION!r}, got {topology.schema_version!r}",
            )
        _required_text(issues, topology.topology_id, "TOPOLOGY_ID_REQUIRED", f"{base}.topology_id")
        _required_text(issues, topology.system, "SYSTEM_REQUIRED", f"{base}.system")
        _required_text(issues, topology.version, "VERSION_REQUIRED", f"{base}.version")

        if topology.topology_id in seen_topology_ids:
            _error(
                issues,
                "DUPLICATE_TOPOLOGY_ID",
                f"{base}.topology_id",
                f"duplicate topology_id {topology.topology_id!r}",
            )
        seen_topology_ids.add(topology.topology_id)

        valid_from = _timestamp(
            issues, topology.valid_from, f"{base}.valid_from", required=True
        )
        valid_to = _timestamp(
            issues, topology.valid_to, f"{base}.valid_to", required=False
        )
        if valid_from and valid_to and valid_to <= valid_from:
            _error(
                issues,
                "INVALID_VALIDITY_WINDOW",
                f"{base}.valid_to",
                "valid_to must be later than valid_from",
            )
        if valid_from:
            intervals_by_system.setdefault(topology.system, []).append(
                (valid_from, valid_to, topology.topology_id)
            )

        _validate_provenance(issues, topology.provenance, f"{base}.provenance")
        _validate_topology_contents(issues, topology, base, status_counts)

    _validate_non_overlapping_intervals(issues, intervals_by_system)

    if status_counts[ReferenceStatus.VERIFIED_POSITIVE.value] == 0:
        _error(
            issues,
            "NO_VERIFIED_POSITIVES",
            "$",
            "at least one VERIFIED_POSITIVE relation is required for masking and recall",
        )
    if topologies and status_counts[ReferenceStatus.VERIFIED_NEGATIVE.value] == 0:
        _warning(
            issues,
            "NO_VERIFIED_NEGATIVES",
            "$",
            "no VERIFIED_NEGATIVE relations are available; precision is only partially auditable",
        )

    errors = tuple(issue for issue in issues if issue.severity == "error")
    warnings = tuple(issue for issue in issues if issue.severity == "warning")
    return ReferenceValidationReport(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        topology_count=len(topologies),
        entity_count=sum(len(topology.entities) for topology in topologies),
        relation_count=sum(len(topology.relations) for topology in topologies),
        relation_status_counts={
            status.value: status_counts[status.value] for status in ReferenceStatus
        },
    )


def _validate_topology_contents(
    issues: list[ValidationIssue],
    topology: ReferenceTopology,
    base: str,
    status_counts: Counter[str],
) -> None:
    entities: dict[str, str] = {}
    for entity_index, entity in enumerate(topology.entities):
        path = f"{base}.entities[{entity_index}]"
        _required_text(issues, entity.entity_id, "ENTITY_ID_REQUIRED", f"{path}.id")
        _required_text(issues, entity.entity_type, "ENTITY_TYPE_REQUIRED", f"{path}.type")
        if entity.entity_type and entity.entity_type not in _ENTITY_TYPES:
            _error(
                issues,
                "UNKNOWN_ENTITY_TYPE",
                f"{path}.type",
                f"unsupported entity type {entity.entity_type!r}",
            )
        if entity.entity_id != entity.entity_id.strip():
            _error(
                issues,
                "UNNORMALIZED_ENTITY_ID",
                f"{path}.id",
                "entity id must not contain leading or trailing whitespace",
            )
        prefix, separator, value = entity.entity_id.partition(":")
        if not separator or not value:
            _error(
                issues,
                "NON_CANONICAL_ENTITY_ID",
                f"{path}.id",
                "entity id must use the canonical '<type>:<value>' form",
            )
        elif entity.entity_type and prefix != entity.entity_type:
            _error(
                issues,
                "ENTITY_PREFIX_TYPE_MISMATCH",
                f"{path}.id",
                f"id prefix {prefix!r} does not match type {entity.entity_type!r}",
            )
        if entity.entity_id in entities:
            _error(
                issues,
                "DUPLICATE_ENTITY_ID",
                f"{path}.id",
                f"duplicate entity id {entity.entity_id!r}",
            )
        entities[entity.entity_id] = entity.entity_type

    seen_relations: dict[tuple[str, str, str], ReferenceStatus] = {}
    for relation_index, relation in enumerate(topology.relations):
        path = f"{base}.relations[{relation_index}]"
        status_counts[relation.status.value] += 1
        _required_text(issues, relation.source, "RELATION_SOURCE_REQUIRED", f"{path}.source")
        _required_text(issues, relation.relation, "RELATION_TYPE_REQUIRED", f"{path}.relation")
        _required_text(issues, relation.target, "RELATION_TARGET_REQUIRED", f"{path}.target")
        _validate_provenance(issues, relation.provenance, f"{path}.provenance")

        if relation.relation and relation.relation not in STRUCTURAL_RELATION_TYPES:
            _error(
                issues,
                "UNKNOWN_RELATION_TYPE",
                f"{path}.relation",
                f"unsupported structural relation {relation.relation!r}",
            )
        if relation.source == relation.target and relation.source:
            _error(
                issues,
                "SELF_LOOP",
                path,
                "self-loop relations are not allowed in the reference topology",
            )
        if relation.source not in entities:
            _error(
                issues,
                "MISSING_SOURCE_ENTITY",
                f"{path}.source",
                f"source entity {relation.source!r} is not declared",
            )
        if relation.target not in entities:
            _error(
                issues,
                "MISSING_TARGET_ENTITY",
                f"{path}.target",
                f"target entity {relation.target!r} is not declared",
            )
        source_type = entities.get(relation.source)
        target_type = entities.get(relation.target)
        if source_type and target_type and relation.relation:
            allowed = STRUCTURAL_RELATION_SCHEMA.get((source_type, target_type), ())
            if relation.relation not in allowed:
                _error(
                    issues,
                    "DOMAIN_RANGE_VIOLATION",
                    path,
                    f"{relation.relation!r} is not allowed for {source_type!r} -> {target_type!r}",
                )

        previous_status = seen_relations.get(relation.key())
        if previous_status is not None:
            code = (
                "RELATION_STATUS_CONFLICT"
                if previous_status is not relation.status
                else "DUPLICATE_RELATION"
            )
            _error(
                issues,
                code,
                path,
                f"duplicate relation triple {relation.key()!r}",
            )
        seen_relations[relation.key()] = relation.status


def _validate_provenance(
    issues: list[ValidationIssue], provenance: ReferenceProvenance, path: str
) -> None:
    _required_text(issues, provenance.source_type, "SOURCE_TYPE_REQUIRED", f"{path}.source_type")
    _required_text(issues, provenance.source, "SOURCE_REQUIRED", f"{path}.source")
    _required_text(issues, provenance.version, "SOURCE_VERSION_REQUIRED", f"{path}.version")
    _required_text(issues, provenance.locator, "SOURCE_LOCATOR_REQUIRED", f"{path}.locator")
    _required_text(
        issues,
        provenance.verification_level,
        "VERIFICATION_LEVEL_REQUIRED",
        f"{path}.verification_level",
    )
    if (
        provenance.verification_level
        and provenance.verification_level not in _VERIFICATION_LEVELS
    ):
        _error(
            issues,
            "INVALID_VERIFICATION_LEVEL",
            f"{path}.verification_level",
            f"expected one of {sorted(_VERIFICATION_LEVELS)}",
        )
    if provenance.independent_of_model_observations is not True:
        _error(
            issues,
            "REFERENCE_NOT_INDEPENDENT",
            f"{path}.independent_of_model_observations",
            "must be the boolean true",
        )
    if provenance.evaluator_only is not True:
        _error(
            issues,
            "REFERENCE_NOT_EVALUATOR_ONLY",
            f"{path}.evaluator_only",
            "must be the boolean true",
        )
    source_description = " ".join(
        (provenance.source_type, provenance.source, provenance.locator)
    ).lower()
    if any(marker in source_description for marker in _DERIVED_SOURCE_MARKERS):
        _error(
            issues,
            "MODEL_DERIVED_REFERENCE",
            path,
            "reference provenance points to the model observation/recovery path",
        )


def _timestamp(
    issues: list[ValidationIssue], value: str | None, path: str, *, required: bool
) -> datetime | None:
    if value is None or not str(value).strip():
        if required:
            _error(issues, "TIMESTAMP_REQUIRED", path, "timestamp is required")
        return None
    normalized = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        _error(issues, "INVALID_TIMESTAMP", path, f"invalid ISO-8601 timestamp {value!r}")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _error(
            issues,
            "TIMEZONE_REQUIRED",
            path,
            "timestamp must include an explicit timezone",
        )
        return None
    return parsed.astimezone(timezone.utc)


def _validate_non_overlapping_intervals(
    issues: list[ValidationIssue],
    intervals_by_system: dict[str, list[tuple[datetime, datetime | None, str]]],
) -> None:
    for system, rows in intervals_by_system.items():
        ordered = sorted(rows, key=lambda row: row[0])
        for previous, current in zip(ordered, ordered[1:]):
            previous_end = previous[1] or datetime.max.replace(tzinfo=timezone.utc)
            if current[0] < previous_end:
                _error(
                    issues,
                    "OVERLAPPING_TOPOLOGY_WINDOWS",
                    "$",
                    f"system {system!r} has overlapping topology windows "
                    f"for {previous[2]!r} and {current[2]!r}",
                )


def _required_text(
    issues: list[ValidationIssue], value: object, code: str, path: str
) -> None:
    if not isinstance(value, str) or not value.strip():
        _error(issues, code, path, "non-empty string is required")


def _error(
    issues: list[ValidationIssue], code: str, path: str, message: str
) -> None:
    issues.append(ValidationIssue("error", code, path, message))


def _warning(
    issues: list[ValidationIssue], code: str, path: str, message: str
) -> None:
    issues.append(ValidationIssue("warning", code, path, message))
