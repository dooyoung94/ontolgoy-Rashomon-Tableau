from __future__ import annotations

import csv
import random
from dataclasses import replace
from pathlib import Path

from .models import BenchmarkCase, Literal
from .ontology import Ontology


def _with_perspective(lit: Literal, perspective: str, negated: bool | None = None) -> Literal:
    return replace(lit, perspective=perspective, negated=lit.negated if negated is None else negated)


def build_controlled_cases(stories: dict[str, dict[str, list[Literal]]], ontology: Ontology, seed: int = 42, max_cases_per_story: int = 80) -> list[BenchmarkCase]:
    """Build reproducible controlled cases from real CONAN gold propositions.

    These labels are derived for method verification; they are not original CONAN contradiction labels.
    """
    rng = random.Random(seed)
    cases: list[BenchmarkCase] = []
    for story, perspectives in stories.items():
        local: list[BenchmarkCase] = []
        names = sorted(perspectives)
        all_facts = [(p, f) for p, facts in perspectives.items() for f in facts]
        rng.shuffle(all_facts)

        for idx, (p, fact) in enumerate(all_facts[: max_cases_per_story // 4]):
            p2 = next((x for x in names if x != p), f"{p}_counter")
            local.append(BenchmarkCase(f"{story}::explicit::{idx}", story, p, p2, "contradiction", "explicit", [_with_perspective(fact,p,False)], [_with_perspective(fact,p2,True)]))

        inv_idx = 0
        for p, fact in all_facts:
            inv = ontology.inverse.get(fact.predicate)
            if not inv:
                continue
            p2 = next((x for x in names if x != p), f"{p}_counter")
            neg_inv = Literal(inv, fact.object, fact.subject, True, p2, story, "controlled")
            local.append(BenchmarkCase(f"{story}::inverse::{inv_idx}", story, p, p2, "contradiction", "implicit_inverse", [_with_perspective(fact,p,False)], [neg_inv]))
            inv_idx += 1
            if inv_idx >= max_cases_per_story // 8:
                break

        hier_idx = 0
        for p, fact in all_facts:
            parents = sorted(ontology.hierarchy.get(fact.predicate, []))
            if not parents:
                continue
            p2 = next((x for x in names if x != p), f"{p}_counter")
            neg_parent = Literal(parents[0], fact.subject, fact.object, True, p2, story, "controlled")
            local.append(BenchmarkCase(f"{story}::hierarchy::{hier_idx}", story, p, p2, "contradiction", "implicit_hierarchy", [_with_perspective(fact,p,False)], [neg_parent]))
            hier_idx += 1
            if hier_idx >= max_cases_per_story // 8:
                break

        for idx, (p, fact) in enumerate(all_facts[: max_cases_per_story // 4]):
            p2 = next((x for x in names if x != p), f"{p}_peer")
            local.append(BenchmarkCase(f"{story}::consistent::{idx}", story, p, p2, "consistent", "same_fact", [_with_perspective(fact,p)], [_with_perspective(fact,p2)]))

        div_idx = 0
        for i in range(len(all_facts)):
            p1, f1 = all_facts[i]
            for j in range(i + 1, len(all_facts)):
                p2, f2 = all_facts[j]
                if p1 == p2 or f1.positive_key() == f2.positive_key():
                    continue
                if f1.subject == f2.subject and f1.object == f2.object and (f1.predicate, f2.predicate) in ontology.incompatible:
                    continue
                local.append(BenchmarkCase(f"{story}::divergence::{div_idx}", story, p1, p2, "divergence", "different_nonconflicting_facts", [_with_perspective(f1,p1)], [_with_perspective(f2,p2)]))
                div_idx += 1
                break
            if div_idx >= max_cases_per_story // 4:
                break
        rng.shuffle(local)
        cases.extend(local[:max_cases_per_story])
    return cases


def load_annotated_cases(path: str | Path) -> list[BenchmarkCase]:
    out: list[BenchmarkCase] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("label", "").strip():
                continue
            b = lambda name: str(row.get(name, "")).strip().lower() in {"1","true","yes","y"}
            fa = Literal(row["predicate_a"], row["subject_a"], row["object_a"], b("negated_a"), row["perspective_a"], row["story"], str(path))
            fb = Literal(row["predicate_b"], row["subject_b"], row["object_b"], b("negated_b"), row["perspective_b"], row["story"], str(path))
            out.append(BenchmarkCase(row["case_id"], row["story"], row["perspective_a"], row["perspective_b"], row["label"], row.get("subtype", "human"), [fa], [fb], {"source":"human_annotation"}))
    return out
