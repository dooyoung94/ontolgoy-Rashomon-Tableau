from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .models import RcaCase, STRUCTURAL_RELATION_TYPES


REFERENCE_PROVENANCE_KEY = "reference_topology_provenance"

# These legacy adapter values mean that the alleged reference topology was
# produced by the same observation-to-hypothesis path that is evaluated later.
# Such data is useful for software smoke tests, but not as independent gold.
_DERIVED_SOURCE_MARKERS = (
    "telemetry",
    "collector",
    "observation_abduction",
    "recover_structural_relations",
)
_MUTABLE_VERSION_MARKERS = frozenset({"latest", "main", "master", "head", "current", "unknown"})


@dataclass(frozen=True)
class ReferenceAudit:
    claim_scope: str
    independent_reference: bool
    reference_data_provided: bool
    n_input_cases: int
    n_reference_cases: int
    topology_groups: list[str]
    issues: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def topology_group_id(case: RcaCase) -> str:
    """Return the stable topology unit shared by incidents from one system.

    Incident IDs must not drive topology masking. Otherwise every incident sees
    a different incomplete CMDB even when it belongs to the same deployment.
    Adapters should set ``topology_id``; ``system`` is the compatibility fallback.
    """

    value = case.metadata.get("topology_id") or case.metadata.get("system")
    return str(value).strip() if value is not None and str(value).strip() else case.case_id


def _typed_relation_count(case: RcaCase) -> int:
    return sum(edge.relation in STRUCTURAL_RELATION_TYPES for edge in case.structural_relations)


def _has_explicit_topology_group(case: RcaCase) -> bool:
    return any(
        case.metadata.get(key) is not None
        and bool(str(case.metadata.get(key)).strip())
        for key in ("topology_id", "system")
    )


def _case_provenance_issues(case: RcaCase) -> list[str]:
    issues: list[str] = []
    provenance = case.metadata.get(REFERENCE_PROVENANCE_KEY)
    prefix = f"case {case.case_id}"
    declared_source = ""

    if not isinstance(provenance, dict):
        issues.append(f"{prefix}: missing {REFERENCE_PROVENANCE_KEY}")
    else:
        declared_source = str(provenance.get("source", "")).strip().lower()
        if not declared_source:
            issues.append(f"{prefix}: reference source is empty")
        declared_version = str(provenance.get("version", "")).strip()
        if not declared_version:
            issues.append(f"{prefix}: reference version is empty")
        elif declared_version.lower() in _MUTABLE_VERSION_MARKERS:
            issues.append(f"{prefix}: reference version must be immutable")
        if provenance.get("independent_of_model_observations") is not True:
            issues.append(
                f"{prefix}: independent_of_model_observations must be true"
            )
        if provenance.get("evaluator_only") is not True:
            issues.append(f"{prefix}: evaluator_only must be true")

    derived_source_text = " ".join(
        [declared_source]
        + [
            str(case.metadata.get(key, "")).lower()
            for key in (
                "structural_relation_source",
                "structural_normalization_policy",
            )
        ]
    )
    if any(marker in derived_source_text for marker in _DERIVED_SOURCE_MARKERS):
        issues.append(f"{prefix}: reference topology is derived from model observations")
    if _typed_relation_count(case) == 0:
        issues.append(f"{prefix}: reference topology has no evaluable typed relations")
    relation_keys = [edge.key() for edge in case.structural_relations]
    if len(relation_keys) != len(set(relation_keys)):
        issues.append(f"{prefix}: reference topology contains duplicate relations")
    return issues


def audit_reference_protocol(
    input_cases: list[RcaCase],
    reference_cases: list[RcaCase],
    *,
    data: str,
    reference_data: str | None,
    allow_derived_reference: bool,
) -> ReferenceAudit:
    """Validate whether a run may be interpreted as a primary experiment.

    ``allow_derived_reference`` never upgrades a reference to independent. It
    only permits an explicitly labelled diagnostic run for unit/CI validation.
    """

    if not input_cases:
        raise ValueError("input data contains no cases")
    if not reference_cases:
        raise ValueError("reference data contains no cases")

    issues: list[str] = []
    provided = reference_data is not None
    if not provided:
        issues.append("independent reference_data was not provided")
    else:
        try:
            if Path(data).resolve() == Path(reference_data).resolve():
                issues.append("data and reference_data resolve to the same file")
        except OSError:
            # Path resolution is a guard, not a reason to hide the more useful
            # provenance validation below.
            issues.append("data/reference path identity could not be verified")

    for case in reference_cases:
        issues.extend(_case_provenance_issues(case))

    reference_by_id = {case.case_id: case for case in reference_cases}
    group_relation_sets: dict[str, set[tuple[str, str, str]]] = {}
    for input_case in input_cases:
        if not _has_explicit_topology_group(input_case):
            issues.append(
                f"case {input_case.case_id}: primary evaluation requires an explicit "
                "topology_id or system; incident case_id fallback is diagnostic-only"
            )
        reference_case = reference_by_id.get(input_case.case_id)
        if reference_case is None:
            continue
        input_group = topology_group_id(input_case)
        reference_group = topology_group_id(reference_case)
        if input_group != reference_group:
            issues.append(
                f"case {input_case.case_id}: input/reference topology groups differ "
                f"({input_group!r} != {reference_group!r})"
            )
        relation_set = {edge.key() for edge in reference_case.structural_relations}
        prior = group_relation_sets.setdefault(reference_group, relation_set)
        if prior != relation_set:
            issues.append(
                f"topology group {reference_group}: reference relation sets differ "
                "across cases; use a versioned topology_id or time-align the snapshot"
            )

    independent = provided and not issues
    if not independent and not allow_derived_reference:
        preview = "; ".join(issues[:8])
        if len(issues) > 8:
            preview += f"; ... ({len(issues) - 8} more)"
        raise ValueError(
            "primary evaluation requires an independent, evaluator-only topology "
            f"reference: {preview}. Use allow_derived_reference=True only for "
            "diagnostic smoke tests; those results are not paper evidence."
        )

    return ReferenceAudit(
        claim_scope="primary" if independent else "diagnostic_only",
        independent_reference=independent,
        reference_data_provided=provided,
        n_input_cases=len(input_cases),
        n_reference_cases=len(reference_cases),
        topology_groups=sorted({topology_group_id(case) for case in input_cases}),
        issues=issues,
    )
