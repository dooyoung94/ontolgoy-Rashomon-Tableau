from __future__ import annotations

import csv

import pytest

from openrca_mr.models import RcaCase
from openrca_mr.openrca2 import dump_normalized_cases, load_normalized_cases
from openrca_mr.reference_topology import build_independent_reference


def _write_csv(path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["topology_group", "source", "relation", "target"]
        )
        writer.writeheader()
        writer.writerows(rows)


def _input(path) -> None:
    dump_normalized_cases(
        [
            RcaCase("case-a", [], [], [], metadata={"topology_id": "shop-v1"}),
            RcaCase("case-b", [], [], [], metadata={"topology_id": "shop-v1"}),
        ],
        path,
    )


def test_build_reference_uses_external_relations_and_scrubs_model_inputs(tmp_path):
    data = tmp_path / "input.jsonl"
    external = tmp_path / "topology.csv"
    out = tmp_path / "reference.jsonl"
    _input(data)
    _write_csv(
        external,
        [
            {
                "topology_group": "shop-v1",
                "source": "service:frontend",
                "relation": "calls",
                "target": "service:orders",
            },
            {
                "topology_group": "shop-v1",
                "source": "service:orders",
                "relation": "uses_database",
                "target": "database:postgres:orders",
            },
        ],
    )

    built = build_independent_reference(
        data=data,
        external_topology_csv=external,
        out=out,
        source="git deployment catalog",
        version="abc123",
        independent_attested=True,
    )

    assert len(built) == 2
    loaded = load_normalized_cases(out)
    assert loaded[0].relation_observations == []
    assert loaded[0].gold_root_causes == []
    assert len(loaded[0].structural_relations) == 2
    provenance = loaded[0].metadata["reference_topology_provenance"]
    assert provenance["independent_of_model_observations"] is True
    assert provenance["evaluator_only"] is True
    assert provenance["primary_relation_types"] == ["calls", "uses_database"]
    assert len(provenance["external_artifact_sha256"]) == 64


def test_build_reference_requires_explicit_independence_attestation(tmp_path):
    data = tmp_path / "input.jsonl"
    external = tmp_path / "topology.csv"
    _input(data)
    _write_csv(
        external,
        [
            {
                "topology_group": "shop-v1",
                "source": "service:a",
                "relation": "calls",
                "target": "service:b",
            }
        ],
    )

    with pytest.raises(ValueError, match="independent_attested must be true"):
        build_independent_reference(
            data=data,
            external_topology_csv=external,
            out=tmp_path / "out.jsonl",
            source="service catalog",
            version="v1",
            independent_attested=False,
        )


def test_build_reference_rejects_temporal_relations_without_time_alignment(tmp_path):
    data = tmp_path / "input.jsonl"
    external = tmp_path / "topology.csv"
    _input(data)
    _write_csv(
        external,
        [
            {
                "topology_group": "shop-v1",
                "source": "service:orders",
                "relation": "deployed_on",
                "target": "pod:orders-1",
            }
        ],
    )

    with pytest.raises(ValueError, match="snapshot-dependent"):
        build_independent_reference(
            data=data,
            external_topology_csv=external,
            out=tmp_path / "out.jsonl",
            source="deployment manifest",
            version="v1",
            independent_attested=True,
        )


def test_build_reference_rejects_unknown_or_missing_groups(tmp_path):
    data = tmp_path / "input.jsonl"
    external = tmp_path / "topology.csv"
    _input(data)
    _write_csv(
        external,
        [
            {
                "topology_group": "other-v1",
                "source": "service:a",
                "relation": "calls",
                "target": "service:b",
            }
        ],
    )

    with pytest.raises(ValueError, match="missing input topology groups"):
        build_independent_reference(
            data=data,
            external_topology_csv=external,
            out=tmp_path / "out.jsonl",
            source="service catalog",
            version="v1",
            independent_attested=True,
        )


def test_build_reference_rejects_incident_id_as_implicit_topology_group(tmp_path):
    data = tmp_path / "input.jsonl"
    external = tmp_path / "topology.csv"
    dump_normalized_cases([RcaCase("case-a", [], [], [])], data)
    _write_csv(
        external,
        [
            {
                "topology_group": "case-a",
                "source": "service:a",
                "relation": "calls",
                "target": "service:b",
            }
        ],
    )

    with pytest.raises(ValueError, match="explicit topology_id or system"):
        build_independent_reference(
            data=data,
            external_topology_csv=external,
            out=tmp_path / "out.jsonl",
            source="service catalog",
            version="v1",
            independent_attested=True,
        )


def test_build_reference_rejects_telemetry_declared_as_external_source(tmp_path):
    data = tmp_path / "input.jsonl"
    external = tmp_path / "topology.csv"
    _input(data)
    _write_csv(
        external,
        [
            {
                "topology_group": "shop-v1",
                "source": "service:a",
                "relation": "calls",
                "target": "service:b",
            }
        ],
    )

    with pytest.raises(ValueError, match="not an independent evaluation reference"):
        build_independent_reference(
            data=data,
            external_topology_csv=external,
            out=tmp_path / "out.jsonl",
            source="telemetry-derived export",
            version="v1",
            independent_attested=True,
        )
