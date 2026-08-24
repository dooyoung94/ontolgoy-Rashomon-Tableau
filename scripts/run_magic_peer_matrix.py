from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

import yaml

from evaluate_magic_natural_language import build_rashomon_judgment
from rashomon_tableau.openai_frontend import direct_magic_judgment, numbered_context
from rashomon_tableau.peer_llm import client_from_environment

MAGIC_BASE = "https://raw.githubusercontent.com/HYU-NLP/MAGIC/main/dataset/multi-hop"
FILES = [
    "1-multi-hop_conflict.json",
    "2-multi-hop_conflict.json",
    "3-multi-hop_conflict.json",
    "4-multi-hop_conflict.json",
]


def download_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def usage_total(response) -> int:
    usage = response.usage
    return int(getattr(usage, "total_tokens", 0) or (getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)))


def aggregate_attempts(attempts: list[dict]) -> dict:
    positive = [x for x in attempts if x.get("conflict_detected")]
    best = max(positive or attempts, key=lambda x: float(x.get("confidence", 0.0)), default={})
    return {
        "conflict_detected": bool(positive),  # MAGIC ID: any successful attempt counts.
        "locations": best.get("locations", []),
        "confidence": float(best.get("confidence", 0.0)),
        "attempts": attempts,
    }


def run_direct_attempts(client, context1: str, context2: str, attempts: int) -> tuple[dict, int, int]:
    outputs = []
    calls = 0
    tokens = 0
    for _ in range(attempts):
        response = direct_magic_judgment(client, context1, context2)
        outputs.append(response.data)
        calls += 1
        tokens += usage_total(response)
    return aggregate_attempts(outputs), calls, tokens


def run_compute_matched_direct(client, context1: str, context2: str, target_calls: int, target_tokens: int, max_calls: int) -> tuple[dict, int, int]:
    """Spend at least the Rashomon call budget and, where possible, its token budget.

    The condition deliberately performs only direct conflict judgments; it never
    constructs claims, graph paths, or possible worlds. This isolates extra inference
    compute from the Rashomon representation itself.
    """
    outputs = []
    calls = 0
    tokens = 0
    minimum_calls = max(1, target_calls)
    while calls < max_calls and (calls < minimum_calls or tokens < target_tokens):
        response = direct_magic_judgment(client, context1, context2)
        outputs.append(response.data)
        calls += 1
        tokens += usage_total(response)
    aggregated = aggregate_attempts(outputs)
    aggregated["budget_target_calls"] = target_calls
    aggregated["budget_target_tokens"] = target_tokens
    aggregated["budget_reached"] = calls >= target_calls and tokens >= target_tokens
    return aggregated, calls, tokens


def run_model(model_key: str, cfg: dict, args) -> dict:
    model_cfg = cfg["models"][model_key]
    client = client_from_environment(model_cfg)
    cache_path = Path(args.cache_dir) / f"{model_key}.jsonl"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                existing[row["key"]] = row

    records = []
    processed = 0
    for filename in FILES:
        rows = download_json(f"{MAGIC_BASE}/{filename}")
        for row in rows:
            if args.limit and processed >= args.limit:
                break
            key = f"{filename}:{row.get('id')}:{model_key}"
            if key in existing:
                records.append(existing[key])
                processed += 1
                continue

            context1, context2 = row["context1"], row["context2"]
            direct, direct_calls, direct_tokens = run_direct_attempts(client, context1, context2, args.attempts)

            rashomon_attempts = []
            rashomon_calls = 0
            rashomon_tokens = 0
            for _ in range(args.attempts):
                r = build_rashomon_judgment(client, context1, context2, args.max_hops)
                rashomon_attempts.append({
                    "conflict_detected": r["conflict_detected"],
                    "locations": r["locations"],
                    "confidence": r["confidence"],
                })
                rashomon_calls += int(r["usage"]["calls"])
                rashomon_tokens += int(r["usage"]["input_tokens"]) + int(r["usage"]["output_tokens"])
            rashomon = aggregate_attempts(rashomon_attempts)

            matched, matched_calls, matched_tokens = run_compute_matched_direct(
                client,
                context1,
                context2,
                target_calls=rashomon_calls,
                target_tokens=rashomon_tokens,
                max_calls=args.max_matched_calls,
            )

            record = {
                "key": key,
                "file": filename,
                "id": row.get("id"),
                "model_key": model_key,
                "model_requested": model_cfg["exact_model"],
                "contexts": {
                    "context1": numbered_context(context1),
                    "context2": numbered_context(context2),
                },
                "conditions": {
                    "direct": direct,
                    "compute_matched_direct": matched,
                    "rashomon_worlds": rashomon,
                },
                "cost": {
                    "direct": {"calls": direct_calls, "tokens": direct_tokens},
                    "compute_matched_direct": {"calls": matched_calls, "tokens": matched_tokens},
                    "rashomon_worlds": {"calls": rashomon_calls, "tokens": rashomon_tokens},
                },
                # Stored only after predictions. Human LOC scorers receive blinded exports.
                "gold_audit_only": {
                    "original_triplet": row.get("original_triplet"),
                    "perturb_triplet": row.get("perturb_triplet"),
                },
            }
            with cache_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.append(record)
            processed += 1
        if args.limit and processed >= args.limit:
            break

    def id_rate(condition: str) -> float:
        return sum(bool(r["conditions"][condition]["conflict_detected"]) for r in records) / len(records) if records else 0.0

    direct_id = id_rate("direct")
    matched_id = id_rate("compute_matched_direct")
    rashomon_id = id_rate("rashomon_worlds")
    return {
        "model_key": model_key,
        "display_name": model_cfg["display_name"],
        "n": len(records),
        "direct_id_recall": direct_id,
        "compute_matched_id_recall": matched_id,
        "rashomon_id_recall": rashomon_id,
        "delta_id_vs_direct_pp": 100 * (rashomon_id - direct_id),
        "delta_id_vs_compute_matched_pp": 100 * (rashomon_id - matched_id),
        "loc_status": "pending blinded human scoring, matching MAGIC's manual LOC protocol",
        "cache": str(cache_path),
    }


def export_blinded_loc(cache_dir: Path, out: Path) -> None:
    rows = []
    for cache in sorted(cache_dir.glob("*.jsonl")):
        for line in cache.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            for condition, prediction in record["conditions"].items():
                rows.append({
                    "blind_id": f"B{len(rows)+1:07d}",
                    "model_key": record["model_key"],
                    "condition": condition,
                    "contexts": record["contexts"],
                    "predicted_conflict": prediction["conflict_detected"],
                    "predicted_locations": prediction["locations"],
                    # gold and method internals intentionally omitted.
                })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/magic_peer_model_matrix.yaml")
    ap.add_argument("--models", nargs="*", default=[])
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--max-hops", type=int, default=4)
    ap.add_argument("--max-matched-calls", type=int, default=128)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cache-dir", default="results/magic_peer_matrix")
    ap.add_argument("--out", default="results/magic_peer_matrix_summary.json")
    ap.add_argument("--loc-export", default="results/magic_peer_loc_blinded.json")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    selected = args.models or list(cfg["models"])
    summaries = []
    failures = []
    for key in selected:
        try:
            summaries.append(run_model(key, cfg, args))
        except Exception as exc:
            failures.append({"model_key": key, "error": str(exc)})

    result = {
        "benchmark": "MAGIC multi-hop natural-language paired method study",
        "attempts_per_example": args.attempts,
        "models": summaries,
        "failures": failures,
        "primary_comparison": "rashomon_worlds vs compute_matched_direct within the same model",
        "loc_protocol": "blind human exact-localization scoring; automatic LOC is intentionally not used",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    export_blinded_loc(Path(args.cache_dir), Path(args.loc_export))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
