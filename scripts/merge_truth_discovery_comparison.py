from __future__ import annotations

import argparse
import json
from pathlib import Path


def pct(v: float) -> str:
    return f"{100*v:.2f}%"


def append_row(rows, method: str, implementation: str, e: dict):
    rows.append({
        "method": method,
        "implementation": implementation,
        "n": e["n"],
        "exact_set_accuracy": e["exact_set_accuracy"],
        "author_f1_mean": e["author_f1_mean"],
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--worlds")
    ap.add_argument("--official-dir", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    ours = json.loads(Path(args.ours).read_text(encoding="utf-8"))
    rows = []
    for p in sorted(Path(args.official_dir).glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        append_row(rows, d["algorithm"], "Official DAFNA-EA", d["evaluation"])

    for key, label in [
        ("majority_whole_claim", "Whole-Claim Majority"),
        ("reliability_weighted_whole_claim", "Reliability-Weighted Vote"),
        ("logic_aware_atomic_truth_resolution", "Prior Atomic Resolution"),
    ]:
        append_row(rows, label, "This repository", ours["methods"][key])

    if args.worlds:
        worlds = json.loads(Path(args.worlds).read_text(encoding="utf-8"))
        for key, label in [
            ("possible_world_uniform", "Rashomon Worlds — Uniform"),
            ("possible_world_hard_commit_reliability", "Rashomon Worlds — Hard Commit"),
            ("possible_world_marginal_reliability", "Rashomon Worlds — Marginal Reliability"),
        ]:
            append_row(rows, label, "This repository", worlds["methods"][key])

    rows.sort(key=lambda r: (r["exact_set_accuracy"], r["author_f1_mean"]), reverse=True)
    result = {
        "dataset": "DAFNA-EA Books / AuthorsNamesList gold subset",
        "comparison_note": (
            "Official algorithms are executed from qcri/DAFNA-EA and re-evaluated with the same surname+first-initial "
            "normalization used for repository methods. DAFNA's own value bucketing and voter decisions are preserved. "
            "Rashomon Worlds candidate generation and source reliability use claims only; gold is evaluation-only."
        ),
        "rows": rows,
    }
    Path(args.out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# DAFNA-EA Books: Official Baselines vs Rashomon Worlds",
        "",
        "| Method | Implementation | N | Exact Truth Accuracy | Author F1 |",
        "|---|---|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(f"| {r['method']} | {r['implementation']} | {r['n']} | {pct(r['exact_set_accuracy'])} | {pct(r['author_f1_mean'])} |")
    lines += [
        "",
        "> Official DAFNA algorithms are cloned and executed in CI. Repository methods use the same 100-book AuthorsNamesList gold subset and shared benchmark-side person normalization. Gold truth is not used to construct or rank Rashomon Worlds.",
    ]
    Path(args.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
