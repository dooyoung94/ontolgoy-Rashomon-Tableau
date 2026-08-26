from __future__ import annotations

import argparse
import json

from openrca_mr.experiment_matrix import run_stage1_matrix


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the fixed A0-A4 x 5-seed x 3-ratio Stage-1 paper matrix."
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--reference-data", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume only when input/reference fingerprints and the fixed grid match.",
    )
    args = parser.parse_args()

    result = run_stage1_matrix(
        data=args.data,
        reference_data=args.reference_data,
        out_dir=args.out_dir,
        resume=args.resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
