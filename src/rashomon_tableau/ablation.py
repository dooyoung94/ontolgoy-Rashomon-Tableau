from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .evaluation import classification_metrics
from .models import BenchmarkCase, Literal, Prediction
from .rashomon import minimal_unsat_subsets, rashomon_explanations
from .tableau import RelationalTableau


SCOPE_LABELS = [
    "consistent",
    "divergence",
    "intra_contradiction",
    "inter_contradiction",
]


def build_scope_ablation_cases(n_per_class: int = 20) -> list[BenchmarkCase]:
    """Controlled four-way benchmark for the perspective-separation ablation.

    The predicates are chosen from the CONAN-normalized relation inventory and the
    default ontology. The benchmark is intentionally controlled: it evaluates the
    *capability difference* between merged-ABox and perspective-indexed reasoning,
    not natural-language generalization.
    """
    cases: list[BenchmarkCase] = []

    for i in range(n_per_class):
        # Intra: A is already inconsistent through father_of_x -> parent_of_x.
        a = [
            Literal("father_of_x", f"parent_{i}", f"child_{i}", False, "A", "scope_ablation", "controlled"),
            Literal("parent_of_x", f"parent_{i}", f"child_{i}", True, "A", "scope_ablation", "controlled"),
        ]
        b = [Literal("friend_of_x", f"u_{i}", f"v_{i}", False, "B", "scope_ablation", "controlled")]
        cases.append(BenchmarkCase(f"scope::intra::{i}", "scope_ablation", "A", "B", "intra_contradiction", "scope_intra", a, b))

    for i in range(n_per_class):
        # Inter: each ABox is SAT, but the union closes after hierarchy expansion.
        a = [Literal("father_of_x", f"parent_{i}", f"child_{i}", False, "A", "scope_ablation", "controlled")]
        b = [Literal("parent_of_x", f"parent_{i}", f"child_{i}", True, "B", "scope_ablation", "controlled")]
        cases.append(BenchmarkCase(f"scope::inter::{i}", "scope_ablation", "A", "B", "inter_contradiction", "scope_inter", a, b))

    for i in range(n_per_class):
        a = [Literal("friend_of_x", f"a_{i}", f"b_{i}", False, "A", "scope_ablation", "controlled")]
        b = [Literal("friend_of_x", f"a_{i}", f"b_{i}", False, "B", "scope_ablation", "controlled")]
        cases.append(BenchmarkCase(f"scope::consistent::{i}", "scope_ablation", "A", "B", "consistent", "scope_consistent", a, b))

    for i in range(n_per_class):
        a = [Literal("friend_of_x", f"a_{i}", f"b_{i}", False, "A", "scope_ablation", "controlled")]
        b = [Literal("acquaintance_of_x", f"a_{i}", f"c_{i}", False, "B", "scope_ablation", "controlled")]
        cases.append(BenchmarkCase(f"scope::divergence::{i}", "scope_ablation", "A", "B", "divergence", "scope_divergence", a, b))

    return cases


def _same_positive_facts(case: BenchmarkCase) -> bool:
    left = {x.positive_key() for x in case.facts_a}
    right = {x.positive_key() for x in case.facts_b}
    return left == right


def classify_vanilla_merged(case: BenchmarkCase, reasoner: RelationalTableau) -> str:
    """Merged-ABox baseline.

    It performs a single satisfiability test after combining the two perspectives.
    Hence it can detect a clash but cannot localize whether it existed inside one
    perspective before merging. For an UNSAT union it therefore attributes the
    contradiction to the merged/inter case.
    """
    union = reasoner.check(case.facts_a + case.facts_b)
    if not union.satisfiable:
        return "inter_contradiction"
    return "consistent" if _same_positive_facts(case) else "divergence"


def classify_perspective_tableau(case: BenchmarkCase, reasoner: RelationalTableau) -> str:
    a = reasoner.check(case.facts_a)
    b = reasoner.check(case.facts_b)
    union = reasoner.check(case.facts_a + case.facts_b)
    if not a.satisfiable or not b.satisfiable:
        return "intra_contradiction"
    if not union.satisfiable:
        return "inter_contradiction"
    return "consistent" if _same_positive_facts(case) else "divergence"


def _as_prediction(case: BenchmarkCase, label: str, reasoner: RelationalTableau) -> Prediction:
    a = reasoner.check(case.facts_a)
    b = reasoner.check(case.facts_b)
    union = reasoner.check(case.facts_a + case.facts_b)
    return Prediction(
        case.case_id,
        case.label,
        label,
        case.subtype,
        case.story,
        case.perspective_a,
        case.perspective_b,
        a.satisfiable,
        b.satisfiable,
        union.satisfiable,
        0,
        {},
    )


def evaluate_scope_ablation(reasoner: RelationalTableau, n_per_class: int = 20) -> dict:
    cases = build_scope_ablation_cases(n_per_class=n_per_class)

    vanilla = [_as_prediction(c, classify_vanilla_merged(c, reasoner), reasoner) for c in cases]
    perspective = [_as_prediction(c, classify_perspective_tableau(c, reasoner), reasoner) for c in cases]

    vanilla_m = classification_metrics(vanilla)
    perspective_m = classification_metrics(perspective)

    return {
        "benchmark": "controlled_scope_ablation",
        "n": len(cases),
        "n_per_class": n_per_class,
        "labels": SCOPE_LABELS,
        "vanilla_merged_tableau": vanilla_m,
        "perspective_tableau": perspective_m,
        "rashomon_tableau": perspective_m,
        "accuracy_gain_pp_perspective_vs_vanilla": 100.0 * (perspective_m["accuracy"] - vanilla_m["accuracy"]),
        "macro_f1_gain_pp_perspective_vs_vanilla": 100.0 * (perspective_m["macro_f1"] - vanilla_m["macro_f1"]),
        "note": "Rashomon does not alter the class decision in this ablation; its contribution is evaluated separately as explanation-set coverage.",
    }


def build_multi_clash_explanation_cases(n_cases: int = 20) -> list[list[Literal]]:
    out: list[list[Literal]] = []
    for i in range(n_cases):
        out.append([
            Literal("father_of_x", f"p_{i}", f"c_{i}", False, "A", "explanation_ablation", "controlled"),
            Literal("parent_of_x", f"p_{i}", f"c_{i}", True, "B", "explanation_ablation", "controlled"),
            Literal("host_of_x", f"h_{i}", f"g_{i}", False, "A", "explanation_ablation", "controlled"),
            Literal("guest_of_x", f"g_{i}", f"h_{i}", True, "B", "explanation_ablation", "controlled"),
        ])
    return out


def evaluate_explanation_ablation(reasoner: RelationalTableau, n_cases: int = 20) -> dict:
    cases = build_multi_clash_explanation_cases(n_cases=n_cases)
    single_path_recalled = 0
    rashomon_recalled = 0
    total_gold_mus = 0
    details = []

    for idx, facts in enumerate(cases):
        muses = minimal_unsat_subsets(facts, reasoner, max_size=4, top_k=10)
        rashomon = rashomon_explanations(facts, reasoner, epsilon=0.1, top_k=10)
        gold_count = len(muses)
        total_gold_mus += gold_count
        single_count = min(1, gold_count)
        single_path_recalled += single_count
        rashomon_count = min(len(rashomon), gold_count)
        rashomon_recalled += rashomon_count
        details.append({
            "case": idx,
            "gold_minimal_explanations": gold_count,
            "single_path_returned": single_count,
            "rashomon_returned": len(rashomon),
        })

    single_cov = single_path_recalled / total_gold_mus if total_gold_mus else 0.0
    rashomon_cov = rashomon_recalled / total_gold_mus if total_gold_mus else 0.0
    return {
        "benchmark": "controlled_multi_clash_explanation_ablation",
        "n": n_cases,
        "gold_minimal_explanations": total_gold_mus,
        "single_path_explanation_coverage": single_cov,
        "rashomon_explanation_coverage": rashomon_cov,
        "coverage_gain_pp": 100.0 * (rashomon_cov - single_cov),
        "details": details,
        "note": "Controlled explanation benchmark with two independent minimal clashes per case.",
    }
