from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_ops_lite_cases as adapter
from openrca_mr.openrca2 import dump_normalized_cases


_original_case = adapter._case


def _prefiltered_case(name: str, cache: Path):
    folder = cache / name
    label = folder / "label.txt"
    adapter._download(f"{adapter.BASE}/cases/{name}/label.txt?download=true", label)
    if label.read_text(encoding="utf-8").strip().lower() != "attributed":
        return None
    return _original_case(name, cache)


def _build_manifest_range(out: Path, cache: Path, start_index: int, end_index: int) -> list:
    manifest = cache / "manifest.jsonl"
    adapter._download(f"{adapter.BASE}/manifest.jsonl?download=true", manifest)
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = max(0, start_index)
    stop = min(len(rows), end_index)
    if stop < start:
        raise ValueError("end-index must be >= start-index")

    cases = []
    skipped_non_attributed = 0
    skipped_invalid = 0
    skipped_error = 0
    for row in rows[start:stop]:
        name = str(row["name"])
        try:
            case = _prefiltered_case(name, cache)
        except Exception as exc:
            skipped_error += 1
            print(f"SKIP_ERROR {name}: {type(exc).__name__}: {exc}")
            continue
        if case is None:
            skipped_non_attributed += 1
            continue
        if not case.known_edges or not case.evidence or not case.gold_root_causes or not case.gold_edges:
            skipped_invalid += 1
            continue
        cases.append(case)
        print(
            "CASE", case.case_id,
            "known", len(case.known_edges),
            "evidence", len(case.evidence),
            "gold_edges", len(case.gold_edges),
        )

    dump_normalized_cases(cases, out)
    print(json.dumps({
        "manifest_total": len(rows),
        "manifest_start": start,
        "manifest_end": stop,
        "requested_rows": stop - start,
        "normalized_cases": len(cases),
        "skipped_non_attributed": skipped_non_attributed,
        "skipped_invalid": skipped_invalid,
        "skipped_error": skipped_error,
        "out": str(out),
    }, indent=2))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/ops_lite_20.jsonl")
    parser.add_argument("--cache", default=".cache/ops-lite")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--start-index", type=int)
    parser.add_argument("--end-index", type=int)
    args = parser.parse_args()

    out = Path(args.out)
    cache = Path(args.cache)
    if args.start_index is not None or args.end_index is not None:
        if args.start_index is None or args.end_index is None:
            parser.error("--start-index and --end-index must be provided together")
        _build_manifest_range(out, cache, args.start_index, args.end_index)
        return

    # Preserve the original fast 20-case behavior for the smoke workflow.
    adapter._case = _prefiltered_case
    cases = adapter.build(out, cache, args.limit)
    print(json.dumps({"n": len(cases), "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
