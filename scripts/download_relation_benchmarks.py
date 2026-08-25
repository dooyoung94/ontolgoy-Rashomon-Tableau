from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve


KG_BERT_RAW = "https://raw.githubusercontent.com/yao8839836/kg-bert/master/data"
DATASETS = {
    "WN18RR": ["train.tsv", "dev.tsv", "test.tsv", "entity2text.txt", "relation2text.txt"],
    "FB15k-237": ["train.tsv", "dev.tsv", "test.tsv", "entity2text.txt", "relation2text.txt"],
}


def download(dataset: str, output_root: Path) -> Path:
    if dataset not in DATASETS:
        raise ValueError(f"unsupported dataset: {dataset}")
    target_dir = output_root / dataset
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in DATASETS[dataset]:
        target = target_dir / filename
        if target.exists() and target.stat().st_size > 0:
            print(f"skip {target}")
            continue
        url = f"{KG_BERT_RAW}/{dataset}/{filename}"
        print(f"download {url} -> {target}")
        urlretrieve(url, target)
    return target_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="WN18RR")
    parser.add_argument("--output-root", default="data/kg_benchmarks")
    args = parser.parse_args()
    path = download(args.dataset, Path(args.output_root))
    print(path)


if __name__ == "__main__":
    main()
