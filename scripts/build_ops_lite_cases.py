from __future__ import annotations

import argparse
import json
import math
import urllib.request
from pathlib import Path

import pandas as pd

from openrca_mr.models import CausalEdge, Evidence, RcaCase
from openrca_mr.openrca2 import dump_normalized_cases
from openrca_mr.structural import (
    observation_type_counts,
    propagation_service_edges,
    recover_structural_relations,
    relation_type_counts,
)

BASE = "https://huggingface.co/datasets/anon-ops/ops-lite/resolve/main"


def _download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        urllib.request.urlretrieve(url, path)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _clip01(x: float) -> float:
    if not math.isfinite(x):
        return 0.0
    return max(0.0, min(1.0, float(x)))


def _seconds(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return series.astype("int64") / 1e9
    return pd.to_numeric(series, errors="coerce") / 1e9


def _load_parquet(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "time" in df.columns:
        df = df.copy()
        df["_time_s"] = _seconds(df["time"])
    return df


def _trace_dependency_edges(normal_traces: pd.DataFrame) -> list[CausalEdge]:
    """Backward-compatible Stage-2 projection from recovered CALLS relations."""
    recovery = recover_structural_relations(normal_traces)
    return propagation_service_edges(recovery.relations)


def _trace_error_mask(df: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    if "attr.status_code" in df.columns:
        status = df["attr.status_code"].fillna("").astype(str).str.lower()
        mask |= status.str.contains("error|fail")
    if "attr.http.response.status_code" in df.columns:
        code = pd.to_numeric(df["attr.http.response.status_code"], errors="coerce")
        mask |= code >= 500
    return mask


def _service_stats(traces: pd.DataFrame, logs: pd.DataFrame) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if "service_name" in traces.columns:
        for service, group in traces.dropna(subset=["service_name"]).groupby("service_name"):
            service = str(service)
            durations = pd.to_numeric(
                group.get("duration", pd.Series(dtype=float)), errors="coerce"
            ).dropna()
            err = _trace_error_mask(group)
            out.setdefault(service, {})["trace_count"] = int(len(group))
            out[service]["error_rate"] = float(err.mean()) if len(group) else 0.0
            out[service]["p95"] = float(durations.quantile(0.95)) if len(durations) else 0.0
            out[service]["p99"] = float(durations.quantile(0.99)) if len(durations) else 0.0
    if "service_name" in logs.columns:
        for service, group in logs.dropna(subset=["service_name"]).groupby("service_name"):
            service = str(service)
            level = (
                group.get("level", pd.Series("", index=group.index))
                .fillna("")
                .astype(str)
                .str.upper()
            )
            out.setdefault(service, {})["log_error_rate"] = (
                float(level.isin(["ERROR", "FATAL", "CRITICAL"]).mean()) if len(group) else 0.0
            )
    return out


def _metric_shift(
    normal: pd.DataFrame,
    abnormal: pd.DataFrame,
    service: str,
) -> tuple[float, str, float | None]:
    required = {"service_name", "metric", "value"}
    if not required.issubset(normal.columns) or not required.issubset(abnormal.columns):
        return 0.0, "", None
    nsvc = normal[normal["service_name"].astype(str) == service]
    asvc = abnormal[abnormal["service_name"].astype(str) == service]
    if nsvc.empty or asvc.empty:
        return 0.0, "", None
    best = (0.0, "", None)
    common = sorted(
        set(nsvc["metric"].dropna().astype(str))
        & set(asvc["metric"].dropna().astype(str))
    )
    for metric in common:
        low = metric.lower()
        if low.endswith(".time") or low.endswith("_time"):
            continue
        nv = pd.to_numeric(
            nsvc.loc[nsvc["metric"].astype(str) == metric, "value"], errors="coerce"
        ).dropna()
        av = pd.to_numeric(
            asvc.loc[asvc["metric"].astype(str) == metric, "value"], errors="coerce"
        ).dropna()
        if len(nv) < 3 or len(av) < 2:
            continue
        center = float(nv.median())
        mad = float((nv - center).abs().median())
        scale = max(1.4826 * mad, abs(center) * 0.05, 1e-9)
        shift = abs(float(av.median()) - center) / scale
        score = _clip01(shift / 6.0)
        if score > best[0]:
            onset = None
            if "_time_s" in asvc.columns:
                vals = pd.to_numeric(
                    asvc.loc[asvc["metric"].astype(str) == metric, "value"],
                    errors="coerce",
                )
                times = asvc.loc[asvc["metric"].astype(str) == metric, "_time_s"]
                z = (vals - center).abs() / scale
                hit = times[z >= 3.0]
                if len(hit):
                    onset = float(hit.min())
            best = (score, metric, onset)
    return best


def _evidence_for_case(
    normal_traces: pd.DataFrame,
    abnormal_traces: pd.DataFrame,
    normal_metrics: pd.DataFrame,
    abnormal_metrics: pd.DataFrame,
    normal_logs: pd.DataFrame,
    abnormal_logs: pd.DataFrame,
    abnormal_start: float,
) -> list[Evidence]:
    ns = _service_stats(normal_traces, normal_logs)
    ac = _service_stats(abnormal_traces, abnormal_logs)
    services = sorted(
        set(ns)
        | set(ac)
        | set(normal_metrics.get("service_name", pd.Series(dtype=str)).dropna().astype(str))
        | set(abnormal_metrics.get("service_name", pd.Series(dtype=str)).dropna().astype(str))
    )
    evidence: list[Evidence] = []
    eid = 0

    for service in services:
        n = ns.get(service, {})
        a = ac.get(service, {})
        ncount = float(n.get("trace_count", 0))
        acount = float(a.get("trace_count", 0))
        if ncount > 0:
            drop = _clip01((ncount - acount) / ncount)
            if drop >= 0.10:
                eid += 1
                evidence.append(
                    Evidence(
                        f"e{eid}", service, "trace", "availability_drop", drop,
                        abnormal_start,
                        f"{service} trace volume dropped {drop * 100:.1f}% versus the normal window.",
                    )
                )

        nerr, aerr = float(n.get("error_rate", 0.0)), float(a.get("error_rate", 0.0))
        err_score = _clip01(max(0.0, aerr - nerr) * 3.0)
        if err_score >= 0.10:
            onset = abnormal_start
            if "service_name" in abnormal_traces.columns and "_time_s" in abnormal_traces.columns:
                grp = abnormal_traces[abnormal_traces["service_name"].astype(str) == service]
                hit = grp.loc[_trace_error_mask(grp), "_time_s"]
                if len(hit):
                    onset = float(hit.min())
            eid += 1
            evidence.append(
                Evidence(
                    f"e{eid}", service, "trace", "error_rate", err_score, onset,
                    f"{service} trace error rate changed from {nerr:.3f} to {aerr:.3f}.",
                )
            )

        np95, ap95 = float(n.get("p95", 0.0)), float(a.get("p95", 0.0))
        if np95 > 0 and ap95 > np95:
            ratio = ap95 / np95
            lat_score = _clip01(math.log2(max(ratio, 1.0)) / 3.0)
            if lat_score >= 0.10:
                onset = abnormal_start
                if (
                    "service_name" in abnormal_traces.columns
                    and "_time_s" in abnormal_traces.columns
                    and "duration" in abnormal_traces.columns
                ):
                    grp = abnormal_traces[abnormal_traces["service_name"].astype(str) == service]
                    d = pd.to_numeric(grp["duration"], errors="coerce")
                    hit = grp.loc[
                        d > max(float(n.get("p99", np95)) * 1.25, np95 * 1.5),
                        "_time_s",
                    ]
                    if len(hit):
                        onset = float(hit.min())
                eid += 1
                evidence.append(
                    Evidence(
                        f"e{eid}", service, "trace", "latency", lat_score, onset,
                        f"{service} p95 span duration increased {ratio:.2f}x versus normal.",
                    )
                )

        nlog, alog = float(n.get("log_error_rate", 0.0)), float(a.get("log_error_rate", 0.0))
        log_score = _clip01(max(0.0, alog - nlog) * 3.0)
        if log_score >= 0.10:
            onset = abnormal_start
            if (
                "service_name" in abnormal_logs.columns
                and "_time_s" in abnormal_logs.columns
                and "level" in abnormal_logs.columns
            ):
                grp = abnormal_logs[abnormal_logs["service_name"].astype(str) == service]
                level = grp["level"].fillna("").astype(str).str.upper()
                hit = grp.loc[level.isin(["ERROR", "FATAL", "CRITICAL"]), "_time_s"]
                if len(hit):
                    onset = float(hit.min())
            eid += 1
            evidence.append(
                Evidence(
                    f"e{eid}", service, "log", "error_log_rate", log_score, onset,
                    f"{service} error-log rate changed from {nlog:.3f} to {alog:.3f}.",
                )
            )

        metric_score, metric_name, onset = _metric_shift(normal_metrics, abnormal_metrics, service)
        if metric_score >= 0.15:
            eid += 1
            evidence.append(
                Evidence(
                    f"e{eid}", service, "metric", metric_name, metric_score,
                    onset or abnormal_start,
                    f"{service} metric {metric_name} shifted materially from its normal-window distribution.",
                )
            )

    by_node = {e.node for e in evidence}
    all_services = sorted(
        set(normal_traces.get("service_name", pd.Series(dtype=str)).dropna().astype(str))
    )
    for service in all_services:
        if service not in by_node:
            eid += 1
            evidence.append(
                Evidence(
                    f"e{eid}", service, "trace", "stable_presence", 0.05,
                    abnormal_start,
                    f"{service} remained observable without a strong detected anomaly.",
                )
            )
    return evidence


def _symptoms(known_edges: list[CausalEdge], evidence: list[Evidence]) -> list[str]:
    anomaly: dict[str, float] = {}
    for item in evidence:
        anomaly[item.node] = max(anomaly.get(item.node, 0.0), item.abnormality)
    sources = {edge.source for edge in known_edges}
    targets = {edge.target for edge in known_edges}
    sinks = sorted(targets - sources)
    ranked_sinks = sorted(sinks, key=lambda x: (-anomaly.get(x, 0.0), x))
    selected = [x for x in ranked_sinks if anomaly.get(x, 0.0) >= 0.5][:2]
    if selected:
        return selected
    ranked = sorted(anomaly, key=lambda x: (-anomaly[x], x))
    return ranked[:1]


def _gold_from_causal_graph(graph: dict) -> tuple[list[str], list[CausalEdge], list[str]]:
    mapping = {str(k): str(v) for k, v in graph.get("component_to_service", {}).items()}

    def service(item) -> str | None:
        component = item.get("component") if isinstance(item, dict) else str(item)
        if component in mapping:
            return mapping[component]
        text = str(component)
        if text.startswith("service|"):
            return text.split("|", 1)[1]
        if text.startswith("span|"):
            return text.split("|", 1)[1].split("::", 1)[0]
        return None

    roots = sorted({x for x in (service(v) for v in graph.get("root_causes", [])) if x})
    alarms_src = graph.get("path_terminal_alarm_nodes") or graph.get("alarm_nodes", [])
    alarms = sorted({x for x in (service(v) for v in alarms_src) if x})
    pairs = set()
    for edge in graph.get("edges", []):
        source = service({"component": edge.get("source")})
        target = service({"component": edge.get("target")})
        if source and target and source != target:
            pairs.add((source, target))
    edges = [CausalEdge(source, "causal_propagates_to", target) for source, target in sorted(pairs)]
    return roots, edges, alarms


def _case(
    name: str,
    cache: Path,
    require_attributed: bool = True,
    system: str | None = None,
) -> RcaCase | None:
    folder = cache / name
    files = [
        "label.txt", "causal_graph.json", "env.json",
        "normal_traces.parquet", "abnormal_traces.parquet",
        "normal_metrics.parquet", "abnormal_metrics.parquet",
        "normal_logs.parquet", "abnormal_logs.parquet",
    ]
    for filename in files:
        _download(f"{BASE}/cases/{name}/{filename}?download=true", folder / filename)
    if require_attributed and (folder / "label.txt").read_text(encoding="utf-8").strip().lower() != "attributed":
        return None

    graph = _json(folder / "causal_graph.json")
    env = _json(folder / "env.json")
    normal_traces = _load_parquet(folder / "normal_traces.parquet")
    abnormal_traces = _load_parquet(folder / "abnormal_traces.parquet")
    normal_metrics = _load_parquet(folder / "normal_metrics.parquet")
    abnormal_metrics = _load_parquet(folder / "abnormal_metrics.parquet")
    normal_logs = _load_parquet(folder / "normal_logs.parquet")
    abnormal_logs = _load_parquet(folder / "abnormal_logs.parquet")

    # Stage 1: model-visible telemetry -> observations -> abductive structural
    # hypotheses -> recovered relations. DeBERTa/PSL are plugged in by the
    # dedicated Stage-S experiment driver; normalization keeps a lightweight,
    # leakage-safe abductive baseline so existing Stage-2 runs stay reproducible.
    structural_recovery = recover_structural_relations(
        normal_traces, normal_metrics, normal_logs, system=system
    )
    structural_relations = structural_recovery.relations
    relation_observations = structural_recovery.observations

    # Stage 2 currently evaluates service-level propagation. CALLS is reversed
    # from caller->callee into callee->caller propagation candidate direction.
    known_edges = propagation_service_edges(structural_relations)

    abnormal_start = float(env.get("ABNORMAL_START", 0.0))
    evidence = _evidence_for_case(
        normal_traces, abnormal_traces, normal_metrics, abnormal_metrics,
        normal_logs, abnormal_logs, abnormal_start,
    )
    symptoms = _symptoms(known_edges, evidence)
    gold_roots, gold_edges, gold_alarms = _gold_from_causal_graph(graph)

    if not gold_roots or not gold_edges:
        return None
    if require_attributed and (not known_edges or not evidence):
        return None

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
            "adapter": "telemetry_structural_v4",
            "gold_usage": "evaluation_only",
            "label_filter": "attributed_only" if require_attributed else "none",
            "structural_relation_source": "normal_telemetry_observation_abduction",
            "structural_observation_counts": observation_type_counts(relation_observations),
            "structural_candidate_count": len(structural_recovery.hypotheses),
            "structural_relation_counts": relation_type_counts(structural_relations),
            "structural_normalization_policy": "observation_then_abduction_no_gold",
        },
        structural_relations=structural_relations,
        relation_observations=relation_observations,
    )


def build(
    out: Path,
    cache: Path,
    limit: int,
    require_attributed: bool = True,
) -> list[RcaCase]:
    manifest = cache / "manifest.jsonl"
    _download(f"{BASE}/manifest.jsonl?download=true", manifest)
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases: list[RcaCase] = []
    for row in rows:
        try:
            case = _case(str(row["name"]), cache, require_attributed=require_attributed)
        except Exception as exc:
            print(f"SKIP {row.get('name')}: {type(exc).__name__}: {exc}")
            continue
        if case is not None:
            case.metadata.update(
                {
                    "system": row.get("system"),
                    "manifest_primary_kind": row.get("primary_kind"),
                    "manifest_subtypes": row.get("subtypes", []),
                    "manifest_hybrid": bool(row.get("hybrid", False)),
                }
            )
            cases.append(case)
            print(
                "CASE", case.case_id,
                "known", len(case.known_edges),
                "observations", len(case.relation_observations),
                "structural", len(case.structural_relations),
                "structural_types", relation_type_counts(case.structural_relations),
                "evidence", len(case.evidence),
                "symptoms", case.symptom_nodes,
                "gold_roots", case.gold_root_causes,
                "gold_edges", len(case.gold_edges),
            )
        if limit and len(cases) >= limit:
            break
    dump_normalized_cases(cases, out)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/ops_lite_20.jsonl")
    parser.add_argument("--cache", default=".cache/ops-lite")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--all-labels",
        action="store_true",
        help="standard OpenRCA2 track: do not filter label.txt",
    )
    args = parser.parse_args()
    cases = build(
        Path(args.out), Path(args.cache), args.limit,
        require_attributed=not args.all_labels,
    )
    print(json.dumps({"n": len(cases), "out": args.out, "all_labels": args.all_labels}, indent=2))


if __name__ == "__main__":
    main()
