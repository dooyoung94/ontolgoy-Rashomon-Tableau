from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


VARIANT_LABELS = {
    "graph_only": "A0 Graph-only",
    "abduction": "A1 Abduction",
    "abduction_deberta": "A2 Abduction + DeBERTa",
    "abduction_psl": "A3 Abduction + PSL",
    "full": "A4 Abduction + DeBERTa + PSL",
}


def _ratio_label(value: float) -> str:
    return f"{round(value * 100):d}%"


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denom = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if denom <= 1e-12:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / denom


def _load_results(folder: Path) -> list[dict]:
    rows = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "summary" not in data or "mask_ratio" not in data:
            continue
        data["_path"] = str(path)
        rows.append(data)
    if not rows:
        raise RuntimeError(f"No benchmark JSON results found in {folder}")
    return rows


def _method_name(result: dict) -> str:
    if "variant" in result:
        return VARIANT_LABELS.get(str(result["variant"]), str(result["variant"]))
    return f"LLM {result.get('model', 'unknown')}"


def _summary_row(result: dict) -> dict:
    s = result.get("summary", {})
    metadata = result.get("model_metadata", {})
    return {
        "mask_ratio": float(result["mask_ratio"]),
        "mask": _ratio_label(float(result["mask_ratio"])),
        "method": _method_name(result),
        "kind": "ablation" if "variant" in result else "llm",
        "variant": result.get("variant"),
        "model": result.get("model"),
        "n_cases": result.get("n"),
        "relation_accuracy": s.get("relation_accuracy"),
        "relation_precision": s.get("relation_precision"),
        "relation_recall": s.get("relation_recall"),
        "relation_f1": s.get("relation_f1"),
        "node_f1": s.get("node_f1"),
        "edge_f1": s.get("edge_f1"),
        "path_reachability": s.get("process_path_reachability"),
        "root_hit_at_1": s.get("root_hit_at_1"),
        "root_hit_at_3": s.get("root_hit_at_3"),
        "parse_success": s.get("parse_success"),
        "prompt_truncated": s.get("prompt_truncated"),
        "mean_input_tokens": s.get("input_tokens"),
        "mean_output_tokens": s.get("output_tokens"),
        "mean_generation_seconds": s.get("generation_seconds"),
        "nominal_parameters": metadata.get("nominal_parameters"),
        "actual_parameters_loaded": metadata.get("actual_parameters_loaded"),
        "published_context_window": metadata.get("published_context_window"),
        "config_context_window": metadata.get("config_context_window"),
        "benchmark_max_input_tokens": metadata.get("benchmark_max_input_tokens"),
        "benchmark_max_new_tokens": metadata.get("benchmark_max_new_tokens"),
    }


def _pair_map(result: dict) -> dict[tuple[str, str, str], dict]:
    out = {}
    for row in result.get("rows", []):
        case_id = str(row.get("case_id"))
        for item in row.get("pair_diagnostics", []):
            key = (case_id, str(item.get("source_norm")), str(item.get("target_norm")))
            out[key] = item
    return out


def _compare_a2_a3(a2: dict, a3: dict) -> dict:
    left = _pair_map(a2)
    right = _pair_map(a3)
    common = sorted(set(left) & set(right))
    only_a2 = sorted(set(left) - set(right))
    only_a3 = sorted(set(right) - set(left))

    final2: list[float] = []
    final3: list[float] = []
    decision_disagreement = 0
    a2_only_positive = 0
    a3_only_positive = 0
    score_mae_values = []
    semantic_shift = []
    psl_shift = []
    exact_score_equal = 0

    for key in common:
        x, y = left[key], right[key]
        d2 = bool(x.get("predicted_causal"))
        d3 = bool(y.get("predicted_causal"))
        if d2 != d3:
            decision_disagreement += 1
            if d2:
                a2_only_positive += 1
            else:
                a3_only_positive += 1
        if x.get("final_score") is not None and y.get("final_score") is not None:
            s2 = float(x["final_score"])
            s3 = float(y["final_score"])
            final2.append(s2)
            final3.append(s3)
            delta = abs(s2 - s3)
            score_mae_values.append(delta)
            if delta <= 1e-12:
                exact_score_equal += 1
        if x.get("final_score") is not None and x.get("abductive_score") is not None:
            semantic_shift.append(abs(float(x["final_score"]) - float(x["abductive_score"])))
        if y.get("final_score") is not None and y.get("abductive_score") is not None:
            psl_shift.append(abs(float(y["final_score"]) - float(y["abductive_score"])))

    n = len(common)
    return {
        "mask_ratio": float(a2["mask_ratio"]),
        "mask": _ratio_label(float(a2["mask_ratio"])),
        "n_common_masked_pairs": n,
        "n_only_in_a2_diagnostics": len(only_a2),
        "n_only_in_a3_diagnostics": len(only_a3),
        "decision_disagreement_count": decision_disagreement,
        "decision_disagreement_rate": decision_disagreement / n if n else None,
        "a2_only_positive_threshold_crossings": a2_only_positive,
        "a3_only_positive_threshold_crossings": a3_only_positive,
        "final_score_mae": sum(score_mae_values) / len(score_mae_values) if score_mae_values else None,
        "final_score_pearson": _pearson(final2, final3),
        "exact_final_score_equal_rate": exact_score_equal / len(score_mae_values) if score_mae_values else None,
        "mean_abs_a2_semantic_shift_from_abduction": sum(semantic_shift) / len(semantic_shift) if semantic_shift else None,
        "mean_abs_a3_psl_shift_from_abduction": sum(psl_shift) / len(psl_shift) if psl_shift else None,
    }


def _pct(value) -> str:
    return "-" if value is None else f"{100.0 * float(value):.2f}%"


def _num(value, digits=4) -> str:
    return "-" if value is None else f"{float(value):.{digits}f}"


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _markdown(summary_rows: list[dict], diagnostics: list[dict], dataset_meta: dict | None) -> str:
    lines = [
        "# Full Controlled Relation-Masking Benchmark",
        "",
        "This report is for the controlled incomplete-relation experiment only. It is not the direct OpenRCA standard leaderboard comparison.",
        "",
    ]
    if dataset_meta:
        lines.extend([
            "## Dataset adapter coverage",
            "",
            f"- Manifest rows scanned: **{dataset_meta.get('manifest_total_rows', '-')}**",
            f"- Adapter-valid attributed cases: **{dataset_meta.get('normalized_adapter_valid_cases', '-')}**",
            "- Every manifest row is inspected; only attributed cases with valid trace-derived topology, telemetry evidence, roots and causal edges enter the controlled experiment.",
            "",
        ])

    lines.extend([
        "## A0-A4 vs Hugging Face LLM baselines",
        "",
        "| Mask | Method | Rel. P | Rel. R | Rel. F1 | Edge F1 | Path | Root@1 | Root@3 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in sorted(summary_rows, key=lambda x: (x["mask_ratio"], x["kind"], x["method"])):
        lines.append(
            f"| {row['mask']} | {row['method']} | {_pct(row['relation_precision'])} | {_pct(row['relation_recall'])} | "
            f"{_pct(row['relation_f1'])} | {_pct(row['edge_f1'])} | {_pct(row['path_reachability'])} | "
            f"{_pct(row['root_hit_at_1'])} | {_pct(row['root_hit_at_3'])} |"
        )

    lines.extend([
        "",
        "## Hugging Face LLM runtime/model controls",
        "",
        "| Model | Nominal params | Loaded params | Published context | Max input | Max output | Parse success | Truncated prompts | Mean input tokens | Mean output tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    seen = set()
    for row in sorted((x for x in summary_rows if x["kind"] == "llm"), key=lambda x: (x["model"], x["mask_ratio"])):
        key = (row["model"], row["mask_ratio"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"| {row['model']} ({row['mask']}) | {row['nominal_parameters'] or '-'} | {row['actual_parameters_loaded'] or '-'} | "
            f"{row['published_context_window'] or '-'} | {row['benchmark_max_input_tokens'] or '-'} | {row['benchmark_max_new_tokens'] or '-'} | "
            f"{_pct(row['parse_success'])} | {_pct(row['prompt_truncated'])} | {_num(row['mean_input_tokens'], 1)} | {_num(row['mean_output_tokens'], 1)} |"
        )

    lines.extend([
        "",
        "## A2 DeBERTa vs A3 PSL score diagnostics",
        "",
        "| Mask | Common pairs | Decision disagree | A2-only + | A3-only + | Final-score MAE | Pearson | Exact-score equal | |A2-abd| | |A3-abd| |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in diagnostics:
        lines.append(
            f"| {row['mask']} | {row['n_common_masked_pairs']} | {_pct(row['decision_disagreement_rate'])} | "
            f"{row['a2_only_positive_threshold_crossings']} | {row['a3_only_positive_threshold_crossings']} | "
            f"{_num(row['final_score_mae'])} | {_num(row['final_score_pearson'])} | {_pct(row['exact_final_score_equal_rate'])} | "
            f"{_num(row['mean_abs_a2_semantic_shift_from_abduction'])} | {_num(row['mean_abs_a3_psl_shift_from_abduction'])} |"
        )

    lines.extend([
        "",
        "Interpretation rule: equal binary metrics do not imply equal algorithms. If decision disagreement is near zero but score MAE is non-zero, the 0.5 threshold is collapsing different continuous scores to the same labels. If both score MAE and disagreement are near zero, PSL is functionally adding little independent signal on this dataset and its contribution must be reconsidered.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--dataset-meta")
    args = parser.parse_args()

    results = _load_results(Path(args.results_dir))
    summary_rows = [_summary_row(result) for result in results]
    summary_rows.sort(key=lambda x: (x["mask_ratio"], x["kind"], x["method"]))

    by_variant_ratio = {
        (str(r.get("variant")), float(r["mask_ratio"])): r
        for r in results if r.get("variant") is not None
    }
    diagnostics = []
    for ratio in (0.2, 0.4, 0.6):
        a2 = by_variant_ratio.get(("abduction_deberta", ratio))
        a3 = by_variant_ratio.get(("abduction_psl", ratio))
        if a2 and a3:
            diagnostics.append(_compare_a2_a3(a2, a3))

    dataset_meta = None
    if args.dataset_meta and Path(args.dataset_meta).exists():
        dataset_meta = json.loads(Path(args.dataset_meta).read_text(encoding="utf-8"))

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "full_summary.json").write_text(
        json.dumps({"dataset": dataset_meta, "summary": summary_rows, "a2_a3_diagnostics": diagnostics}, indent=2),
        encoding="utf-8",
    )
    _write_csv(out / "full_summary.csv", summary_rows)
    (out / "a2_a3_diagnostics.json").write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    report = _markdown(summary_rows, diagnostics, dataset_meta)
    (out / "FULL_RELATION_MASK_RESULTS.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
