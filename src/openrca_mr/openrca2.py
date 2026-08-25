from __future__ import annotations

import json
from pathlib import Path

from .models import CausalEdge, Evidence, RcaCase


def load_normalized_cases(path: str | Path) -> list[RcaCase]:
    """Load the repository's leakage-safe normalized OpenRCA 2.0 format.

    The upstream OpenRCA 2.0 release may evolve independently. Conversion from
    its raw telemetry/PAVE annotations belongs in a dataset adapter; the core
    reasoner consumes this stable JSONL schema so gold process annotations stay
    separated from model-visible inputs.
    """

    cases: list[RcaCase] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            cases.append(
                RcaCase(
                    case_id=str(row["case_id"]),
                    symptom_nodes=[str(x) for x in row.get("symptom_nodes", [])],
                    known_edges=[_edge(x) for x in row.get("known_edges", [])],
                    evidence=[_evidence(x) for x in row.get("evidence", [])],
                    gold_root_causes=[str(x) for x in row.get("gold_root_causes", [])],
                    gold_edges=[_edge(x) for x in row.get("gold_edges", [])],
                    gold_paths=[[str(v) for v in path] for path in row.get("gold_paths", [])],
                    metadata=dict(row.get("metadata", {})),
                )
            )
    return cases


def dump_normalized_cases(cases: list[RcaCase], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(_case_to_dict(case), ensure_ascii=False) + "\n")


def _edge(value) -> CausalEdge:
    if isinstance(value, dict):
        return CausalEdge(str(value["source"]), str(value.get("relation", "causal_propagates_to")), str(value["target"]))
    source, relation, target = value
    return CausalEdge(str(source), str(relation), str(target))


def _evidence(value: dict) -> Evidence:
    return Evidence(
        evidence_id=str(value["evidence_id"]),
        node=str(value["node"]),
        kind=str(value["kind"]),
        signal=str(value["signal"]),
        abnormality=float(value["abnormality"]),
        timestamp=float(value["timestamp"]) if value.get("timestamp") is not None else None,
        text=str(value.get("text", "")),
        metadata=dict(value.get("metadata", {})),
    )


def _case_to_dict(case: RcaCase) -> dict:
    return {
        "case_id": case.case_id,
        "symptom_nodes": case.symptom_nodes,
        "known_edges": [edge.__dict__ for edge in case.known_edges],
        "evidence": [e.__dict__ for e in case.evidence],
        "gold_root_causes": case.gold_root_causes,
        "gold_edges": [edge.__dict__ for edge in case.gold_edges],
        "gold_paths": case.gold_paths,
        "metadata": case.metadata,
    }
