from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from openrca_mr.masking import mask_relation_types
from openrca_mr.metrics import (
    all_root_services_hit,
    any_root_service_hit,
    exact_root_set,
    is_loadgen,
    node_metrics,
    normalize_service,
    process_path_reachability,
    relation_classification_metrics,
    root_hit_at_k,
    root_set_metrics,
    service_edge_metrics,
)
from openrca_mr.models import REL_CAUSAL
from openrca_mr.openrca2 import load_normalized_cases


MODEL_SPECS = {
    "Qwen/Qwen2.5-0.5B-Instruct": {
        "nominal_parameters": 490_000_000,
        "published_context_window": 32768,
        "family": "Qwen2.5",
    },
    "HuggingFaceTB/SmolLM2-360M-Instruct": {
        "nominal_parameters": 360_000_000,
        "published_context_window": 8192,
        "family": "SmolLM2",
    },
}


def _compact(text: str) -> str:
    return " ".join(str(text).split())


def _fmt(value) -> str:
    if value is None:
        return "NA"
    try:
        return f"{float(value):.3f}"
    except Exception:
        return str(value)


def _pair(source: str, target: str) -> tuple[str, str]:
    return normalize_service(source), normalize_service(target)


def _a4_pair_map(a4_row: dict) -> dict[tuple[str, str], dict]:
    """Return only model-produced A4 signals; evaluator truth is never exposed."""
    out: dict[tuple[str, str], dict] = {}
    for item in a4_row.get("pair_diagnostics", []):
        key = (str(item.get("source_norm") or ""), str(item.get("target_norm") or ""))
        out[key] = {
            "predicted_causal": bool(item.get("predicted_causal")),
            "abductive_score": item.get("abductive_score"),
            "temporal_score": item.get("temporal_score"),
            "anomaly_score": item.get("anomaly_score"),
            "semantic_support": item.get("semantic_support"),
            "semantic_contradiction": item.get("semantic_contradiction"),
            "semantic_neutral": item.get("semantic_neutral"),
            "semantic_margin": item.get("semantic_margin"),
            "soft_logic_score": item.get("soft_logic_score"),
            "final_score": item.get("final_score"),
        }
    return out


def _prompt(case, a4_row: dict) -> tuple[str, list]:
    # The A5 LLM is an adjudicator, not a topology generator. It may revise A4's
    # causal/non-causal choice for any MASKED observed pair, but cannot invent
    # endpoint pairs. Gold labels are not referenced anywhere in this function.
    masked_candidates = [edge for edge in case.known_edges if edge.relation == "__MASKED_RELATION__" and not (is_loadgen(edge.source) or is_loadgen(edge.target))]
    visible_causal = [edge for edge in case.known_edges if edge.relation == REL_CAUSAL and not (is_loadgen(edge.source) or is_loadgen(edge.target))]
    signals = _a4_pair_map(a4_row)

    candidate_lines = []
    for idx, edge in enumerate(masked_candidates):
        s = signals.get(_pair(edge.source, edge.target), {})
        candidate_lines.append(
            f"{idx}|{edge.source}|{edge.target}|"
            f"a4_decision={int(bool(s.get('predicted_causal')))}|"
            f"abd={_fmt(s.get('abductive_score'))}|"
            f"temporal={_fmt(s.get('temporal_score'))}|"
            f"anomaly={_fmt(s.get('anomaly_score'))}|"
            f"semantic_margin={_fmt(s.get('semantic_margin'))}|"
            f"psl={_fmt(s.get('soft_logic_score'))}|"
            f"final={_fmt(s.get('final_score'))}"
        )

    visible_lines = [f"{edge.source}|{edge.target}" for edge in visible_causal]
    evidence = sorted(
        case.evidence,
        key=lambda e: (-float(e.abnormality), e.timestamp if e.timestamp is not None else float("inf"), e.evidence_id),
    )
    evidence_lines = []
    for e in evidence:
        timestamp = "NA" if e.timestamp is None else f"{float(e.timestamp):.3f}"
        evidence_lines.append(
            f"{e.node}|{e.kind}|{e.signal}|abn={float(e.abnormality):.3f}|t={timestamp}|{_compact(e.text)}"
        )

    a4_roots = [str(x) for x in a4_row.get("predicted_roots", [])][:3]
    prompt = "\n".join([
        "Task: make the final RCA decision from an A4 abductive+semantic+soft-logic analysis.",
        "The graph is relation-masked: endpoint pairs are observed, but some causal-vs-noncausal labels are hidden.",
        "Use A4 scores together with telemetry. A4 is advisory and may be corrected.",
        "Select causal IDs only from MASKED_CANDIDATES; never invent an endpoint pair.",
        "VISIBLE_CAUSAL_EDGES are already observed causal relations and remain in the final propagation graph.",
        "Rank at most three final root-cause services. Prefer a root that is temporally/anomalously plausible and can propagate to a symptom through the final graph.",
        'Output JSON only: {"causal_ids":[0,2],"root_causes":["service-a"]}',
        "",
        "A4_ROOT_RANKING:",
        json.dumps(a4_roots, ensure_ascii=False),
        "",
        "SYMPTOM_SERVICES:",
        json.dumps(case.symptom_nodes, ensure_ascii=False),
        "",
        "VISIBLE_CAUSAL_EDGES source|target:",
        *(visible_lines or ["NONE"]),
        "",
        "MASKED_CANDIDATES id|source|target|A4 signals:",
        *(candidate_lines or ["NONE"]),
        "",
        "TELEMETRY node|kind|signal|abnormality|time|text:",
        *(evidence_lines or ["NONE"]),
    ])
    return prompt, masked_candidates


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
    id_match = re.search(r"causal_ids\s*[:=]\s*\[([^\]]*)\]", text, flags=re.I | re.S)
    if id_match:
        ids = [int(x) for x in re.findall(r"-?\d+", id_match.group(1))]
    root_match = re.search(r"root_causes\s*[:=]\s*\[([^\]]*)\]", text, flags=re.I | re.S)
    if root_match:
        roots = re.findall(r"['\"]([^'\"]+)['\"]", root_match.group(1))
    if id_match or root_match:
        return ids, roots, "regex_fallback"
    return [], [], "failed"


def _canonical_roots(raw_roots: list[str], case) -> tuple[list[str], int]:
    nodes = {edge.source for edge in case.known_edges} | {edge.target for edge in case.known_edges}
    nodes |= {e.node for e in case.evidence}
    by_norm: dict[str, str] = {}
    for node in sorted(nodes):
        if not is_loadgen(node):
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
    a4_results: str,
    out: str,
    model_name: str,
    mask_ratio: float,
    seed: int,
    limit: int,
    max_input_tokens: int,
    max_new_tokens: int,
) -> None:
    if model_name not in MODEL_SPECS:
        raise ValueError(f"Unsupported model: {model_name}")

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Install torch and transformers for A5 LLM adjudication") from exc

    a4 = json.loads(Path(a4_results).read_text(encoding="utf-8"))
    if str(a4.get("variant")) != "full":
        raise ValueError("A5 requires the A4 full ablation result")
    if abs(float(a4.get("mask_ratio")) - float(mask_ratio)) > 1e-9:
        raise ValueError("A4 mask ratio does not match A5 mask ratio")
    a4_by_case = {str(row["case_id"]): row for row in a4.get("rows", [])}

    cases = load_normalized_cases(data)
    if limit:
        cases = cases[:limit]

    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float32)
    model.to("cpu")
    model.eval()

    actual_parameters = int(sum(p.numel() for p in model.parameters()))
    spec = MODEL_SPECS[model_name]
    config_context = int(getattr(model.config, "max_position_embeddings", spec["published_context_window"]))
    effective_input_cap = min(int(max_input_tokens), max(1, config_context - int(max_new_tokens)))

    rows = []
    for index, case in enumerate(cases, start=1):
        a4_row = a4_by_case.get(case.case_id)
        if a4_row is None:
            raise KeyError(f"A4 result missing case {case.case_id}")

        visible, masked_truth = mask_relation_types(case, mask_ratio, seed)
        user_prompt, masked_candidates = _prompt(visible, a4_row)
        messages = [
            {"role": "system", "content": "You are the final deterministic RCA adjudicator. Use only supplied evidence and output valid JSON."},
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
        predicted_edges = [edge.key() for edge in visible.known_edges if edge.relation == REL_CAUSAL]
        predicted_edges.extend(masked_candidates[idx].key()[:-2] + (REL_CAUSAL, masked_candidates[idx].target) if False else (masked_candidates[idx].source, REL_CAUSAL, masked_candidates[idx].target) for idx in valid_ids)
        roots, invalid_roots = _canonical_roots(raw_roots, visible)
        if not roots:
            # Deterministic failure-safe: retain A4 ranking rather than converting
            # a formatting failure into an artificial zero-root prediction.
            roots, _ = _canonical_roots([str(x) for x in a4_row.get("predicted_roots", [])], visible)

        relation = relation_classification_metrics(predicted_edges, masked_truth)
        edge = service_edge_metrics(predicted_edges, case.gold_edges)
        node = node_metrics(
            predicted_edges,
            case.gold_edges,
            predicted_roots=roots,
            gold_roots=case.gold_root_causes,
        )
        root_service = root_set_metrics(roots, case.gold_root_causes)
        path = process_path_reachability(
            predicted_edges,
            roots,
            case.gold_root_causes,
            case.gold_alarm_nodes or case.symptom_nodes,
        )
        rows.append({
            "case_id": case.case_id,
            "root_service_precision": root_service.precision,
            "root_service_recall": root_service.recall,
            "root_service_f1": root_service.f1,
            "root_service_exact": exact_root_set(roots, case.gold_root_causes),
            "any_service_hit": any_root_service_hit(roots, case.gold_root_causes),
            "all_service_hit": all_root_services_hit(roots, case.gold_root_causes),
            "path_reachability": path,
            "node_precision": node.precision,
            "node_recall": node.recall,
            "node_f1": node.f1,
            "edge_precision": edge.precision,
            "edge_recall": edge.recall,
            "edge_f1": edge.f1,
            "relation_accuracy": relation.accuracy,
            "relation_precision": relation.precision,
            "relation_recall": relation.recall,
            "relation_f1": relation.f1,
            "process_path_reachability": path,
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
            "predicted_roots": roots,
            "predicted_edges": [list(edge) for edge in predicted_edges],
            "parse_mode": parse_mode,
            "raw_output": text,
        })
        if index % 25 == 0 or index == len(cases):
            print(f"A5_PROGRESS {index}/{len(cases)}")

    metric_keys = [
        "root_service_precision", "root_service_recall", "root_service_f1", "root_service_exact",
        "any_service_hit", "all_service_hit", "path_reachability",
        "node_precision", "node_recall", "node_f1",
        "edge_precision", "edge_recall", "edge_f1",
        "relation_accuracy", "relation_precision", "relation_recall", "relation_f1",
        "process_path_reachability", "root_exact_set", "root_hit_at_1", "root_hit_at_3",
        "parse_success", "prompt_truncated", "raw_prompt_tokens", "input_tokens", "output_tokens", "generation_seconds",
    ]
    result = {
        "variant": "llm_adjudication",
        "stage": "A5",
        "method": "A4 Abduction+DeBERTa+PSL -> LLM final adjudication",
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
            "role": "final adjudication over A4 outputs, not direct zero-shot relation recovery",
            "candidate_policy": "LLM may select only relation-masked observed endpoint pairs; no endpoint invention",
            "a4_input": "predicted roots plus abduction/temporal/anomaly/semantic/PSL/final scores; evaluator truth fields removed",
            "telemetry_policy": "same telemetry evidence as A0-A4, sorted deterministically by abnormality then onset",
            "gold_usage": "evaluation only; no gold root, edge, alarm, truth_relation or truth_causal field is included in prompt",
            "outcome_metrics": "OpenRCA2-compatible root service P/R/F1, exact, AnySvc, AllSvc plus Node/Edge F1 and Path Reachability",
            "relation_metrics": "controlled relation-mask recovery diagnostics, supplementary to OpenRCA2 metrics",
        },
        "summary": {key: _mean(rows, key) for key in metric_keys},
        "rows": rows,
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("A5_RESULT", json.dumps(result["summary"], sort_keys=True))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--a4-results", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct", choices=sorted(MODEL_SPECS))
    p.add_argument("--mask-ratio", type=float, required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--max-input-tokens", type=int, default=4096)
    p.add_argument("--max-new-tokens", type=int, default=96)
    args = p.parse_args()
    run(
        args.data,
        args.a4_results,
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
