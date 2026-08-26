from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable

from .psl import PslStructuralInference
from .reference_topology import PRIMARY_REFERENCE_RELATION_TYPES
from .semantic import DebertaStructuralRelationScorer
from .stage1_eval import STAGE1_PROTOCOL_VERSION, VARIANTS, run_stage1_evaluation


PAPER_VARIANTS = tuple(VARIANTS)
PAPER_SEEDS = (13, 42, 97, 123, 2026)
PAPER_MISSING_RATIOS = (0.2, 0.4, 0.6)
PAPER_RELATION_THRESHOLD = 0.5


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _runtime_metadata() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "implementation": sys.implementation.name,
        "deberta_model": DebertaStructuralRelationScorer.DEFAULT_MODEL,
        "deberta_revision": DebertaStructuralRelationScorer.DEFAULT_REVISION,
        "packages": {
            name: _package_version(name)
            for name in (
                "openrca-missing-relation",
                "numpy",
                "pandas",
                "torch",
                "transformers",
                "pslpython",
            )
        },
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def _result_path(root: Path, variant: str, seed: int, ratio: float) -> Path:
    ratio_name = f"ratio_{int(round(ratio * 100)):02d}"
    return root / "runs" / ratio_name / f"seed_{seed}" / f"{variant}.json"


def _aggregate_cells(results: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for result in results:
        grouped[(result["variant"], float(result["topology_missing_ratio"]))].append(
            result
        )

    metrics = (
        "micro_missing_relation_precision",
        "micro_missing_relation_recall",
        "micro_missing_relation_f1",
        "false_edge_insertion_rate",
        "candidate_recall_ceiling",
        "realized_missing_ratio",
    )
    cells: list[dict] = []
    for (variant, ratio), items in sorted(grouped.items()):
        cell: dict = {
            "variant": variant,
            "topology_missing_ratio": ratio,
            "n_seeds": len(items),
            "seeds": sorted(int(item["seed"]) for item in items),
        }
        for metric in metrics:
            values = [
                float(item["summary"][metric])
                for item in items
                if isinstance(item["summary"].get(metric), (int, float))
            ]
            cell[f"mean_{metric}"] = statistics.mean(values) if values else None
            cell[f"sample_std_{metric}"] = (
                statistics.stdev(values) if len(values) > 1 else None
            )
        cells.append(cell)
    return cells


def _ablation_identifiability(results: list[dict]) -> dict:
    indexed = {
        (
            int(result["seed"]),
            float(result["topology_missing_ratio"]),
            result["variant"],
        ): result
        for result in results
    }
    semantic_results = [result for result in results if VARIANTS[result["variant"]][1]]
    psl_results = [result for result in results if VARIANTS[result["variant"]][2]]

    semantic_flips = sum(
        int(result["summary"].get("n_semantic_decision_flips", 0))
        for result in semantic_results
    )
    psl_flips = sum(
        int(result["summary"].get("n_psl_decision_flips", 0))
        for result in psl_results
    )
    competing_pairs = sum(
        int(result["summary"].get("n_competing_endpoint_pairs", 0))
        for result in psl_results
    )
    visible_conflicts = sum(
        int(result["summary"].get("n_visible_functional_conflicts", 0))
        for result in psl_results
    )

    comparisons = {
        "deberta": (
            ("abduction", "abduction_deberta"),
            ("abduction_psl", "abduction_deberta_psl"),
        ),
        "psl": (
            ("abduction", "abduction_psl"),
            ("abduction_deberta", "abduction_deberta_psl"),
        ),
    }
    outcome_changes: dict[str, int] = {}
    comparable_cells: dict[str, int] = {}
    seed_ratio_cells = sorted({(seed, ratio) for seed, ratio, _variant in indexed})
    for factor, pairs in comparisons.items():
        changed = compared = 0
        for seed, ratio in seed_ratio_cells:
            for baseline, treatment in pairs:
                left = indexed.get((seed, ratio, baseline))
                right = indexed.get((seed, ratio, treatment))
                if left is None or right is None:
                    continue
                compared += 1
                left_f1 = left["summary"].get("micro_missing_relation_f1")
                right_f1 = right["summary"].get("micro_missing_relation_f1")
                if (
                    isinstance(left_f1, (int, float))
                    and isinstance(right_f1, (int, float))
                    and abs(float(left_f1) - float(right_f1)) > 1e-12
                ):
                    changed += 1
        outcome_changes[factor] = changed
        comparable_cells[factor] = compared

    warnings: list[str] = []
    if semantic_results and semantic_flips == 0:
        warnings.append(
            "DeBERTa caused no relation-selection decision flip at the configured "
            "threshold; A2/A4 are not identifiable as distinct selection methods."
        )
    if psl_results and psl_flips == 0:
        warnings.append(
            "PSL caused no relation-selection decision flip at the configured threshold; "
            "A3/A4 are not identifiable as distinct selection methods."
        )
    if psl_results and competing_pairs == 0 and visible_conflicts == 0:
        warnings.append(
            "No competing predicate pair or visible functional conflict activated the "
            "reported PSL constraints; review the candidate universe and ontology rules."
        )
    if outcome_changes["deberta"] == 0 and comparable_cells["deberta"]:
        warnings.append("DeBERTa changed no micro missing-relation F1 comparison cell.")
    if outcome_changes["psl"] == 0 and comparable_cells["psl"]:
        warnings.append("PSL changed no micro missing-relation F1 comparison cell.")

    return {
        "semantic_selection_flips": semantic_flips,
        "psl_selection_flips": psl_flips,
        "psl_competing_endpoint_pairs": competing_pairs,
        "psl_visible_functional_conflicts": visible_conflicts,
        "outcome_change_cells": outcome_changes,
        "comparable_cells": comparable_cells,
        "deberta_identifiable_at_selection_threshold": (
            semantic_flips > 0 if semantic_results else None
        ),
        "psl_identifiable_at_selection_threshold": (
            psl_flips > 0 if psl_results else None
        ),
        "warnings": warnings,
        "status": "ready" if not warnings else "review_required",
    }


def run_stage1_matrix(
    *,
    data: str,
    reference_data: str,
    out_dir: str,
    relation_threshold: float = 0.5,
    variants: tuple[str, ...] = PAPER_VARIANTS,
    seeds: tuple[int, ...] = PAPER_SEEDS,
    missing_ratios: tuple[float, ...] = PAPER_MISSING_RATIOS,
    enforce_paper_grid: bool = True,
    resume: bool = False,
    evaluation_runner: Callable[..., dict] = run_stage1_evaluation,
    semantic_factory: Callable[[], object] = DebertaStructuralRelationScorer,
    logic_factory: Callable[[], object] = PslStructuralInference,
) -> dict:
    """Run the fixed A0--A4 paper grid with shared model instances and checkpoints."""

    if enforce_paper_grid and (
        variants != PAPER_VARIANTS
        or seeds != PAPER_SEEDS
        or missing_ratios != PAPER_MISSING_RATIOS
        or relation_threshold != PAPER_RELATION_THRESHOLD
    ):
        raise ValueError(
            "primary paper runs must use fixed A0-A4 variants, seeds, ratios and threshold"
        )
    if not variants or not seeds or not missing_ratios:
        raise ValueError("variants, seeds and missing_ratios must not be empty")
    unknown_variants = set(variants) - set(VARIANTS)
    if unknown_variants:
        raise ValueError(f"unknown variants: {sorted(unknown_variants)}")
    if not 0.0 <= relation_threshold <= 1.0:
        raise ValueError("relation_threshold must be in [0, 1]")
    if any(not 0.0 <= ratio <= 1.0 for ratio in missing_ratios):
        raise ValueError("missing ratios must be in [0, 1]")

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    checkpoint_path = root / "matrix.json"
    fingerprints = {
        "input_sha256": _sha256(data),
        "reference_sha256": _sha256(reference_data),
    }
    grid = {
        "stage1_protocol_version": STAGE1_PROTOCOL_VERSION,
        "variants": list(variants),
        "seeds": list(seeds),
        "topology_missing_ratios": list(missing_ratios),
        "relation_threshold": relation_threshold,
        "evaluation_relation_types": sorted(PRIMARY_REFERENCE_RELATION_TYPES),
    }
    runtime = _runtime_metadata()

    existing: dict | None = None
    if checkpoint_path.exists():
        if not resume:
            raise FileExistsError(
                f"{checkpoint_path} already exists; use resume=True to continue it"
            )
        existing = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (
            existing.get("fingerprints") != fingerprints
            or existing.get("grid") != grid
            or existing.get("runtime") != runtime
        ):
            raise ValueError("existing matrix checkpoint does not match input files or grid")

    results: list[dict] = []
    semantic_model = None
    logic_model = None
    expected_runs = len(variants) * len(seeds) * len(missing_ratios)

    for ratio in missing_ratios:
        for seed in seeds:
            for variant in variants:
                output_path = _result_path(root, variant, seed, ratio)
                if resume and output_path.exists():
                    result = json.loads(output_path.read_text(encoding="utf-8"))
                    if (
                        result.get("variant") != variant
                        or result.get("seed") != seed
                        or float(result.get("topology_missing_ratio", -1.0)) != ratio
                        or result.get("claim_scope") != "primary"
                    ):
                        raise ValueError(f"stale or invalid resumable result: {output_path}")
                else:
                    _do_recovery, use_deberta, use_psl = VARIANTS[variant]
                    if use_deberta and semantic_model is None:
                        semantic_model = semantic_factory()
                    if use_psl and logic_model is None:
                        logic_model = logic_factory()
                    result = evaluation_runner(
                        data=data,
                        reference_data=reference_data,
                        out=str(output_path),
                        variant=variant,
                        topology_missing_ratio=ratio,
                        seed=seed,
                        relation_threshold=relation_threshold,
                        evaluation_relation_types=PRIMARY_REFERENCE_RELATION_TYPES,
                        semantic_scorer=semantic_model if use_deberta else None,
                        global_inference=logic_model if use_psl else None,
                    )
                if result.get("claim_scope") != "primary":
                    raise ValueError(
                        f"matrix run {variant}/{seed}/{ratio} is not a primary evaluation"
                    )
                results.append(result)
                checkpoint = {
                    "status": "in_progress",
                    "claim_scope": "primary" if enforce_paper_grid else "custom_grid",
                    "fingerprints": fingerprints,
                    "grid": grid,
                    "runtime": runtime,
                    "n_expected_runs": expected_runs,
                    "n_completed_runs": len(results),
                    "completed_outputs": [
                        str(_result_path(root, item["variant"], item["seed"], item["topology_missing_ratio"]))
                        for item in results
                    ],
                }
                _write_json(checkpoint_path, checkpoint)

    final = {
        "status": "complete",
        "claim_scope": "primary" if enforce_paper_grid else "custom_grid",
        "fingerprints": fingerprints,
        "grid": grid,
        "runtime": runtime,
        "n_expected_runs": expected_runs,
        "n_completed_runs": len(results),
        "cells": _aggregate_cells(results),
        "ablation_identifiability": _ablation_identifiability(results),
        "completed_outputs": [
            str(_result_path(root, item["variant"], item["seed"], item["topology_missing_ratio"]))
            for item in results
        ],
    }
    _write_json(checkpoint_path, final)
    return final
