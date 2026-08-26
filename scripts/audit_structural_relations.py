from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from openrca_mr.openrca2 import load_normalized_cases


def run(data: str, out: str) -> dict:
    cases = load_normalized_cases(data)
    type_counts: Counter[str] = Counter()
    case_type_counts: Counter[str] = Counter()
    examples: dict[str, list[list[str]]] = {}
    with_any = 0

    for case in cases:
        if case.structural_relations:
            with_any += 1
        seen_types = set()
        for edge in case.structural_relations:
            type_counts[edge.relation] += 1
            seen_types.add(edge.relation)
            examples.setdefault(edge.relation, [])
            if len(examples[edge.relation]) < 5:
                examples[edge.relation].append([edge.source, edge.relation, edge.target])
        for relation in seen_types:
            case_type_counts[relation] += 1

    result = {
        "n_cases": len(cases),
        "cases_with_any_structural_relation": with_any,
        "coverage_any": with_any / len(cases) if cases else 0.0,
        "total_structural_relations": sum(type_counts.values()),
        "mean_structural_relations_per_case": (
            sum(type_counts.values()) / len(cases) if cases else 0.0
        ),
        "relation_counts": dict(sorted(type_counts.items())),
        "case_coverage_by_relation": {
            relation: {
                "cases": case_type_counts[relation],
                "rate": case_type_counts[relation] / len(cases) if cases else 0.0,
            }
            for relation in sorted(case_type_counts)
        },
        "examples": examples,
        "note": (
            "These are telemetry-derived operational relations, not PAVE causal gold. "
            "Absence means the released telemetry did not expose enough attributes; "
            "the extractor does not fabricate a relation."
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
