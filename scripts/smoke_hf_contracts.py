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


def run_call(name: str, fn) -> dict:
    try:
        response = fn()
        return {
            "name": name,
            "ok": True,
            "model": response.model,
            "keys": sorted(response.data.keys()),
            "usage": usage_dict(response),
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
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

    for model_key in selected:
        # Hard safety rule for the smoke test: client-level HTTP and contract retries
        # are disabled. The three calls below therefore mean at most three HF
        # provider requests per model, regardless of success/failure.
        model_cfg = dict(cfg["models"][model_key])
        model_cfg["max_retries"] = 0
        model_cfg["contract_retries"] = 0
        model_cfg["timeout_seconds"] = min(int(model_cfg.get("timeout_seconds", 180)), 120)
        model_cfg["max_tokens"] = min(int(model_cfg.get("max_tokens", 2048)), 1536)
        client = client_from_environment(model_cfg)

        calls = [
            run_call(
                "direct",
                lambda: direct_magic_judgment(client, row["context1"], row["context2"]),
            ),
            run_call(
                "claim_extraction",
                lambda: extract_claims(client, row["context1"], row["context2"]),
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
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # A smoke run is considered useful if at least one model passes all three
    # contracts. Failures remain in the artifact for provider-specific diagnosis.
    if not any(model["all_contracts_ok"] for model in results):
        raise SystemExit("No HF model passed all three bounded contract checks")


if __name__ == "__main__":
    main()
