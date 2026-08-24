from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


MAGIC_BASE = "https://raw.githubusercontent.com/HYU-NLP/MAGIC/main/dataset"


@dataclass(frozen=True)
class Triple:
    subject: str
    relation: str
    object: str


def norm(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def parse_triple(text: str) -> Triple | None:
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    parts = [norm(p) for p in text.split("|")]
    if len(parts) != 3 or not all(parts):
        return None
    return Triple(*parts)


def flatten_triples(value) -> list[Triple]:
    out: list[Triple] = []
    if isinstance(value, str):
        t = parse_triple(value)
        if t:
            out.append(t)
    elif isinstance(value, list):
        for item in value:
            out.extend(flatten_triples(item))
    return out


def relation_base(rel: str) -> tuple[str, bool]:
    r = norm(rel)
    neg = False
    if r.startswith("not "):
        neg = True
        r = r[4:]
    return r, neg


def triple_conflict(a: Triple, b: Triple) -> bool:
    ra, na = relation_base(a.relation)
    rb, nb = relation_base(b.relation)
    # Explicit negation of the same relation/value.
    if a.subject == b.subject and a.object == b.object and ra == rb and na != nb:
        return True
    # Functional-style conflict: same subject/relation but competing object values.
    # MAGIC perturbations are intentionally generated around the target relation, so this is
    # a benchmark-side structured baseline, not a claim of universal relation functionality.
    if a.subject == b.subject and ra == rb and not na and not nb and a.object != b.object:
        return True
    # Relation replacement over the same subject-object pair (father vs brother, etc.).
    if a.subject == b.subject and a.object == b.object and ra != rb:
        return True
    return False


def exact_overlap(a: Triple, b: Triple) -> float:
    score = 0.0
    if a.subject == b.subject:
        score += 0.4
    if relation_base(a.relation)[0] == relation_base(b.relation)[0]:
        score += 0.35
    if a.object == b.object:
        score += 0.25
    return score


def localize_pair(originals: list[Triple], perturbs: list[Triple]) -> tuple[Triple | None, Triple | None, bool]:
    best = None
    best_score = -1.0
    for o in originals:
        for p in perturbs:
            score = exact_overlap(o, p)
            conflict = triple_conflict(o, p)
            if conflict:
                score += 1.0
            if score > best_score:
                best_score = score
                best = (o, p, conflict)
    return best if best is not None else (None, None, False)


def download_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def evaluate_file(hop: str, n_conflicts: int) -> dict:
    filename = f"{n_conflicts}-{hop}_conflict.json"
    url = f"{MAGIC_BASE}/{hop}/{filename}"
    rows = download_json(url)

    n = 0
    detection_correct = 0
    localized = 0
    relation_replacement = 0
    explicit_negation = 0
    object_replacement = 0

    for row in rows:
        originals = flatten_triples(row.get("original_triplet"))
        perturbs = flatten_triples(row.get("perturb_triplet"))
        if not originals or not perturbs:
            continue
        n += 1
        o, p, conflict = localize_pair(originals, perturbs)
        if conflict:
            detection_correct += 1
        if o is not None and p is not None:
            localized += 1
            ro, no = relation_base(o.relation)
            rp, np = relation_base(p.relation)
            if ro == rp and no != np and o.subject == p.subject and o.object == p.object:
                explicit_negation += 1
            elif ro == rp and o.subject == p.subject and o.object != p.object:
                object_replacement += 1
            elif o.subject == p.subject and o.object == p.object and ro != rp:
                relation_replacement += 1

    return {
        "file": filename,
        "n": n,
        "conflict_detection_accuracy": detection_correct / n if n else 0.0,
        "pair_localization_coverage": localized / n if n else 0.0,
        "localized_pattern_counts": {
            "explicit_negation": explicit_negation,
            "object_replacement": object_replacement,
            "relation_replacement": relation_replacement,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="results/magic_structured_metrics.json")
    args = parser.parse_args()

    per_file = []
    for hop in ("single-hop", "multi-hop"):
        for n_conflicts in (1, 2, 3, 4):
            per_file.append(evaluate_file(hop, n_conflicts))

    total_n = sum(x["n"] for x in per_file)
    weighted_det = sum(x["n"] * x["conflict_detection_accuracy"] for x in per_file) / total_n
    weighted_loc = sum(x["n"] * x["pair_localization_coverage"] for x in per_file) / total_n

    result = {
        "benchmark": "MAGIC (EMNLP 2025 Findings)",
        "mode": "structured-triplet sanity benchmark",
        "important_caveat": (
            "This evaluator uses MAGIC's released structured original/perturbed triplets, not only the natural-language contexts. "
            "It therefore validates deterministic conflict/provenance handling but is not directly comparable to the paper's LLM ID/LOC scores."
        ),
        "total_examples": total_n,
        "conflict_detection_accuracy": weighted_det,
        "pair_localization_coverage": weighted_loc,
        "per_file": per_file,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
