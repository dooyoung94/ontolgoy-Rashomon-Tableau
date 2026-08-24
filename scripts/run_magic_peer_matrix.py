from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import yaml

from evaluate_magic_natural_language import build_rashomon_judgment
from rashomon_tableau.deberta_world_scorer import DebertaWorldScorer
from rashomon_tableau.openai_frontend import (
    compute_matched_analysis,
    compute_matched_finalize,
    direct_magic_judgment,
    extract_claims,
    numbered_context,
)
from rashomon_tableau.peer_llm import client_from_environment

MAGIC_BASE = "https://raw.githubusercontent.com/HYU-NLP/MAGIC/main/dataset/multi-hop"
FILES = [
    "1-multi-hop_conflict.json",
    "2-multi-hop_conflict.json",
    "3-multi-hop_conflict.json",
    "4-multi-hop_conflict.json",
]
FIXED_PROTOCOL_VERSION = "fixed-v2"
LOGICAL_CALLS_PER_ATTEMPT = 5


def download_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def usage_total(response) -> int:
    usage = response.usage
    return int(
        getattr(usage, "total_tokens", 0)
        or (getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0))
    )


def aggregate_attempts(attempts: list[dict]) -> dict:
    positive = [x for x in attempts if x.get("conflict_detected")]
    best = max(positive or attempts, key=lambda x: float(x.get("confidence", 0.0)), default={})
    return {
        "conflict_detected": bool(positive),
        "locations": best.get("locations", []),
        "confidence": float(best.get("confidence", 0.0)),
        "attempts": attempts,
    }


def _prediction_view(value: dict) -> dict:
    return {
        "conflict_detected": bool(value.get("conflict_detected")),
        "locations": value.get("locations", []),
        "confidence": float(value.get("confidence", 0.0)),
    }


def _request_log(client) -> list[dict]:
    value = getattr(client, "request_log", None)
    return value if isinstance(value, list) else []


def run_one_macro_attempt(client, context1: str, context2: str, max_hops: int, deberta) -> dict:
    """Run five logical provider calls; transport retries reuse the exact payload."""
    request_start = len(_request_log(client))

    direct = direct_magic_judgment(client, context1, context2)
    compute_analysis = compute_matched_analysis(client, context1, context2)
    compute_final = compute_matched_finalize(client, context1, context2, compute_analysis.data)
    extracted = extract_claims(client, context1, context2)
    candidate_llm = build_rashomon_judgment(
        client,
        context1,
        context2,
        max_hops,
        world_scorer=None,
        extracted_response=extracted,
    )
    candidate_deberta = None
    if deberta is not None:
        candidate_deberta = build_rashomon_judgment(
            client,
            context1,
            context2,
            max_hops,
            world_scorer=deberta,
            extracted_response=extracted,
        )

    shared_extraction_tokens = usage_total(extracted)
    batch_tokens = int(candidate_llm["usage"]["input_tokens"]) + int(candidate_llm["usage"]["output_tokens"])
    actual_requests = _request_log(client)[request_start:]

    return {
        "predictions": {
            "direct": _prediction_view(direct.data),
            "compute_matched_direct": _prediction_view(compute_final.data),
            "rashomon_worlds_llm_scorer": _prediction_view(candidate_llm),
            **(
                {"rashomon_worlds_deberta_scorer": _prediction_view(candidate_deberta)}
                if candidate_deberta is not None else {}
            ),
        },
        "diagnostics": {
            "compute_first_pass": compute_analysis.data,
            "rashomon_llm": {
                "candidate_queries": candidate_llm["candidate_queries"],
                "evaluated_query_paths": candidate_llm["evaluated_query_paths"],
                "world_scorer": candidate_llm["world_scorer"],
                "decision_rule": candidate_llm.get("decision_rule"),
                "best_contradiction_path": candidate_llm.get("best_contradiction_path"),
                "candidates": candidate_llm.get("candidates", []),
            },
            **(
                {
                    "rashomon_deberta": {
                        "candidate_queries": candidate_deberta["candidate_queries"],
                        "evaluated_query_paths": candidate_deberta["evaluated_query_paths"],
                        "world_scorer": candidate_deberta["world_scorer"],
                        "decision_rule": candidate_deberta.get("decision_rule"),
                        "best_contradiction_path": candidate_deberta.get("best_contradiction_path"),
                        "candidates": candidate_deberta.get("candidates", []),
                    }
                }
                if candidate_deberta is not None else {}
            ),
            "actual_requests": actual_requests,
        },
        "physical_cost": {
            "provider_calls": len(actual_requests) if actual_requests else LOGICAL_CALLS_PER_ATTEMPT,
            "provider_tokens": (
                usage_total(direct)
                + usage_total(compute_analysis)
                + usage_total(compute_final)
                + shared_extraction_tokens
                + batch_tokens
            ),
            "logical_provider_calls": LOGICAL_CALLS_PER_ATTEMPT,
        },
        "condition_cost": {
            "direct": {"logical_llm_calls": 1, "llm_tokens": usage_total(direct)},
            "compute_matched_direct": {
                "logical_llm_calls": 2,
                "llm_tokens": usage_total(compute_analysis) + usage_total(compute_final),
                "fixed_two_stage": True,
            },
            "rashomon_worlds_llm_scorer": {
                "logical_llm_calls": 2,
                "llm_tokens": shared_extraction_tokens + batch_tokens,
                "shared_extraction_physically_reused": True,
                "batch_world_scoring": True,
            },
            **(
                {
                    "rashomon_worlds_deberta_scorer": {
                        "logical_llm_calls": 1,
                        "llm_tokens": shared_extraction_tokens,
                        "shared_extraction_physically_reused": True,
                        "deberta_scoring": True,
                    }
                }
                if candidate_deberta is not None else {}
            ),
        },
    }


def run_model(model_key: str, cfg: dict, args, deberta: DebertaWorldScorer | None) -> dict:
    model_cfg = dict(cfg["models"][model_key])
    if args.no_retries:
        # Preserve the fixed logical-call protocol: no contract/regeneration retry.
        # A model may explicitly allow same-payload transport retries for 5xx/504.
        model_cfg["max_retries"] = int(model_cfg.get("fixed_transport_retries", 0))
        model_cfg["contract_retries"] = 0
    client = client_from_environment(model_cfg)

    cache_path = Path(args.cache_dir) / f"{model_key}.jsonl"
    failure_path = Path(args.cache_dir) / f"{model_key}.failures.jsonl"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cached = json.loads(line)
                existing[cached["key"]] = cached

    records: list[dict] = []
    row_failures: list[dict] = []
    processed = 0
    failed_physical_calls = 0
    for filename in FILES:
        rows = download_json(f"{MAGIC_BASE}/{filename}")
        for row in rows:
            if args.limit and processed >= args.limit:
                break
            key = (
                f"{filename}:{row.get('id')}:{model_key}:{FIXED_PROTOCOL_VERSION}:"
                f"a{args.attempts}:h{args.max_hops}:contractretry{0 if args.no_retries else 1}"
            )
            if key in existing:
                records.append(existing[key])
                processed += 1
                continue

            context1, context2 = row["context1"], row["context2"]
            row_request_start = len(_request_log(client))
            try:
                macro_attempts = [
                    run_one_macro_attempt(client, context1, context2, args.max_hops, deberta)
                    for _ in range(args.attempts)
                ]
            except Exception as exc:
                actual_requests = _request_log(client)[row_request_start:]
                failed_physical_calls += len(actual_requests)
                failure = {
                    "key": key,
                    "file": filename,
                    "id": row.get("id"),
                    "model_key": model_key,
                    "error": str(exc),
                    "actual_requests": actual_requests,
                }
                with failure_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
                row_failures.append(failure)
                processed += 1
                continue

            condition_names = list(macro_attempts[0]["predictions"])
            conditions = {
                condition: aggregate_attempts([attempt["predictions"][condition] for attempt in macro_attempts])
                for condition in condition_names
            }

            condition_cost = {}
            for condition in condition_names:
                entries = [attempt["condition_cost"][condition] for attempt in macro_attempts]
                condition_cost[condition] = {
                    "logical_llm_calls": sum(int(x["logical_llm_calls"]) for x in entries),
                    "llm_tokens": sum(int(x["llm_tokens"]) for x in entries),
                }
                for field in (
                    "fixed_two_stage", "shared_extraction_physically_reused",
                    "batch_world_scoring", "deberta_scoring",
                ):
                    if any(bool(x.get(field)) for x in entries):
                        condition_cost[condition][field] = True

            physical_calls = sum(int(x["physical_cost"]["provider_calls"]) for x in macro_attempts)
            physical_tokens = sum(int(x["physical_cost"]["provider_tokens"]) for x in macro_attempts)
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
                "conditions": conditions,
                "cost": condition_cost,
                "physical_provider_cost": {
                    "calls": physical_calls,
                    "tokens": physical_tokens,
                    "logical_calls": args.attempts * LOGICAL_CALLS_PER_ATTEMPT,
                    "same_payload_transport_retries_allowed": int(model_cfg.get("max_retries", 0)),
                    "contract_retries_disabled": bool(args.no_retries),
                },
                "macro_diagnostics": [attempt["diagnostics"] for attempt in macro_attempts],
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

    def id_rate(condition: str) -> float | None:
        available = [r for r in records if condition in r["conditions"]]
        if not available:
            return None
        return sum(bool(r["conditions"][condition]["conflict_detected"]) for r in available) / len(available)

    direct_id = id_rate("direct")
    matched_id = id_rate("compute_matched_direct")
    llm_id = id_rate("rashomon_worlds_llm_scorer")
    deberta_id = id_rate("rashomon_worlds_deberta_scorer")
    successful_physical_calls = sum(int(r["physical_provider_cost"]["calls"]) for r in records)
    total_physical_tokens = sum(int(r["physical_provider_cost"]["tokens"]) for r in records)

    return {
        "model_key": model_key,
        "display_name": model_cfg["display_name"],
        "target_rows": processed,
        "n": len(records),
        "failed_rows": len(row_failures),
        "direct_id_recall": direct_id,
        "compute_matched_id_recall": matched_id,
        "rashomon_llm_id_recall": llm_id,
        "rashomon_deberta_id_recall": deberta_id,
        "delta_llm_vs_direct_pp": 100 * (llm_id - direct_id) if llm_id is not None and direct_id is not None else None,
        "delta_llm_vs_compute_matched_pp": 100 * (llm_id - matched_id) if llm_id is not None and matched_id is not None else None,
        "delta_deberta_vs_direct_pp": 100 * (deberta_id - direct_id) if deberta_id is not None and direct_id is not None else None,
        "delta_deberta_vs_llm_pp": 100 * (deberta_id - llm_id) if deberta_id is not None and llm_id is not None else None,
        "physical_provider_calls": successful_physical_calls + failed_physical_calls,
        "physical_provider_tokens": total_physical_tokens,
        "expected_logical_calls_if_complete": processed * args.attempts * LOGICAL_CALLS_PER_ATTEMPT,
        "transport_retry_count": max(0, successful_physical_calls + failed_physical_calls - len(records) * args.attempts * LOGICAL_CALLS_PER_ATTEMPT),
        "loc_status": "pending blinded human scoring, matching MAGIC's manual LOC protocol",
        "cache": str(cache_path),
        "failure_log": str(failure_path) if row_failures else None,
    }


def export_blinded_loc(cache_dir: Path, out: Path) -> None:
    rows = []
    for cache in sorted(cache_dir.glob("*.jsonl")):
        if cache.name.endswith(".failures.jsonl"):
            continue
        for line in cache.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if f":{FIXED_PROTOCOL_VERSION}:" not in record.get("key", ""):
                continue
            for condition, prediction in record["conditions"].items():
                rows.append({
                    "blind_id": f"B{len(rows)+1:07d}",
                    "model_key": record["model_key"],
                    "condition": condition,
                    "contexts": record["contexts"],
                    "predicted_conflict": prediction["conflict_detected"],
                    "predicted_locations": prediction["locations"],
                })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/magic_peer_model_matrix.yaml")
    ap.add_argument("--model-set", default="current_available")
    ap.add_argument("--models", nargs="*", default=[])
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--max-hops", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--without-deberta", action="store_true")
    ap.add_argument("--no-retries", action="store_true", help="Disable contract retries; configured same-payload transport retries may remain enabled.")
    ap.add_argument("--cache-dir", default="results/magic_peer_matrix")
    ap.add_argument("--out", default="results/magic_peer_matrix_summary.json")
    ap.add_argument("--loc-export", default="results/magic_peer_loc_blinded.json")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    selected = args.models or cfg.get("model_sets", {}).get(args.model_set, list(cfg["models"]))
    deberta = None if args.without_deberta else DebertaWorldScorer(cfg["discriminative_scorer"]["model"])

    summaries = []
    failures = []
    for key in selected:
        try:
            summaries.append(run_model(key, cfg, args, deberta))
        except Exception as exc:
            failures.append({"model_key": key, "error": str(exc)})

    logical_cap = args.limit * len(selected) * args.attempts * LOGICAL_CALLS_PER_ATTEMPT if args.limit else None
    result = {
        "benchmark": "MAGIC multi-hop natural-language paired method study",
        "protocol_version": FIXED_PROTOCOL_VERSION,
        "model_set": args.model_set,
        "attempts_per_example": args.attempts,
        "limit": args.limit,
        "models": summaries,
        "failures": failures,
        "fixed_call_policy": {
            "direct_calls_per_attempt": 1,
            "compute_matched_calls_per_attempt": 2,
            "shared_claim_extraction_calls_per_attempt": 1,
            "llm_batch_score_calls_per_attempt": 1,
            "deberta_provider_score_calls_per_attempt": 0,
            "logical_provider_calls_per_attempt": LOGICAL_CALLS_PER_ATTEMPT,
            "logical_provider_call_cap": logical_cap,
            "contract_retries_disabled": bool(args.no_retries),
            "transport_retry_policy": "Only explicitly configured transient transport retries resend the exact same payload; they do not add logical model calls.",
        },
        "primary_comparison": "same-model candidate-path LLM scorer vs same-model fixed two-stage compute-matched direct baseline",
        "candidate_space_control": "LLM and DeBERTa scoring conditions share the exact same claim extraction and candidate paths per macro attempt.",
        "decision_rule": "existential_dominant_path_contradiction",
        "world_marginal_role": "diagnostic/ablation only; it does not control the MAGIC binary conflict decision",
        "loc_protocol": "blind human exact-localization scoring; automatic LOC is intentionally not used",
        "metric_warning": "Released MAGIC multi-hop files used here contain conflict cases, so automated ID is conflict recall rather than official full-dataset ID accuracy.",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    export_blinded_loc(Path(args.cache_dir), Path(args.loc_export))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
