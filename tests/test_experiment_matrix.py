from __future__ import annotations

import json

import pytest

from openrca_mr.experiment_matrix import run_stage1_matrix


def _fake_runner(**kwargs) -> dict:
    variant = kwargs["variant"]
    use_semantic = "deberta" in variant
    use_psl = "psl" in variant
    result = {
        "variant": variant,
        "seed": kwargs["seed"],
        "topology_missing_ratio": kwargs["topology_missing_ratio"],
        "claim_scope": "primary",
        "summary": {
            "micro_missing_relation_precision": 1.0,
            "micro_missing_relation_recall": 1.0,
            "micro_missing_relation_f1": 1.0,
            "false_edge_insertion_rate": 0.0,
            "candidate_recall_ceiling": 1.0,
            "realized_missing_ratio": kwargs["topology_missing_ratio"],
            "n_semantic_decision_flips": int(use_semantic),
            "n_psl_decision_flips": int(use_psl),
            "n_competing_endpoint_pairs": int(use_psl),
            "n_visible_functional_conflicts": 0,
        },
    }
    path = kwargs["out"]
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(result), encoding="utf-8")
    return result


def test_custom_matrix_checkpoints_aggregates_and_reuses_factories(tmp_path):
    data = tmp_path / "data.jsonl"
    reference = tmp_path / "reference.jsonl"
    data.write_text("input", encoding="utf-8")
    reference.write_text("reference", encoding="utf-8")
    calls = {"semantic": 0, "logic": 0}

    def semantic_factory():
        calls["semantic"] += 1
        return object()

    def logic_factory():
        calls["logic"] += 1
        return object()

    result = run_stage1_matrix(
        data=str(data),
        reference_data=str(reference),
        out_dir=str(tmp_path / "matrix"),
        variants=("abduction", "abduction_deberta", "abduction_psl"),
        seeds=(13, 42),
        missing_ratios=(0.2,),
        enforce_paper_grid=False,
        evaluation_runner=_fake_runner,
        semantic_factory=semantic_factory,
        logic_factory=logic_factory,
    )

    assert result["status"] == "complete"
    assert result["n_completed_runs"] == 6
    assert len(result["cells"]) == 3
    assert calls == {"semantic": 1, "logic": 1}
    assert result["ablation_identifiability"]["semantic_selection_flips"] == 2
    assert result["ablation_identifiability"]["psl_selection_flips"] == 2


def test_matrix_resume_rejects_changed_input_fingerprint(tmp_path):
    data = tmp_path / "data.jsonl"
    reference = tmp_path / "reference.jsonl"
    data.write_text("input", encoding="utf-8")
    reference.write_text("reference", encoding="utf-8")
    kwargs = dict(
        data=str(data),
        reference_data=str(reference),
        out_dir=str(tmp_path / "matrix"),
        variants=("abduction",),
        seeds=(13,),
        missing_ratios=(0.2,),
        enforce_paper_grid=False,
        evaluation_runner=_fake_runner,
    )
    run_stage1_matrix(**kwargs)
    data.write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match"):
        run_stage1_matrix(**kwargs, resume=True)


def test_primary_matrix_grid_is_fixed(tmp_path):
    data = tmp_path / "data.jsonl"
    reference = tmp_path / "reference.jsonl"
    data.write_text("input", encoding="utf-8")
    reference.write_text("reference", encoding="utf-8")

    with pytest.raises(ValueError, match="fixed A0-A4"):
        run_stage1_matrix(
            data=str(data),
            reference_data=str(reference),
            out_dir=str(tmp_path / "matrix"),
            variants=("abduction",),
            evaluation_runner=_fake_runner,
        )
