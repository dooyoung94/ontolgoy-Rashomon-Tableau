from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_ops_lite_cases as adapter
from openrca_mr.models import RcaCase
from openrca_mr.openrca2 import dump_normalized_cases, load_normalized_cases
from openrca_mr.structural import (
    collect_structural_observations,
    observation_type_counts,
    recover_structural_relations,
    relation_type_counts,
)


def _ensure_case_files(name: str, cache: Path) -> Path:
    folder = cache / name
    for filename in (
        "normal_traces.parquet",
        "abnormal_traces.parquet",
        "normal_metrics.parquet",
        "abnormal_metrics.parquet",
        "normal_logs.parquet",
        "abnormal_logs.parquet",
    ):
        adapter._download(
            f"{adapter.BASE}/cases/{name}/{filename}?download=true",
            folder / filename,
        )
    return folder


def build(source: Path, cache: Path, out: Path) -> list[RcaCase]:
    source_cases = load_normalized_cases(source)
    result: list[RcaCase] = []

    for source_case in source_cases:
        folder = _ensure_case_files(source_case.case_id, cache)
        normal_traces = adapter._load_parquet(folder / "normal_traces.parquet")
        abnormal_traces = adapter._load_parquet(folder / "abnormal_traces.parquet")
        normal_metrics = adapter._load_parquet(folder / "normal_metrics.parquet")
        abnormal_metrics = adapter._load_parquet(folder / "abnormal_metrics.parquet")
        normal_logs = adapter._load_parquet(folder / "normal_logs.parquet")
        abnormal_logs = adapter._load_parquet(folder / "abnormal_logs.parquet")

        # Primary Stage-1 metric deliberately excludes HAS_SERVICE membership.
        # The case-level system label is benchmark metadata, not an explicit
        # per-service inventory relation. Feeding it to both windows would create
        # trivially stable HAS_SERVICE triples and inflate cross-window F1.
        normal_reference = recover_structural_relations(
            normal_traces,
            normal_metrics,
            normal_logs,
            system=None,
        )
        abnormal_observations = collect_structural_observations(
            abnormal_traces,
            abnormal_metrics,
            abnormal_logs,
            system=None,
        )

        case = RcaCase(
            case_id=source_case.case_id,
            symptom_nodes=[],
            known_edges=[],
            evidence=[],
            metadata={
                "dataset": "anon-ops/ops-lite",
                "system": source_case.metadata.get("system"),
                "structural_reference_protocol": (
                    "normal_window_reference_vs_abnormal_window_observations"
                ),
                "structural_reference_source": (
                    "normal_telemetry_observation_abduction_no_causal_gold"
                ),
                "structural_model_input_source": "abnormal_telemetry_relation_observations",
                "causal_gold_usage": "none",
                "system_membership_in_primary_metric": False,
                "normal_reference_relation_counts": relation_type_counts(
                    normal_reference.relations
                ),
                "normal_reference_observation_counts": observation_type_counts(
                    normal_reference.observations
                ),
                "abnormal_input_observation_counts": observation_type_counts(
                    abnormal_observations
                ),
            },
            structural_relations=list(normal_reference.relations),
            relation_observations=list(abnormal_observations),
        )
        result.append(case)
        print(
            "STAGE1_CASE",
            case.case_id,
            "reference",
            len(case.structural_relations),
            relation_type_counts(case.structural_relations),
            "abnormal_observations",
            len(case.relation_observations),
            observation_type_counts(case.relation_observations),
        )

    dump_normalized_cases(result, out)
    print(
        json.dumps(
            {
                "n": len(result),
                "source": str(source),
                "out": str(out),
                "protocol": "normal_window_reference_vs_abnormal_window_observations",
                "system_membership_in_primary_metric": False,
            },
            indent=2,
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Existing normalized OpenRCA case set")
    parser.add_argument("--cache", default=".cache/ops-lite")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    build(Path(args.source), Path(args.cache), Path(args.out))


if __name__ == "__main__":
    main()
