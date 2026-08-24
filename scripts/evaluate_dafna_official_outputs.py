from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from rashomon_tableau.truth_resolution import parse_multivalue, set_prf


def read_gold(path: Path) -> dict[str, frozenset[str]]:
    out = {}
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.reader(f, skipinitialspace=True):
            if len(row) < 3 or row[0].strip().lower() == "objectid":
                continue
            if row[1].strip() != "AuthorsNamesList":
                continue
            value = parse_multivalue(row[2])
            if value:
                out[row[0].strip()] = value
    return out


def read_claim_map(path: Path) -> tuple[dict[str, tuple[str, frozenset[str]]], dict[int, tuple[str, frozenset[str]]]]:
    by_claim: dict[str, tuple[str, frozenset[str]]] = {}
    by_bucket_seed: dict[int, tuple[str, frozenset[str]]] = {}
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.reader(f, skipinitialspace=True):
            if len(row) < 6 or row[0].strip().lower() == "claimid":
                continue
            cid, obj, prop, raw = row[0].strip(), row[1].strip(), row[2].strip(), row[3]
            if prop != "AuthorsNamesList":
                continue
            val = parse_multivalue(raw)
            if val:
                by_claim[cid] = (obj, val)
    return by_claim, by_bucket_seed


def read_confidences(path: Path, claim_map: dict[str, tuple[str, frozenset[str]]]):
    # One row is emitted per claim. BucketId identifies DAFNA's value bucket and
    # Confidence/IsTrue are shared by all claims in that bucket.
    bucket_rows: dict[int, dict] = {}
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            cid = str(row.get("ClaimID", "")).strip()
            if cid not in claim_map:
                continue
            obj, value = claim_map[cid]
            bid = int(row["BucketId"])
            rec = bucket_rows.setdefault(
                bid,
                {
                    "object_id": obj,
                    "value": value,
                    "confidence": float(row["Confidence"]),
                    "is_true": str(row["IsTrue"]).lower() == "true",
                    "claims": 0,
                },
            )
            rec["claims"] += 1
    return list(bucket_rows.values())


def predict(bucket_rows: list[dict]) -> dict[str, frozenset[str]]:
    by_obj: dict[str, list[dict]] = {}
    for row in bucket_rows:
        by_obj.setdefault(row["object_id"], []).append(row)
    pred = {}
    for obj, rows in by_obj.items():
        # Respect the official voter's IsTrue flag first. If no bucket is marked true,
        # use the maximum confidence bucket so every evaluated object receives a value.
        true_rows = [r for r in rows if r["is_true"]]
        candidates = true_rows or rows
        best = max(candidates, key=lambda r: (r["confidence"], r["claims"], len(r["value"]), tuple(sorted(r["value"]))))
        pred[obj] = best["value"]
    return pred


def evaluate(pred, gold):
    objects = sorted(set(pred) & set(gold))
    exact = 0
    ps, rs, fs = [], [], []
    for obj in objects:
        p, r, f = set_prf(pred[obj], gold[obj])
        ps.append(p); rs.append(r); fs.append(f)
        exact += int(pred[obj] == gold[obj])
    return {
        "n": len(objects),
        "exact_set_accuracy": exact / len(objects) if objects else 0.0,
        "author_precision_mean": sum(ps) / len(ps) if ps else 0.0,
        "author_recall_mean": sum(rs) / len(rs) if rs else 0.0,
        "author_f1_mean": sum(fs) / len(fs) if fs else 0.0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--algorithm", required=True)
    ap.add_argument("--claims", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--confidences", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    gold = read_gold(Path(args.gold))
    claim_map, _ = read_claim_map(Path(args.claims))
    buckets = read_confidences(Path(args.confidences), claim_map)
    pred = predict(buckets)
    result = {
        "algorithm": args.algorithm,
        "implementation": "qcri/DAFNA-EA official Java implementation",
        "evaluation": evaluate(pred, gold),
        "official_output_buckets": len(buckets),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
