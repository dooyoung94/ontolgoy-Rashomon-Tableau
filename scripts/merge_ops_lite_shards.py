from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

from openrca_mr.openrca2 import dump_normalized_cases, load_normalized_cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glob", dest="pattern", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--manifest-total", type=int, default=500)
    args = parser.parse_args()

    paths = sorted(Path(p) for p in glob.glob(args.pattern))
    if not paths:
        raise RuntimeError(f"No shard files matched {args.pattern}")

    by_id = {}
    counts = {}
    for path in paths:
        cases = load_normalized_cases(path)
        counts[path.name] = len(cases)
        for case in cases:
            if case.case_id in by_id:
                raise RuntimeError(f"Duplicate case_id across shards: {case.case_id}")
            by_id[case.case_id] = case

    cases = [by_id[key] for key in sorted(by_id)]
    dump_normalized_cases(cases, Path(args.out))
    stats = {
        "manifest_total_rows": args.manifest_total,
        "normalized_adapter_valid_cases": len(cases),
        "n_shards": len(paths),
        "shard_counts": counts,
        "out": args.out,
    }
    print(json.dumps(stats, indent=2, sort_keys=True))
    Path(args.out + ".meta.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
