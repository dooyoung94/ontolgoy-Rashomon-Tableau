from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import yaml

from rashomon_tableau.openai_frontend import (
    direct_magic_judgment,
    extract_claims,
    score_world_bidirectionally,
)
from rashomon_tableau.peer_llm import client_from_environment

MAGIC_SAMPLE = (
    "https://raw.githubusercontent.com/HYU-NLP/MAGIC/main/dataset/multi-hop/"
    "1-multi-hop_conflict.json"
)


def download_first_row() -> dict:
    with urllib.request.urlopen(MAGIC_SAMPLE, timeout=60) as response:
        rows = json.load(response)
    if not rows:
        raise RuntimeError("MAGIC sample file was empty")
    return rows[0]


def usage_dict(response) -> dict:
    usage = response.usage
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def run_call(name: str, fn, token_budget: int | None) -> dict:
    try:
        response = fn()
        return {
            "name": name,
            "ok": True,
            "token_budget": token_budget,
            "model": response.model,
            "keys": sorted(response.data.keys()),
            "usage": usage_dict(response),
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "token_budget": token_budget,
            "error": str(exc),
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/magic_peer_model_matrix.yaml")
    ap.add_argument("--model-set", default="hf_open_llms")
    ap.add_argument("--out", default="results/hf_contract_smoke.json")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    selected = cfg["model_sets"][args.model_set]
    row = download_first_row()
    results = []

    schema_names = {
        "direct": "magic_direct_judgment",
        "claim_extraction": "magic_claim_extraction",
        "world_score": "rashomon_world_score",
    }

    for model_key in selected:
        # Hard safety rule: no client retries. The three calls below therefore mean
        # at most three HF provider requests per model. Task-specific token budgets
        # affect response length/cost but never increase request count.
        model_cfg = dict(cfg["models"][model_key])
        model_cfg["max_retries"] = 0
        model_cfg["contract_retries"] = 0
        model_cfg["timeout_seconds"] = min(int(model_cfg.get("timeout_seconds", 180)), 120)
        client = client_from_environment(model_cfg)
        budgets = model_cfg.get("schema_max_tokens") or {}

        calls = [
            run_call(
                "direct",
                lambda: direct_magic_judgment(client, row["context1"], row["context2"]),
                budgets.get(schema_names["direct"], model_cfg.get("max_tokens")),
            ),
            run_call(
                "claim_extraction",
                lambda: extract_claims(client, row["context1"], row["context2"]),
                budgets.get(schema_names["claim_extraction"], model_cfg.get("max_tokens")),
            ),
            run_call(
                "world_score",
                lambda: score_world_bidirectionally(
                    client,
                    query="entity_a --related_to--> entity_b [source=context1, sentence=0]",
                    world_evidence=[
                        "entity_a --related_to--> entity_b [source=context2, sentence=0]"
                    ],
                ),
                budgets.get(schema_names["world_score"], model_cfg.get("max_tokens")),
            ),
        ]
        results.append(
            {
                "model_key": model_key,
                "display_name": model_cfg["display_name"],
                "requested_model": model_cfg["exact_model"],
                "max_provider_requests": 3,
                "calls": calls,
                "all_contracts_ok": all(call["ok"] for call in calls),
                "successful_calls": sum(bool(call["ok"]) for call in calls),
            }
        )

    result = {
        "purpose": "HF provider/JSON-contract smoke test only; not a MAGIC benchmark score",
        "models": results,
        "hard_provider_request_cap": 3 * len(results),
        "retries_enabled": False,
        "full_rashomon_pipeline_executed": False,
        "compute_matched_executed": False,
        "task_budgets": {
            "direct": "1024 tokens configured",
            "claim_extraction": "4096 tokens configured",
            "world_score": "768 tokens configured",
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not any(model["all_contracts_ok"] for model in results):
        raise SystemExit("No HF model passed all three bounded contract checks")


if __name__ == "__main__":
    main()
