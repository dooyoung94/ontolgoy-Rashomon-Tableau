from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from openrca_mr.openrca2 import load_normalized_cases


def run(data: str, out: str) -> dict:
    cases = load_normalized_cases(data)
    relation_counts: Counter[str] = Counter()
    observation_counts: Counter[str] = Counter()
    case_type_counts: Counter[str] = Counter()
    examples: dict[str, list[list[str]]] = {}
    with_any_relation = 0
    with_any_observation = 0
    candidate_total = 0

    for case in cases:
        if case.structural_relations:
            with_any_relation += 1
        if case.relation_observations:
            with_any_observation += 1
        candidate_total += int(case.metadata.get("structural_candidate_count", 0) or 0)

        seen_types = set()
        for item in case.relation_observations:
            observation_counts[item.evidence_kind] += 1
        for edge in case.structural_relations:
            relation_counts[edge.relation] += 1
            seen_types.add(edge.relation)
            examples.setdefault(edge.relation, [])
            if len(examples[edge.relation]) < 5:
                examples[edge.relation].append([edge.source, edge.relation, edge.target])
        for relation in seen_types:
            case_type_counts[relation] += 1

    result = {
        "n_cases": len(cases),
        "cases_with_any_relation_observation": with_any_observation,
        "observation_coverage_any": with_any_observation / len(cases) if cases else 0.0,
        "cases_with_any_recovered_structural_relation": with_any_relation,
        "relation_coverage_any": with_any_relation / len(cases) if cases else 0.0,
        "total_relation_observations": sum(observation_counts.values()),
        "mean_relation_observations_per_case": (
            sum(observation_counts.values()) / len(cases) if cases else 0.0
        ),
        "observation_counts": dict(sorted(observation_counts.items())),
        "total_structural_candidates": candidate_total,
        "mean_structural_candidates_per_case": candidate_total / len(cases) if cases else 0.0,
        "total_recovered_structural_relations": sum(relation_counts.values()),
        "mean_recovered_structural_relations_per_case": (
            sum(relation_counts.values()) / len(cases) if cases else 0.0
        ),
        "relation_counts": dict(sorted(relation_counts.items())),
        "case_coverage_by_relation": {
            relation: {
                "cases": case_type_counts[relation],
                "rate": case_type_counts[relation] / len(cases) if cases else 0.0,
            }
            for relation in sorted(case_type_counts)
        },
        "examples": examples,
        "note": (
            "Relation observations and recovered triples use model-visible telemetry only. "
            "PAVE causal_graph.json is evaluator-only. This audit is a coverage/sanity check, "
            "not the paper's main structural-recovery score; main Stage-S evaluation requires "
            "independent reference triples or controlled evidence missingness."
        ),
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", default="results/structural_relation_audit.json")
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
