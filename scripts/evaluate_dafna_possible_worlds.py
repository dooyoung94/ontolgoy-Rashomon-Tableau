from __future__ import annotations

import csv
import io
import json
import urllib.request
from pathlib import Path

from rashomon_tableau.truth_resolution import (
    SourceClaim,
    collapse_source_object_claims,
    logic_aware_truth_resolution,
    parse_multivalue,
    reliability_weighted_set_vote,
    set_prf,
)
from rashomon_tableau.truth_worlds import possible_world_truth_resolution

CLAIMS_URL = "https://raw.githubusercontent.com/qcri/DAFNA-EA/master/data/Books_CSV/claims/claim1.txt"
GOLD_URL = "https://raw.githubusercontent.com/qcri/DAFNA-EA/master/data/Books_CSV/truth/book_golden.csv"
OUT = Path("results/dafna_possible_worlds_metrics.json")


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "rashomon-worlds-benchmark/1.0"})
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
    claims = []
    for row in csv.reader(io.StringIO(text), skipinitialspace=True):
        if len(row) < 6 or row[0].strip().lower() == "claimid":
            continue
        object_id, property_id, value, source_id = row[2].strip(), row[3].strip(), row[4], row[5].strip()
        if object_id not in valid_objects or property_id != "AuthorsNamesList" or not source_id:
            continue
        parsed = parse_multivalue(value)
        if parsed:
            claims.append(SourceClaim(object_id, source_id, parsed))
    return collapse_source_object_claims(claims)


def evaluate(pred: dict[str, frozenset[str]], gold: dict[str, frozenset[str]]) -> dict:
    objects = sorted(set(pred) & set(gold))
    exact = 0
    ps, rs, fs = [], [], []
    for object_id in objects:
        p, r, f = set_prf(pred[object_id], gold[object_id])
        ps.append(p)
        rs.append(r)
        fs.append(f)
        exact += int(pred[object_id] == gold[object_id])
    return {
        "n": len(objects),
        "exact_set_accuracy": exact / len(objects) if objects else 0.0,
        "author_precision_mean": sum(ps) / len(ps) if ps else 0.0,
        "author_recall_mean": sum(rs) / len(rs) if rs else 0.0,
        "author_f1_mean": sum(fs) / len(fs) if fs else 0.0,
    }


def coverage(candidates: dict[str, list[frozenset[str]]], gold: dict[str, frozenset[str]]) -> dict:
    objects = sorted(set(candidates) & set(gold))
    covered = sum(gold[o] in candidates[o] for o in objects)
    return {
        "n": len(objects),
        "gold_world_coverage": covered / len(objects) if objects else 0.0,
        "mean_candidate_worlds": sum(len(candidates[o]) for o in objects) / len(objects) if objects else 0.0,
        "max_candidate_worlds": max((len(candidates[o]) for o in objects), default=0),
    }


def reliability_summary(values: dict[str, float]) -> dict:
    vals = list(values.values())
    return {
        "sources": len(vals),
        "mean": sum(vals) / len(vals) if vals else 0.0,
        "min": min(vals) if vals else 0.0,
        "max": max(vals) if vals else 0.0,
    }


def main() -> None:
    gold = parse_gold(fetch_text(GOLD_URL))
    claims = parse_claims(fetch_text(CLAIMS_URL), set(gold))

    if len(gold) != 100:
        raise RuntimeError(f"Expected 100 gold books, got {len(gold)}")

    whole_pred, whole_rel = reliability_weighted_set_vote(claims)
    atomic_pred, atomic_rel, _ = logic_aware_truth_resolution(claims)

    uniform_pred, uniform_rel, uniform_worlds, candidates = possible_world_truth_resolution(claims, mode="uniform")
    hard_pred, hard_rel, hard_worlds, _ = possible_world_truth_resolution(claims, mode="hard")
    marginal_pred, marginal_rel, marginal_worlds, _ = possible_world_truth_resolution(claims, mode="marginal")

    metrics = {
        "dataset": "DAFNA-EA Books_CSV / AuthorsNamesList",
        "claim_source": CLAIMS_URL,
        "gold_source": GOLD_URL,
        "gold_objects": len(gold),
        "collapsed_source_object_claims": len(claims),
        "sources": len({c.source_id for c in claims}),
        "leakage_policy": "Gold is used only for evaluation and candidate-world coverage. Candidate worlds and reliabilities are generated from claims only.",
        "world_generation": coverage(candidates, gold),
        "methods": {
            "reliability_weighted_whole_claim_prior": evaluate(whole_pred, gold),
            "logic_aware_atomic_prior": evaluate(atomic_pred, gold),
            "possible_world_uniform": evaluate(uniform_pred, gold),
            "possible_world_hard_commit_reliability": evaluate(hard_pred, gold),
            "possible_world_marginal_reliability": evaluate(marginal_pred, gold),
        },
        "source_reliability": {
            "whole_claim_prior": reliability_summary(whole_rel),
            "logic_aware_atomic_prior": reliability_summary(atomic_rel),
            "possible_world_uniform": reliability_summary(uniform_rel),
            "possible_world_hard_commit": reliability_summary(hard_rel),
            "possible_world_marginal": reliability_summary(marginal_rel),
        },
        "design": {
            "candidate_worlds": "All observed author sets plus bounded combinations of the 12 most source-supported atomic authors up to the largest observed claim cardinality; max 256 worlds/object.",
            "world_evidence": "0.80 * reliability-weighted partial-claim compatibility + 0.20 * exact whole-claim support.",
            "uniform": "Equal source reliability; MAP truth world selected after one scoring pass.",
            "hard_commit": "Reliability iteratively updated against the current MAP world (early commitment).",
            "marginal": "Reliability iteratively updated by expected claim compatibility over the full posterior over worlds (delayed commitment).",
            "gold_usage": "No gold information enters generation, scoring, or reliability updates.",
        },
        "samples": [],
    }

    for object_id in sorted(gold)[:5]:
        worlds = marginal_worlds.get(object_id, [])[:5]
        metrics["samples"].append({
            "object_id": object_id,
            "gold": sorted(gold[object_id]),
            "prediction": sorted(marginal_pred.get(object_id, frozenset())),
            "top_worlds": [
                {
                    "values": sorted(w.values),
                    "posterior": w.posterior,
                    "evidence_score": w.evidence_score,
                    "exact_support": w.exact_support,
                    "observed": w.observed,
                }
                for w in worlds
            ],
        })

    atomic = metrics["methods"]["logic_aware_atomic_prior"]
    marginal = metrics["methods"]["possible_world_marginal_reliability"]
    hard = metrics["methods"]["possible_world_hard_commit_reliability"]
    metrics["gains_pp"] = {
        "marginal_vs_atomic_exact": 100 * (marginal["exact_set_accuracy"] - atomic["exact_set_accuracy"]),
        "marginal_vs_atomic_f1": 100 * (marginal["author_f1_mean"] - atomic["author_f1_mean"]),
        "marginal_vs_hard_exact": 100 * (marginal["exact_set_accuracy"] - hard["exact_set_accuracy"]),
        "marginal_vs_hard_f1": 100 * (marginal["author_f1_mean"] - hard["author_f1_mean"]),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
