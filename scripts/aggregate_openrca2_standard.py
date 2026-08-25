from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from statistics import mean

METRIC_KEYS = [
    "root_service_precision",
    "root_service_recall",
    "root_service_f1",
    "root_service_exact",
    "any_service_hit",
    "all_service_hit",
    "path_reachability",
    "node_precision",
    "node_recall",
    "node_f1",
    "edge_precision",
    "edge_recall",
    "edge_f1",
]


def summarize(rows: list[dict]) -> dict:
    return {
        key: mean(float(row[key]) for row in rows) if rows else 0.0
        for key in METRIC_KEYS
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glob", dest="pattern", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--md-out", required=True)
    parser.add_argument("--expected", type=int, default=500)
    args = parser.parse_args()

    files = sorted(glob.glob(args.pattern))
    if not files:
        raise RuntimeError(f"no result files matched {args.pattern}")

    rows: list[dict] = []
    predictions: list[dict] = []
    seen = set()
    for filename in files:
        payload = json.loads(Path(filename).read_text(encoding="utf-8"))
        for row in payload.get("rows", []):
            case_id = str(row["case_id"])
            if case_id in seen:
                raise RuntimeError(f"duplicate case in standard results: {case_id}")
            seen.add(case_id)
            rows.append(row)
        predictions.extend(payload.get("predictions", []))

    if len(rows) != args.expected:
        raise RuntimeError(f"expected {args.expected} standard cases, got {len(rows)}")

    systems = sorted({str(row.get("system", "unknown")) for row in rows})
    per_system = {}
    for system in systems:
        subset = [row for row in rows if str(row.get("system", "unknown")) == system]
        per_system[system] = {"n": len(subset), **summarize(subset)}

    summary = summarize(rows)
    result = {
        "dataset_id": "anon-ops/ops-lite:standard-all-500",
        "method": "Abduction+DeBERTa+PSL",
        "n": len(rows),
        "summary": summary,
        "per_system": per_system,
        "protocol": {
            "masking": "none",
            "topology_input": "no prebuilt dependency graph; endpoint connectivity inferred from normal+abnormal traces",
            "gold_usage": "evaluation only",
            "directly_comparable_metrics": ["any_service_hit", "path_reachability", "node_f1", "edge_f1"],
            "not_yet_comparable": ["fault-kind pair F1", "fault-kind exact match", "fault-kind accuracy", "SQL Exec"],
        },
        "rows": rows,
        "predictions": predictions,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# OpenRCA 2.0 Standard Direct Comparison — A4",
        "",
        f"Cases: **{len(rows)}**",
        "",
        "No relation masking. No prebuilt topology is supplied. Structural endpoint connectivity is reconstructed from the paired trace telemetry and PAVE gold is evaluation-only.",
        "",
        "| Scope | N | AnySvc | PR | Node-F1 | Edge-F1 | Root-service F1 | Root exact |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def pct(x):
        return f"{100.0 * float(x):.2f}%"

    md.append(
        "| All | {n} | {any} | {pr} | {node} | {edge} | {rootf1} | {exact} |".format(
            n=len(rows),
            any=pct(summary["any_service_hit"]),
            pr=pct(summary["path_reachability"]),
            node=pct(summary["node_f1"]),
            edge=pct(summary["edge_f1"]),
            rootf1=pct(summary["root_service_f1"]),
            exact=pct(summary["root_service_exact"]),
        )
    )
    for system, values in per_system.items():
        md.append(
            "| {system} | {n} | {any} | {pr} | {node} | {edge} | {rootf1} | {exact} |".format(
                system=system,
                n=values["n"],
                any=pct(values["any_service_hit"]),
                pr=pct(values["path_reachability"]),
                node=pct(values["node_f1"]),
                edge=pct(values["edge_f1"]),
                rootf1=pct(values["root_service_f1"]),
                exact=pct(values["root_service_exact"]),
            )
        )
    md.extend([
        "",
        "Official outcome F1/EM are intentionally not reported here because A4 does not yet emit the benchmark's observable fault_kind label. Process metrics and AnySvc are directly comparable.",
    ])
    Path(args.md_out).write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
