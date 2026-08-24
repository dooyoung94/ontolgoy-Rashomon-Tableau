from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from rashomon_tableau.graph_paths import bidirectional_candidate_paths
from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.tableau import RelationalTableau

MAGIC_BASE = "https://raw.githubusercontent.com/HYU-NLP/MAGIC/main/dataset"

# Published MAGIC Table 9/10 values used only as a reference peer group.
# They are natural-language LLM ID/LOC scores and are NOT directly comparable to this
# structured-triplet symbolic evaluator. Keeping them here makes the comparison explicit.
PEER_MULTI_HOP = {
    "Mixtral-8x7B": {"id": [23.47, 31.61, 38.16, 30.00], "loc": [12.59, 7.10, 6.58, 0.00]},
    "Llama-3.1-70B": {"id": [59.52, 78.67, 70.00, 73.91], "loc": [31.75, 25.33, 25.00, 8.70]},
    "Claude-3.5-Haiku": {"id": [41.00, 44.30, 63.75, 86.00], "loc": [33.67, 35.44, 33.75, 32.00]},
    "GPT-4o-mini": {"id": [70.67, 84.18, 86.25, 94.00], "loc": [54.67, 47.47, 33.75, 24.00]},
    "o1": {"id": [36.00, 58.23, 71.25, 62.00], "loc": [30.67, 30.38, 27.50, 12.00]},
}
MULTI_HOP_COUNTS = [300, 158, 80, 50]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def parse_literal(text: str, source: str | None = None) -> Literal | None:
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    parts = [norm(p) for p in text.split("|")]
    if len(parts) != 3 or not all(parts):
        return None
    subject, relation, object_ = parts
    negated = relation.startswith("not ")
    if negated:
        relation = relation[4:].strip()
    return Literal(relation, subject, object_, negated=negated, source=source)


def flatten_literals(value, source: str | None = None) -> list[Literal]:
    out: list[Literal] = []
    if isinstance(value, str):
        lit = parse_literal(value, source)
        if lit:
            out.append(lit)
    elif isinstance(value, list):
        for item in value:
            out.extend(flatten_literals(item, source))
    return out


def download_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def direct_pair_conflict(query: Literal, facts: list[Literal]) -> bool:
    """Legacy structured heuristic retained as an ablation, not as ontology truth."""
    for lit in facts:
        if query.subject == lit.subject and query.object == lit.object and query.predicate == lit.predicate:
            if query.negated != lit.negated:
                return True
        if (
            not query.negated
            and not lit.negated
            and query.subject == lit.subject
            and query.predicate == lit.predicate
            and query.object != lit.object
        ):
            return True
        if (
            not query.negated
            and not lit.negated
            and query.subject == lit.subject
            and query.object == lit.object
            and query.predicate != lit.predicate
        ):
            return True
    return False


def weighted(values: list[float], counts: list[int]) -> float:
    return sum(v * n for v, n in zip(values, counts)) / sum(counts)


def peer_summary() -> dict:
    rows = {}
    for model, scores in PEER_MULTI_HOP.items():
        rows[model] = {
            "published_id_by_conflict_count": scores["id"],
            "published_loc_by_conflict_count": scores["loc"],
            "weighted_id": weighted(scores["id"], MULTI_HOP_COUNTS),
            "weighted_loc": weighted(scores["loc"], MULTI_HOP_COUNTS),
        }
    return {
        "source": "MAGIC, Findings of EMNLP 2025, Tables 9 and 10",
        "counts": MULTI_HOP_COUNTS,
        "rows": rows,
        "peer_mean_weighted_id": sum(r["weighted_id"] for r in rows.values()) / len(rows),
        "peer_mean_weighted_loc": sum(r["weighted_loc"] for r in rows.values()) / len(rows),
        "comparability_warning": (
            "Published peers read natural-language contexts. Rashomon-Tableau here reads released structured triplets. "
            "The numbers must be shown in separate columns/tracks and must not be described as a head-to-head model ranking."
        ),
    }


def evaluate_file(hop: str, n_conflicts: int, ontology: Ontology, max_path_hops: int) -> dict:
    filename = f"{n_conflicts}-{hop}_conflict.json"
    rows = download_json(f"{MAGIC_BASE}/{hop}/{filename}")
    reasoner = RelationalTableau(ontology)

    n = 0
    direct_detected = 0
    tableau_detected = 0
    forward_candidate = 0
    reverse_candidate = 0
    any_candidate = 0
    statuses: Counter[str] = Counter()
    derived_support = 0
    derived_contradiction = 0
    examples = []

    for row in rows:
        originals = flatten_literals(row.get("original_triplet"), source="context1")
        perturbs = flatten_literals(row.get("perturb_triplet"), source="context2")
        subgraph = flatten_literals(row.get("subgraph"), source="kg")
        if not originals or not perturbs:
            continue
        n += 1

        facts = subgraph + perturbs
        closure, _ = ontology.forward_chain(facts)
        row_direct = False
        row_tableau = False
        row_forward = False
        row_reverse = False
        row_statuses = []

        for query in originals:
            if direct_pair_conflict(query, perturbs):
                row_direct = True

            paths = bidirectional_candidate_paths(closure, query.subject, query.object, max_hops=max_path_hops)
            if any(p.direction == "FORWARD" for p in paths):
                row_forward = True
            if any(p.direction == "REVERSE" for p in paths):
                row_reverse = True

            verification = reasoner.verify(facts, query)
            row_statuses.append(verification.status)
            statuses[verification.status] += 1
            if verification.status in {"CONTRADICTED", "BOTH"}:
                row_tableau = True
            if verification.supported and verification.support_rules and verification.support_rules != ["asserted"]:
                derived_support += 1
            if verification.contradicted and verification.contradiction_rules:
                if any(not rule.startswith("asserted") for rule in verification.contradiction_rules):
                    derived_contradiction += 1

            if len(examples) < 8 and (paths or verification.status != "UNRESOLVED"):
                examples.append(
                    {
                        "id": row.get("id"),
                        "query": query.text(),
                        "status": verification.status,
                        "support_rules": verification.support_rules,
                        "contradiction_rules": verification.contradiction_rules,
                        "candidate_paths": [p.text() for p in paths[:4]],
                    }
                )

        direct_detected += int(row_direct)
        tableau_detected += int(row_tableau)
        forward_candidate += int(row_forward)
        reverse_candidate += int(row_reverse)
        any_candidate += int(row_forward or row_reverse)

    def rate(x: int) -> float:
        return x / n if n else 0.0

    return {
        "file": filename,
        "n": n,
        "legacy_direct_heuristic_detection": rate(direct_detected),
        "ontology_tableau_conflict_detection": rate(tableau_detected),
        "forward_candidate_path_coverage": rate(forward_candidate),
        "reverse_candidate_path_coverage": rate(reverse_candidate),
        "bidirectional_candidate_path_coverage": rate(any_candidate),
        "query_status_counts": dict(statuses),
        "derived_support_count": derived_support,
        "derived_contradiction_count": derived_contradiction,
        "examples": examples,
    }


def aggregate(per_file: list[dict], hop: str, metric: str) -> float:
    rows = [x for x in per_file if hop in x["file"]]
    total = sum(x["n"] for x in rows)
    return sum(x["n"] * x[metric] for x in rows) / total if total else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology", default="config/magic_ontology_rules.yaml")
    parser.add_argument("--max-path-hops", type=int, default=4)
    parser.add_argument("--out", default="results/magic_bidirectional_tableau_metrics.json")
    args = parser.parse_args()

    ontology = Ontology.from_yaml(args.ontology)
    per_file = [
        evaluate_file(hop, n_conflicts, ontology, args.max_path_hops)
        for hop in ("single-hop", "multi-hop")
        for n_conflicts in (1, 2, 3, 4)
    ]

    result = {
        "benchmark": "MAGIC (Findings EMNLP 2025)",
        "method": "Ontology-Guided Bidirectional Tableau",
        "protocol": {
            "input": "released structured subgraph/original_triplet/perturb_triplet fields",
            "candidate_retrieval": "bounded forward + reverse graph paths after ontology closure",
            "verification": "q / not-q with explicit negation, incompatible relations, and declared exclusivity only",
            "closed_world_assumption": False,
            "max_path_hops": args.max_path_hops,
            "warning": (
                "Graph path coverage is candidate retrieval, not conflict accuracy. A path is accepted as truth/conflict only when ontology rules justify it."
            ),
        },
        "per_file": per_file,
        "aggregates": {
            "single_hop_legacy_direct_detection": aggregate(per_file, "single-hop", "legacy_direct_heuristic_detection"),
            "multi_hop_legacy_direct_detection": aggregate(per_file, "multi-hop", "legacy_direct_heuristic_detection"),
            "single_hop_ontology_tableau_detection": aggregate(per_file, "single-hop", "ontology_tableau_conflict_detection"),
            "multi_hop_ontology_tableau_detection": aggregate(per_file, "multi-hop", "ontology_tableau_conflict_detection"),
            "single_hop_bidirectional_path_coverage": aggregate(per_file, "single-hop", "bidirectional_candidate_path_coverage"),
            "multi_hop_bidirectional_path_coverage": aggregate(per_file, "multi-hop", "bidirectional_candidate_path_coverage"),
        },
        "published_peer_reference": peer_summary(),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
