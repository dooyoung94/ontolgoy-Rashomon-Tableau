from __future__ import annotations

import argparse
import json
from pathlib import Path

from openrca_mr.reference_topology import (
    dump_reference_topologies,
    load_reference_topologies,
)
from openrca_mr.reference_validation import validate_reference_topologies


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize and validate an independently authored reference-topology "
            "manifest. This command never derives gold relations from telemetry."
        )
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="JSON/JSONL manifest containing one topology or a topologies list",
    )
    parser.add_argument("--out", required=True, help="Canonical reference JSONL output")
    parser.add_argument(
        "--audit-out",
        help="Optional JSON path for the validation report",
    )
    args = parser.parse_args()

    topologies = load_reference_topologies(args.manifest)
    report = validate_reference_topologies(topologies)
    payload = report.to_dict()
    if args.audit_out:
        audit_path = Path(args.audit_out)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if not report.valid:
        raise SystemExit(json.dumps(payload, ensure_ascii=False, indent=2))

    dump_reference_topologies(topologies, args.out)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
