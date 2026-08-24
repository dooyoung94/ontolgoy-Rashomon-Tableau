from __future__ import annotations

import argparse
import json
from pathlib import Path

from rashomon_tableau.ablation import evaluate_explanation_ablation, evaluate_scope_ablation
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.tableau import RelationalTableau


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ontology", default="config/ontology_rules.yaml")
    p.add_argument("--scope-n-per-class", type=int, default=20)
    p.add_argument("--explanation-cases", type=int, default=20)
    p.add_argument("--out", default="results/ablation_metrics.json")
    args = p.parse_args()

    ontology = Ontology.from_yaml(args.ontology)
    reasoner = RelationalTableau(ontology)
    result = {
        "scope_ablation": evaluate_scope_ablation(reasoner, args.scope_n_per_class),
        "explanation_ablation": evaluate_explanation_ablation(reasoner, args.explanation_cases),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
