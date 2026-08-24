from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dafna-root", required=True)
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()

    dafna = Path(args.dafna_root)
    out = Path(args.out_root)
    claims_out = out / "claims"
    truth_out = out / "truth"
    claims_out.mkdir(parents=True, exist_ok=True)
    truth_out.mkdir(parents=True, exist_ok=True)

    gold_src = dafna / "data" / "Books_CSV" / "truth" / "book_golden.csv"
    claims_src = dafna / "data" / "Books_CSV" / "claims" / "claim1.txt"

    gold_rows: list[list[str]] = []
    valid_objects: set[str] = set()
    with gold_src.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.reader(f, skipinitialspace=True):
            if len(row) < 3:
                continue
            object_id, property_id, value = row[0].strip(), row[1].strip(), row[2]
            if not object_id or property_id != "AuthorsNamesList":
                continue
            valid_objects.add(object_id)
            gold_rows.append([object_id, property_id, value])

    with (truth_out / "book_golden.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ObjectID", "PropertyID", "PropertyValue"])
        w.writerows(gold_rows)

    selected_claims: list[list[str]] = []
    with claims_src.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.reader(f, skipinitialspace=True):
            # Repository Books_CSV contains a legacy extra "Remove" column:
            # ClaimID, Remove, ObjectID, PropertyID, PropertyValue, SourceID, TimeStamp.
            if len(row) < 7:
                continue
            if row[0].strip().lower() == "claimid":
                continue
            claim_id = row[0].strip()
            object_id = row[2].strip()
            property_id = row[3].strip()
            value = row[4]
            source_id = row[5].strip()
            timestamp = row[6].strip() or "null"
            if object_id not in valid_objects or property_id != "AuthorsNamesList":
                continue
            if not claim_id or not source_id:
                continue
            selected_claims.append(
                [claim_id, object_id, property_id, value, source_id, timestamp]
            )

    with (claims_out / "claim1.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ClaimID", "ObjectID", "PropertyID", "PropertyValue", "SourceID", "TimeStamp"])
        w.writerows(selected_claims)

    print(f"gold_objects={len(valid_objects)}")
    print(f"claims={len(selected_claims)}")
    print(f"claims_dir={claims_out}")
    print(f"truth_dir={truth_out}")


if __name__ == "__main__":
    main()
