from __future__ import annotations

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import build_ops_lite_cases as adapter
from openrca_mr.openrca2 import dump_normalized_cases


_original_case = adapter._case
_CASE_FILES = (
    "causal_graph.json",
    "env.json",
    "normal_traces.parquet",
    "abnormal_traces.parquet",
    "normal_metrics.parquet",
    "abnormal_metrics.parquet",
    "normal_logs.parquet",
    "abnormal_logs.parquet",
)


def _retrying_download(url: str, path: Path, max_attempts: int = 6) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    tmp = path.with_name(path.name + ".part")
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            if tmp.exists():
                tmp.unlink()
            urllib.request.urlretrieve(url, tmp)
            if not tmp.exists() or tmp.stat().st_size <= 0:
                raise IOError(f"empty download: {url}")
            tmp.replace(path)
            return
        except Exception as exc:
            last_error = exc
            if tmp.exists():
                tmp.unlink()
            if path.exists() and path.stat().st_size == 0:
                path.unlink()
            if attempt == max_attempts:
                break
            delay = min(16, 2 ** (attempt - 1))
            print(
                f"DOWNLOAD_RETRY attempt={attempt}/{max_attempts} delay={delay}s "
                f"url={url} error={type(exc).__name__}: {exc}"
            )
            time.sleep(delay)
    raise RuntimeError(f"download failed after {max_attempts} attempts: {url}") from last_error


adapter._download = _retrying_download


def _download_case_payload(name: str, cache: Path) -> None:
    folder = cache / name

    def one(filename: str) -> None:
        adapter._download(
            f"{adapter.BASE}/cases/{name}/{filename}?download=true",
            folder / filename,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(one, _CASE_FILES))


def _prefiltered_case(name: str, cache: Path):
    """Read the tiny label first; download telemetry only for attributed cases."""
    folder = cache / name
    label = folder / "label.txt"
    adapter._download(f"{adapter.BASE}/cases/{name}/label.txt?download=true", label)
    if label.read_text(encoding="utf-8").strip().lower() != "attributed":
        return None
    _download_case_payload(name, cache)
    return _original_case(name, cache, require_attributed=True)


def _standard_case(name: str, cache: Path):
    _download_case_payload(name, cache)
    return _original_case(name, cache, require_attributed=False)


def _attach_manifest_metadata(case, row: dict, all_labels: bool) -> None:
    case.metadata.update(
        {
            "system": row.get("system"),
            "manifest_primary_kind": row.get("primary_kind"),
            "manifest_subtypes": row.get("subtypes", []),
            "manifest_hybrid": bool(row.get("hybrid", False)),
            "manifest_root_services": row.get("root_services", []),
            "standard_all_500": bool(all_labels),
        }
    )


def _load_manifest(cache: Path) -> list[dict]:
    manifest = cache / "manifest.jsonl"
    adapter._download(f"{adapter.BASE}/manifest.jsonl?download=true", manifest)
    return [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _build_prefiltered_limit(out: Path, cache: Path, limit: int) -> list:
    """Build the first N valid attributed cases without downloading rejected telemetry."""
    rows = _load_manifest(cache)
    cases = []
    checked_labels = 0
    skipped_non_attributed = 0
    skipped_invalid = 0
    skipped_error = 0

    for row in rows:
        if len(cases) >= limit:
            break
        name = str(row["name"])
        checked_labels += 1
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

        _attach_manifest_metadata(case, row, all_labels=False)
        cases.append(case)
        print(
            "CASE",
            case.case_id,
            "known",
            len(case.known_edges),
            "evidence",
            len(case.evidence),
            "gold_edges",
            len(case.gold_edges),
        )

    if len(cases) < limit:
        raise RuntimeError(
            f"requested {limit} valid attributed cases but built {len(cases)} "
            f"after checking {checked_labels} labels"
        )

    dump_normalized_cases(cases, out)
    print(
        json.dumps(
            {
                "manifest_total": len(rows),
                "checked_labels": checked_labels,
                "normalized_cases": len(cases),
                "skipped_non_attributed": skipped_non_attributed,
                "skipped_invalid": skipped_invalid,
                "skipped_error": skipped_error,
                "prefilter_label_before_telemetry": True,
                "parallel_case_downloads": True,
                "out": str(out),
            },
            indent=2,
        )
    )
    return cases


def _build_manifest_range(
    out: Path,
    cache: Path,
    start_index: int,
    end_index: int,
    all_labels: bool = False,
) -> list:
    rows = _load_manifest(cache)
    start = max(0, start_index)
    stop = min(len(rows), end_index)
    if stop < start:
        raise ValueError("end-index must be >= start-index")

    cases = []
    skipped_non_attributed = 0
    skipped_invalid = 0
    skipped_error = 0
    error_names: list[str] = []
    for row in rows[start:stop]:
        name = str(row["name"])
        try:
            case = _standard_case(name, cache) if all_labels else _prefiltered_case(name, cache)
        except Exception as exc:
            skipped_error += 1
            error_names.append(name)
            print(f"SKIP_ERROR {name}: {type(exc).__name__}: {exc}")
            continue
        if case is None:
            if all_labels:
                skipped_invalid += 1
            else:
                skipped_non_attributed += 1
            continue

        if all_labels:
            if not case.gold_root_causes or not case.gold_edges:
                skipped_invalid += 1
                continue
        else:
            if not case.known_edges or not case.evidence or not case.gold_root_causes or not case.gold_edges:
                skipped_invalid += 1
                continue

        _attach_manifest_metadata(case, row, all_labels=all_labels)
        cases.append(case)
        print(
            "CASE",
            case.case_id,
            "known",
            len(case.known_edges),
            "evidence",
            len(case.evidence),
            "gold_edges",
            len(case.gold_edges),
        )

    stats = {
        "manifest_total": len(rows),
        "manifest_start": start,
        "manifest_end": stop,
        "requested_rows": stop - start,
        "normalized_cases": len(cases),
        "all_labels": all_labels,
        "skipped_non_attributed": skipped_non_attributed,
        "skipped_invalid": skipped_invalid,
        "skipped_error": skipped_error,
        "error_names": error_names,
        "out": str(out),
    }
    print(json.dumps(stats, indent=2))
    if skipped_error:
        raise RuntimeError(
            f"{skipped_error} case downloads/parses failed after retries: {error_names}"
        )
    if all_labels and skipped_invalid:
        raise RuntimeError(f"standard all-500 adapter dropped {skipped_invalid} curated cases")

    dump_normalized_cases(cases, out)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/ops_lite_20.jsonl")
    parser.add_argument("--cache", default=".cache/ops-lite")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--start-index", type=int)
    parser.add_argument("--end-index", type=int)
    parser.add_argument(
        "--all-labels",
        action="store_true",
        help="standard OpenRCA2: include all 500 curated manifest cases",
    )
    args = parser.parse_args()

    out = Path(args.out)
    cache = Path(args.cache)
    if args.start_index is not None or args.end_index is not None:
        if args.start_index is None or args.end_index is None:
            parser.error("--start-index and --end-index must be provided together")
        _build_manifest_range(
            out,
            cache,
            args.start_index,
            args.end_index,
            all_labels=args.all_labels,
        )
        return

    if args.all_labels:
        cases = adapter.build(out, cache, args.limit, require_attributed=False)
    else:
        cases = _build_prefiltered_limit(out, cache, args.limit)
    print(
        json.dumps(
            {"n": len(cases), "out": str(out), "all_labels": args.all_labels},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
