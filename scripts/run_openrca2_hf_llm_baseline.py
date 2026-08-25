from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from openrca_mr.masking import mask_relation_types
from openrca_mr.metrics import (
    exact_root_set,
    node_metrics,
    normalize_service,
    process_path_reachability,
    relation_classification_metrics,
    root_hit_at_k,
    service_edge_metrics,
)
from openrca_mr.models import REL_CAUSAL, REL_MASKED
from openrca_mr.openrca2 import load_normalized_cases


MODEL_SPECS = {
    "HuggingFaceTB/SmolLM2-360M-Instruct": {
        "nominal_parameters": 360_000_000,
        "published_context_window": 8192,
        "family": "SmolLM2",
    },
    "Qwen/Qwen2.5-0.5B-Instruct": {
        "nominal_parameters": 490_000_000,
        "published_context_window": 32768,
        "family": "Qwen2.5",
    },
}


def _compact_text(text: str) -> str:
    return " ".join(str(text).split())


def _prompt(case) -> tuple[str, list]:
    masked = [edge for edge in case.known_edges if edge.relation == REL_MASKED]
    visible = [edge for edge in case.known_edges if edge.relation != REL_MASKED]

    masked_lines = [f"{idx}|{edge.source}|{edge.target}" for idx, edge in enumerate(masked)]
    visible_lines = [f"{edge.source}|{edge.relation}|{edge.target}" for edge in visible]

    # Stable high-signal-first ordering makes truncation deterministic. No gold
    # information is used in ordering or prompt construction.
    evidence = sorted(
        case.evidence,
        key=lambda e: (-float(e.abnormality), e.timestamp if e.timestamp is not None else float("inf"), e.evidence_id),
    )
    evidence_lines = []
    for e in evidence:
        timestamp = "NA" if e.timestamp is None else f"{float(e.timestamp):.3f}"
        evidence_lines.append(
            f"{e.node}|{e.kind}|{e.signal}|abn={float(e.abnormality):.3f}|t={timestamp}|{_compact_text(e.text)}"
        )

    prompt = "\n".join([
        "Task: recover incident-specific causal relations in an observed microservice dependency graph.",
        "Every MASKED candidate is a real observed source-target dependency; only its relation label is hidden.",
        "For each MASKED candidate decide causal_propagates_to vs non_causal_dependency.",
        "Return causal candidate IDs only; never invent a new endpoint pair.",
        "Also rank at most three likely root-cause services using only the supplied graph and telemetry.",
        'Output JSON only: {"causal_ids":[0,2],"root_causes":["service-a"]}',
        "",
        "MASKED_CANDIDATES id|source|target:",
        *(masked_lines or ["NONE"]),
        "",
        "VISIBLE_RELATIONS source|relation|target:",
        *(visible_lines or ["NONE"]),
        "",
        "SYMPTOM_SERVICES:",
        json.dumps(case.symptom_nodes, ensure_ascii=False),
        "",
        "TELEMETRY node|kind|signal|abnormality|time|text:",
        *(evidence_lines or ["NONE"]),
    ])
    return prompt, masked


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object")
    return json.loads(cleaned[start : end + 1])


def _parse_prediction(text: str) -> tuple[list[int], list[str], str]:
    try:
        obj = _parse_json_object(text)
        ids = [int(x) for x in (obj.get("causal_ids") or []) if str(x).lstrip("-").isdigit()]
        roots = [str(x) for x in (obj.get("root_causes") or [])]
        return ids, roots, "json"
    except Exception:
        pass

    ids: list[int] = []
    roots: list[str] = []
    m = re.search(r"causal_ids\s*[:=]\s*\[([^\]]*)\]", text, flags=re.I | re.S)
    if m:
        ids = [int(x) for x in re.findall(r"-?\d+", m.group(1))]
    m = re.search(r"root_causes\s*[:=]\s*\[([^\]]*)\]", text, flags=re.I | re.S)
    if m:
        roots = re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))
    if m or ids:
        return ids, roots, "regex_fallback"
    return [], [], "failed"


def _canonical_roots(raw_roots: list[str], case) -> tuple[list[str], int]:
    nodes = {edge.source for edge in case.known_edges} | {edge.target for edge in case.known_edges}
    by_norm: dict[str, str] = {}
    for node in sorted(nodes):
        by_norm.setdefault(normalize_service(node), node)
    valid: list[str] = []
    invalid = 0
    for raw in raw_roots:
        canonical = by_norm.get(normalize_service(raw))
        if canonical is None:
            invalid += 1
            continue
        if canonical not in valid:
            valid.append(canonical)
        if len(valid) >= 3:
            break
    return valid, invalid


def _mean(rows: list[dict], key: str):
    vals = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]
    return sum(vals) / len(vals) if vals else None


def run(
    data: str,
    out: str,
    model_name: str,
    mask_ratio: float,
    seed: int,
    limit: int,
    max_input_tokens: int,
    max_new_tokens: int,
) -> None:
    if model_name not in MODEL_SPECS:
        raise ValueError(f"Unsupported benchmark model: {model_name}. Allowed: {sorted(MODEL_SPECS)}")

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Install torch and transformers for the Hugging Face LLM baseline") from exc

    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float32)
    model.to("cpu")
    model.eval()

    actual_parameters = int(sum(p.numel() for p in model.parameters()))
    config_context = int(getattr(model.config, "max_position_embeddings", MODEL_SPECS[model_name]["published_context_window"]))
    effective_input_cap = min(int(max_input_tokens), max(1, config_context - int(max_new_tokens)))
    if effective_input_cap + max_new_tokens > config_context:
        raise ValueError("input/output token caps exceed model context window")

    cases = load_normalized_cases(data)
    if limit:
        cases = cases[:limit]

    rows = []
    for case in cases:
        visible, masked_truth = mask_relation_types(case, mask_ratio, seed)
        user_prompt, masked_candidates = _prompt(visible)
        messages = [
            {"role": "system", "content": "You are a deterministic RCA evaluator. Follow the requested JSON schema exactly."},
            {"role": "user", "content": user_prompt},
        ]
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        raw_ids = tokenizer(rendered, add_special_tokens=False)["input_ids"]
        encoded = tokenizer(
            rendered,
            return_tensors="pt",
            add_special_tokens=False,
            truncation=True,
            max_length=effective_input_cap,
        )
        input_tokens = int(encoded["input_ids"].shape[-1])
        truncated = len(raw_ids) > input_tokens

        started = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                use_cache=True,
                pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        runtime = time.perf_counter() - started
        new_ids = generated[0, input_tokens:]
        output_tokens = int(new_ids.shape[-1])
        text = tokenizer.decode(new_ids, skip_special_tokens=True)
        raw_causal_ids, raw_roots, parse_mode = _parse_prediction(text)

        valid_ids = sorted({idx for idx in raw_causal_ids if 0 <= idx < len(masked_candidates)})
        invalid_ids = len(set(raw_causal_ids)) - len(valid_ids)
        predicted = [masked_candidates[idx].key() for idx in valid_ids]
        predicted.extend(edge.key() for edge in visible.known_edges if edge.relation == REL_CAUSAL)
        roots, invalid_roots = _canonical_roots(raw_roots, visible)

        relation = relation_classification_metrics(predicted, masked_truth)
        edge = service_edge_metrics(predicted, case.gold_edges)
        node = node_metrics(predicted, case.gold_edges)
        rows.append({
            "case_id": case.case_id,
            "relation_accuracy": relation.accuracy,
            "relation_precision": relation.precision,
            "relation_recall": relation.recall,
            "relation_f1": relation.f1,
            "node_f1": node.f1,
            "edge_f1": edge.f1,
            "process_path_reachability": process_path_reachability(
                predicted, roots, case.gold_root_causes, case.gold_alarm_nodes or case.symptom_nodes
            ),
            "root_exact_set": exact_root_set(roots, case.gold_root_causes),
            "root_hit_at_1": root_hit_at_k(roots, case.gold_root_causes, 1),
            "root_hit_at_3": root_hit_at_k(roots, case.gold_root_causes, 3),
            "parse_success": float(parse_mode != "failed"),
            "prompt_truncated": float(truncated),
            "raw_prompt_tokens": len(raw_ids),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_seconds": runtime,
            "n_invalid_causal_ids": invalid_ids,
            "n_invalid_roots": invalid_roots,
            "parse_mode": parse_mode,
            "raw_output": text,
        })

    metric_keys = [
        "relation_accuracy", "relation_precision", "relation_recall", "relation_f1",
        "node_f1", "edge_f1", "process_path_reachability", "root_exact_set",
        "root_hit_at_1", "root_hit_at_3", "parse_success", "prompt_truncated",
        "raw_prompt_tokens", "input_tokens", "output_tokens", "generation_seconds",
    ]
    spec = MODEL_SPECS[model_name]
    result = {
        "baseline": "hf_llm_relation_recovery",
        "model": model_name,
        "model_metadata": {
            **spec,
            "actual_parameters_loaded": actual_parameters,
            "config_context_window": config_context,
            "benchmark_max_input_tokens": effective_input_cap,
            "benchmark_max_new_tokens": max_new_tokens,
            "decoding": "greedy_do_sample_false",
            "runtime_dtype": "float32",
            "device": "cpu",
        },
        "mask_mode": "relation",
        "mask_ratio": mask_ratio,
        "seed": seed,
        "n": len(rows),
        "protocol": {
            "endpoint_policy": "LLM selects only IDs of observed masked endpoint pairs; invented endpoint pairs are impossible by construction",
            "visible_relation_policy": "same unmasked causal/non-causal relation facts as A0-A4",
            "telemetry_policy": "same adapter telemetry fields; deterministic high-abnormality-first ordering if token truncation is required",
            "root_policy": "up to 3 roots, canonicalized only to services present in the observed graph",
        },
        "summary": {key: _mean(rows, key) for key in metric_keys},
        "rows": rows,
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--model", required=True, choices=sorted(MODEL_SPECS))
    p.add_argument("--mask-ratio", type=float, required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--max-input-tokens", type=int, default=4096)
    p.add_argument("--max-new-tokens", type=int, default=128)
    args = p.parse_args()
    run(
        args.data,
        args.out,
        args.model,
        args.mask_ratio,
        args.seed,
        args.limit,
        args.max_input_tokens,
        args.max_new_tokens,
    )


if __name__ == "__main__":
    main()
