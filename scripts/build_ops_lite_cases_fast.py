from __future__ import annotations

import argparse
from pathlib import Path

import build_ops_lite_cases as adapter


_original_case = adapter._case


def _prefiltered_case(name: str, cache: Path):
    folder = cache / name
    label = folder / "label.txt"
    adapter._download(f"{adapter.BASE}/cases/{name}/label.txt?download=true", label)
    if label.read_text(encoding="utf-8").strip().lower() != "attributed":
        return None
    return _original_case(name, cache)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/ops_lite_20.jsonl")
    parser.add_argument("--cache", default=".cache/ops-lite")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    adapter._case = _prefiltered_case
    cases = adapter.build(Path(args.out), Path(args.cache), args.limit)
    print({"n": len(cases), "out": args.out})


if __name__ == "__main__":
    main()
