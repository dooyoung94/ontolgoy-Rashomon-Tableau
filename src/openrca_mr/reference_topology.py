from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from .models import (
    CausalEdge,
    RcaCase,
    REL_CALLS,
    REL_DEPLOYED_ON,
    REL_HAS_SERVICE,
    REL_RUNS_ON,
    REL_USES_DATABASE,
)
from .openrca2 import dump_normalized_cases, load_normalized_cases
from .research_protocol import REFERENCE_PROVENANCE_KEY, topology_group_id
from .structural import STRUCTURAL_RELATION_SCHEMA, entity_kind


PRIMARY_REFERENCE_RELATION_TYPES = frozenset({REL_CALLS, REL_USES_DATABASE})
AUXILIARY_REFERENCE_RELATION_TYPES = frozenset({REL_HAS_SERVICE})
TEMPORAL_REFERENCE_RELATION_TYPES = frozenset({REL_DEPLOYED_ON, REL_RUNS_ON})

_REQUIRED_COLUMNS = frozenset({"topology_group", "source", "relation", "target"})
_PROHIBITED_SOURCE_MARKERS = (
    "telemetry",
    "collector",
    "observation_abduction",
    "recover_structural_relations",
)
_MUTABLE_VERSION_MARKERS = frozenset({"latest", "main", "master", "head", "current", "unknown"})
REFERENCE_CONTRACT_VERSION = "independent-topology-reference-v1"


def _clean(value: object) -> str:
    return str(value or "").strip()


def _validate_source_declaration(source: str, version: str) -> None:
    if not source:
        raise ValueError("reference source must not be empty")
    if not version:
        raise ValueError("reference version must not be empty")
    if version.lower() in _MUTABLE_VERSION_MARKERS:
        raise ValueError("reference version must be an immutable commit or export ID")
    normalized = source.lower()
    if any(marker in normalized for marker in _PROHIBITED_SOURCE_MARKERS):
        raise ValueError(
            "reference source declares a telemetry/observation-derived topology; "
            "it is not an independent evaluation reference"
        )


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_external_relations(
    path: str | Path,
    *,
    include_auxiliary_has_service: bool,
) -> dict[str, list[CausalEdge]]:
    allowed = set(PRIMARY_REFERENCE_RELATION_TYPES)
    if include_auxiliary_has_service:
        allowed.update(AUXILIARY_REFERENCE_RELATION_TYPES)

    grouped: dict[str, list[CausalEdge]] = defaultdict(list)
    seen: set[tuple[str, str, str, str]] = set()
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing_columns = sorted(_REQUIRED_COLUMNS - columns)
        if missing_columns:
            raise ValueError(
                "external topology CSV is missing required columns: "
                + ", ".join(missing_columns)
            )

        for line_number, row in enumerate(reader, start=2):
            group = _clean(row.get("topology_group"))
            source = _clean(row.get("source"))
            relation = _clean(row.get("relation"))
            target = _clean(row.get("target"))
            if not all((group, source, relation, target)):
                raise ValueError(f"external topology CSV line {line_number} has an empty field")

            if relation in TEMPORAL_REFERENCE_RELATION_TYPES:
                raise ValueError(
                    f"external topology CSV line {line_number}: {relation} is snapshot-dependent. "
                    "DEPLOYED_ON/RUNS_ON are prohibited until both the incident topology "
                    "snapshot and relation effective interval are time-aligned"
                )
            if relation not in allowed:
                allowed_text = ", ".join(sorted(allowed))
                raise ValueError(
                    f"external topology CSV line {line_number}: unsupported relation "
                    f"{relation!r}; allowed relations are {allowed_text}"
                )

            schema_relations = STRUCTURAL_RELATION_SCHEMA.get(
                (entity_kind(source), entity_kind(target)), ()
            )
            if relation not in schema_relations:
                raise ValueError(
                    f"external topology CSV line {line_number}: ontology domain/range "
                    f"does not permit {source} --{relation}--> {target}"
                )

            key = (group, source, relation, target)
            if key in seen:
                raise ValueError(
                    f"external topology CSV line {line_number}: duplicate relation {key}"
                )
            seen.add(key)
            grouped[group].append(CausalEdge(source, relation, target))

    if not grouped:
        raise ValueError("external topology CSV contains no relations")
    return {
        group: sorted(relations, key=lambda edge: edge.key())
        for group, relations in grouped.items()
    }


def build_independent_reference(
    *,
    data: str | Path,
    external_topology_csv: str | Path,
    out: str | Path,
    source: str,
    version: str,
    independent_attested: bool,
    include_auxiliary_has_service: bool = False,
) -> list[RcaCase]:
    """Build an evaluator-only reference from a versioned external topology.

    The function deliberately does not derive relations from ``data``. Input cases
    are used only to map case IDs to stable topology groups. The caller must attest
    that the external artifact was produced independently of model observations;
    software validation can record this declaration but cannot prove it.
    """

    _validate_source_declaration(_clean(source), _clean(version))
    if not independent_attested:
        raise ValueError(
            "independent_attested must be true; do not create a primary reference "
            "until the external source is verified independent of model observations"
        )

    try:
        if Path(data).resolve() == Path(external_topology_csv).resolve():
            raise ValueError("input data and external topology CSV must be different files")
    except OSError as exc:
        raise ValueError("input/reference path identity could not be verified") from exc

    cases = load_normalized_cases(data)
    if not cases:
        raise ValueError("input data contains no cases")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("input data contains duplicate case_id values")
    missing_explicit_groups = sorted(
        case.case_id
        for case in cases
        if not any(
            case.metadata.get(key) is not None
            and bool(str(case.metadata.get(key)).strip())
            for key in ("topology_id", "system")
        )
    )
    if missing_explicit_groups:
        raise ValueError(
            "input cases require an explicit topology_id or system; case_id fallback "
            "would create incident-specific masks: " + ", ".join(missing_explicit_groups)
        )

    relations_by_group = _load_external_relations(
        external_topology_csv,
        include_auxiliary_has_service=include_auxiliary_has_service,
    )
    input_groups = {topology_group_id(case) for case in cases}
    missing_groups = sorted(input_groups - set(relations_by_group))
    unknown_groups = sorted(set(relations_by_group) - input_groups)
    if missing_groups:
        raise ValueError(
            "external topology CSV is missing input topology groups: "
            + ", ".join(missing_groups)
        )
    if unknown_groups:
        raise ValueError(
            "external topology CSV contains groups absent from input data: "
            + ", ".join(unknown_groups)
        )

    provenance = {
        "contract_version": REFERENCE_CONTRACT_VERSION,
        "source": _clean(source),
        "version": _clean(version),
        "external_artifact_sha256": _sha256(external_topology_csv),
        "independent_of_model_observations": True,
        "independence_attested_by_user": True,
        "evaluator_only": True,
        "primary_relation_types": sorted(PRIMARY_REFERENCE_RELATION_TYPES),
        "auxiliary_relation_types": (
            sorted(AUXILIARY_REFERENCE_RELATION_TYPES)
            if include_auxiliary_has_service
            else []
        ),
        "temporal_relations_included": False,
    }

    reference_cases: list[RcaCase] = []
    for case in cases:
        group = topology_group_id(case)
        metadata = {
            "topology_id": group,
            REFERENCE_PROVENANCE_KEY: dict(provenance),
        }
        if case.metadata.get("system") is not None:
            metadata["system"] = case.metadata["system"]
        reference_cases.append(
            RcaCase(
                case_id=case.case_id,
                symptom_nodes=[],
                known_edges=[],
                evidence=[],
                metadata=metadata,
                structural_relations=list(relations_by_group[group]),
            )
        )

    output_path = Path(out)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    dump_normalized_cases(reference_cases, temporary)
    temporary.replace(output_path)
    return reference_cases
