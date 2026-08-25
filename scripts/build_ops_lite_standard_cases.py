from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

import build_ops_lite_cases as base
from openrca_mr.models import RcaCase
from openrca_mr.openrca2 import dump_normalized_cases


def _retry_download(url: str, path: Path, max_attempts: int = 6) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    tmp = path.with_name(path.name + ".part")
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            if tmp.exists():
                tmp.unlink()
            urllib.request.urlretrieve(url, tmp)
            if not tmp.exists() or tmp.stat().st_size <= 0:
                raise IOError(f"empty download: {url}")
            tmp.replace(path)
            return
        except Exception as exc:
            last_error = exc
            if tmp.exists():
                tmp.unlink()
            if attempt == max_attempts:
                break
            delay = min(16, 2 ** (attempt - 1))
            print(f"DOWNLOAD_RETRY attempt={attempt}/{max_attempts} delay={delay}s url={url} error={type(exc).__name__}: {exc}")
            time.sleep(delay)
    raise RuntimeError(f"download failed after {max_attempts} attempts: {url}") from last_error


def _standard_case(name: str, cache: Path, manifest_root_services: list[str]) -> RcaCase:
    folder = cache / name
    files = [
        "causal_graph.json", "env.json",
        "normal_traces.parquet", "abnormal_traces.parquet",
        "normal_metrics.parquet", "abnormal_metrics.parquet",
        "normal_logs.parquet", "abnormal_logs.parquet",
    ]
    for filename in files:
        _retry_download(f"{base.BASE}/cases/{name}/{filename}?download=true", folder / filename)

    graph = base._json(folder / "causal_graph.json")
    env = base._json(folder / "env.json")
    normal_traces = base._load_parquet(folder / "normal_traces.parquet")
    abnormal_traces = base._load_parquet(folder / "abnormal_traces.parquet")
    normal_metrics = base._load_parquet(folder / "normal_metrics.parquet")
    abnormal_metrics = base._load_parquet(folder / "abnormal_metrics.parquet")
    normal_logs = base._load_parquet(folder / "normal_logs.parquet")
    abnormal_logs = base._load_parquet(folder / "abnormal_logs.parquet")

    # Standard OpenRCA2 agents can inspect both normal and abnormal telemetry.
    # This is structural endpoint discovery only; no causal label is imported.
    trace_union = pd.concat([normal_traces, abnormal_traces], ignore_index=True, sort=False)
    known_edges = base._trace_dependency_edges(trace_union)
    abnormal_start = float(env.get("ABNORMAL_START", 0.0))
    evidence = base._evidence_for_case(
        normal_traces,
        abnormal_traces,
        normal_metrics,
        abnormal_metrics,
        normal_logs,
        abnormal_logs,
        abnormal_start,
    )
    symptoms = base._symptoms(known_edges, evidence)

    # The 500-case release is manifest-driven. Service-level root GT comes from
    # manifest.root_services; causal_graph root components can be pod/container
    # entities that do not appear in component_to_service.
    _graph_roots, gold_edges, gold_alarms = base._gold_from_causal_graph(graph)
    gold_roots = [str(x) for x in manifest_root_services if str(x).strip()]
    if not gold_roots:
        raise RuntimeError(f"manifest missing root_services: {name}")
    if not gold_alarms:
        raise RuntimeError(f"causal graph missing service-level alarm nodes: {name}")

    # A valid PAVE component path can collapse entirely inside one service.
    # In that case the official service-level gold edge set is legitimately
    # empty. Keep the case in the denominator: the evaluator's empty/empty
    # boundary rule assigns Edge-F1=1 only when the model also predicts no edge.
    return RcaCase(
        case_id=name,
        symptom_nodes=symptoms,
        known_edges=known_edges,
        evidence=evidence,
        gold_root_causes=gold_roots,
        gold_edges=gold_edges,
        gold_alarm_nodes=gold_alarms,
        metadata={
            "dataset": "anon-ops/ops-lite",
            "fault_type": graph.get("fault_type"),
            "adapter": "openrca2_standard_telemetry_v3",
            "topology_source": "union(normal_traces, abnormal_traces)",
            "root_gold_source": "manifest.root_services",
            "edge_alarm_gold_source": "causal_graph.json",
            "gold_usage": "evaluation_only",
            "service_level_gold_edge_count": len(gold_edges),
        },
    )


def build_range(out: Path, cache: Path, start: int, end: int) -> list[RcaCase]:
    manifest = cache / "manifest.jsonl"
    _retry_download(f"{base.BASE}/manifest.jsonl?download=true", manifest)
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = max(0, start)
    end = min(len(rows), end)
    if end < start:
        raise ValueError("end must be >= start")

    cases: list[RcaCase] = []
    errors: list[dict] = []
    for row in rows[start:end]:
        name = str(row["name"])
        try:
            case = _standard_case(name, cache, list(row.get("root_services") or []))
        except Exception as exc:
            errors.append({"case_id": name, "error": f"{type(exc).__name__}: {exc}"})
            print("CASE_ERROR", name, errors[-1]["error"])
            continue
        case.metadata.update({
            "system": row.get("system"),
            "manifest_primary_kind": row.get("primary_kind"),
            "manifest_subtypes": row.get("subtypes", []),
            "manifest_hybrid": bool(row.get("hybrid", False)),
        })
        cases.append(case)
        print(
            "CASE", name,
            "known", len(case.known_edges),
            "evidence", len(case.evidence),
            "gold_roots", case.gold_root_causes,
            "gold_edges", len(case.gold_edges),
            "gold_alarms", len(case.gold_alarm_nodes),
        )

    stats = {
        "manifest_total": len(rows),
        "start": start,
        "end": end,
        "requested": end - start,
        "normalized": len(cases),
        "empty_service_edge_cases": sum(not c.gold_edges for c in cases),
        "errors": errors,
    }
    print(json.dumps(stats, indent=2))
    if errors:
        raise RuntimeError(f"standard shard has {len(errors)} errors: {errors}")
    if len(cases) != end - start:
        raise RuntimeError(f"standard shard coverage mismatch: expected {end-start}, got {len(cases)}")
    dump_normalized_cases(cases, out)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--cache", default=".cache/ops-lite-standard")
    parser.add_argument("--start-index", type=int, required=True)
    parser.add_argument("--end-index", type=int, required=True)
    args = parser.parse_args()
    build_range(Path(args.out), Path(args.cache), args.start_index, args.end_index)


if __name__ == "__main__":
    main()
