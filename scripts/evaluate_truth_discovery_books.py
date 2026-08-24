from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import urllib.request

from rashomon_tableau.truth_resolution import (
    SourceClaim,
    classification_macro_f1,
    collapse_source_object_claims,
    logic_aware_truth_resolution,
    majority_set_vote,
    parse_multivalue,
    relation_label,
    reliability_weighted_set_vote,
    set_prf,
)

CLAIMS_URL = "https://raw.githubusercontent.com/qcri/DAFNA-EA/master/data/Books_CSV/claims/claim1.txt"
GOLD_URL = "https://raw.githubusercontent.com/qcri/DAFNA-EA/master/data/Books_CSV/truth/book_golden.csv"
OUT = Path("results/truth_discovery_books_metrics.json")


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "rashomon-tableau-benchmark/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_gold(text: str) -> dict[str, frozenset[str]]:
    gold = {}
    for row in csv.reader(io.StringIO(text), skipinitialspace=True):
        if len(row) < 3:
            continue
        object_id, property_id, value = row[0].strip(), row[1].strip(), row[2]
        if property_id != "AuthorsNamesList":
            continue
        parsed = parse_multivalue(value)
        if parsed:
            gold[object_id] = parsed
    return gold


def parse_claims(text: str, valid_objects: set[str]) -> list[SourceClaim]:
    claims: list[SourceClaim] = []
    # The source file has a malformed header but the actual records are regular 7-column CSV.
    for row in csv.reader(io.StringIO(text), skipinitialspace=True):
        if len(row) < 6:
            continue
        if row[0].strip().lower() == "claimid":
            continue
        object_id = row[2].strip()
        property_id = row[3].strip()
        value = row[4]
        source_id = row[5].strip()
        if object_id not in valid_objects or property_id != "AuthorsNamesList" or not source_id:
            continue
        parsed = parse_multivalue(value)
        if parsed:
            claims.append(SourceClaim(object_id, source_id, parsed))
    return collapse_source_object_claims(claims)


def evaluate_truth(pred: dict[str, frozenset[str]], gold: dict[str, frozenset[str]]) -> dict:
    objects = sorted(set(gold) & set(pred))
    exact = 0
    ps, rs, fs = [], [], []
    for obj in objects:
        p, r, f = set_prf(pred[obj], gold[obj])
        ps.append(p)
        rs.append(r)
        fs.append(f)
        exact += int(pred[obj] == gold[obj])
    return {
        "n": len(objects),
        "exact_set_accuracy": exact / len(objects) if objects else 0.0,
        "author_micro_like_precision_mean": sum(ps) / len(ps) if ps else 0.0,
        "author_recall_mean": sum(rs) / len(rs) if rs else 0.0,
        "author_f1_mean": sum(fs) / len(fs) if fs else 0.0,
    }


def evaluate_localization(
    claims: list[SourceClaim],
    pred_truth: dict[str, frozenset[str]],
    gold_truth: dict[str, frozenset[str]],
) -> dict:
    labels = ["exact", "partial", "conflict"]
    gold_labels, pred_labels = [], []
    for claim in claims:
        if claim.object_id not in gold_truth or claim.object_id not in pred_truth:
            continue
        gold_labels.append(relation_label(claim.values, gold_truth[claim.object_id]))
        pred_labels.append(relation_label(claim.values, pred_truth[claim.object_id]))
    accuracy = sum(g == p for g, p in zip(gold_labels, pred_labels)) / len(gold_labels)
    return {
        "n_claims": len(gold_labels),
        "accuracy": accuracy,
        "macro_f1": classification_macro_f1(gold_labels, pred_labels, labels),
        "gold_distribution": {label: gold_labels.count(label) for label in labels},
        "pred_distribution": {label: pred_labels.count(label) for label in labels},
    }


def main() -> None:
    gold = parse_gold(fetch_text(GOLD_URL))
    claims = parse_claims(fetch_text(CLAIMS_URL), set(gold))

    majority = majority_set_vote(claims)
    reliability_vote, baseline_reliability = reliability_weighted_set_vote(claims)
    logic_truth, logic_reliability, atom_scores = logic_aware_truth_resolution(claims)

    metrics = {
        "dataset": "DAFNA-EA Books_CSV",
        "claim_source": CLAIMS_URL,
        "gold_source": GOLD_URL,
        "gold_objects": len(gold),
        "collapsed_source_object_claims": len(claims),
        "sources": len({c.source_id for c in claims}),
        "methods": {
            "majority_whole_claim": evaluate_truth(majority, gold),
            "reliability_weighted_whole_claim": evaluate_truth(reliability_vote, gold),
            "logic_aware_atomic_truth_resolution": evaluate_truth(logic_truth, gold),
        },
        "conflict_localization": {
            "majority_whole_claim": evaluate_localization(claims, majority, gold),
            "reliability_weighted_whole_claim": evaluate_localization(claims, reliability_vote, gold),
            "logic_aware_atomic_truth_resolution": evaluate_localization(claims, logic_truth, gold),
        },
        "design": {
            "majority": "Exact whole-set majority over each ISBN.",
            "reliability_baseline": "Iterative source-reliability weighted whole-set vote; not claimed as an exact TruthFinder reproduction.",
            "proposed": "Authors are treated as atomic propositions. Partial subsets are compatible evidence rather than automatic contradictions; atom confidence and source reliability are iteratively co-estimated while preserving source provenance.",
            "normalization": "All methods share the same benchmark-side person canonicalization (surname + first initial) to reduce surface-form aliases.",
        },
        "sample_explanations": [],
    }

    for obj in sorted(logic_truth)[:5]:
        supporters = {}
        for atom in sorted(logic_truth[obj]):
            supporters[atom] = sorted(
                c.source_id for c in claims if c.object_id == obj and atom in c.values
            )[:10]
        metrics["sample_explanations"].append(
            {
                "object_id": obj,
                "predicted_truth": sorted(logic_truth[obj]),
                "gold_truth": sorted(gold.get(obj, frozenset())),
                "atom_scores": atom_scores.get(obj, {}),
                "supporting_sources": supporters,
            }
        )

    methods = metrics["methods"]
    base = methods["reliability_weighted_whole_claim"]
    prop = methods["logic_aware_atomic_truth_resolution"]
    metrics["gain_vs_reliability_baseline_pp"] = {
        "exact_set_accuracy": 100 * (prop["exact_set_accuracy"] - base["exact_set_accuracy"]),
        "author_f1_mean": 100 * (prop["author_f1_mean"] - base["author_f1_mean"]),
    }

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
