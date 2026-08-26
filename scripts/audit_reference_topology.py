from __future__ import annotations

import argparse
import json
from pathlib import Path

from openrca_mr.reference_topology import load_reference_topologies
from openrca_mr.reference_validation import validate_reference_topologies


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit a contract-v1 reference topology before paper evaluation"
    )
    parser.add_argument("--reference-data", required=True)
    parser.add_argument("--out", help="Optional JSON audit-report path")
    args = parser.parse_args()

    topologies = load_reference_topologies(args.reference_data)
    report = validate_reference_topologies(topologies)
    payload = report.to_dict()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    print(rendered)
    if not report.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
