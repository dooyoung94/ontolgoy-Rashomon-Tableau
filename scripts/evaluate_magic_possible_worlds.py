from __future__ import annotations

import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

from rashomon_tableau.graph_paths import bidirectional_candidate_paths
from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.possible_worlds import PathRelationHypothesis, WorldChoice, build_possible_worlds, truth_marginal
from rashomon_tableau.tableau import RelationalTableau

MAGIC_BASE = "https://raw.githubusercontent.com/HYU-NLP/MAGIC/main/dataset/multi-hop"
FILES = [(1, 300), (2, 158), (3, 80), (4, 50)]
NEGATIVE_CUES = ("not ", "distinct", "disjoint", "different", "opposite", "excluding", "does not")
POSITIVE_CUES = ("equivalent", "same", "part of", "contains", "instance of", "subclass of")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def parse_literal(text: str, source: str | None = None) -> Literal | None:
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    parts = [norm(x) for x in text.split("|")]
    if len(parts) != 3:
        return None
    s, p, o = parts
    neg = p.startswith("not ")
    if neg:
        p = p[4:].strip()
    return Literal(p, s, o, negated=neg, source=source)


def flatten(value, source: str | None = None) -> list[Literal]:
    if isinstance(value, str):
        x = parse_literal(value, source)
        return [x] if x else []
    out: list[Literal] = []
    if isinstance(value, list):
        for item in value:
            out.extend(flatten(item, source))
    return out


def download_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def semantic_scores(path_relations: tuple[str, ...]) -> tuple[float, float, float]:
    """Label-free lexical prior used only for the B4 weighting ablation.

    It never reads row IDs, rel_id labels, gold answers, or perturb counts.
    The broad cue list is fixed before evaluation and intentionally weak.
    """
    text = " | ".join(path_relations)
    neg_hits = sum(cue in text for cue in NEGATIVE_CUES)
    pos_hits = sum(cue in text for cue in POSITIVE_CUES)
    if neg_hits > pos_hits:
        return 0.15, 0.70, 0.15
    if pos_hits > neg_hits:
        return 0.55, 0.20, 0.25
    return 0.25, 0.25, 0.50


def fact_key(x: Literal) -> tuple[str, str, str, bool]:
    return x.key()


def path_covers_gold(path, perturb: list[Literal]) -> bool:
    keys = {fact_key(x) for x in path.literals}
    return all(fact_key(x) in keys for x in perturb)


def evaluate_row(row: dict, ontology: Ontology, max_hops: int = 4) -> dict | None:
    originals = flatten(row.get("original_triplet"), "context1")
    perturbs = flatten(row.get("perturb_triplet"), "context2")
    subgraph = flatten(row.get("subgraph"), "kg")
    if not originals or not perturbs:
        return None

    reasoner = RelationalTableau(ontology)
    facts = subgraph + perturbs
    closure, _ = ontology.forward_chain(facts)

    b1_conflict = False
    b2_conflict = False
    b3_gold_world = False
    b3_exact_loc = False
    b4_conflict = False
    world_count = 0
    masses = []

    for query in originals:
        base = reasoner.verify(facts, query)
        b1_conflict |= base.status in {"CONTRADICTED", "BOTH"}

        paths = bidirectional_candidate_paths(closure, query.subject, query.object, max_hops=max_hops)
        choices: list[WorldChoice] = []
        best_single = None
        best_single_score = -1.0

        for idx, path in enumerate(paths[:12]):
            relations = tuple(edge.predicate for edge in path.literals)
            support_score, contradiction_score, unresolved_score = semantic_scores(relations)
            support_h = PathRelationHypothesis(
                f"path-{idx}-support", relations, query.predicate, support_score,
                negated_result=query.negated, origin="lexical-path-prior",
            )
            contradiction_h = PathRelationHypothesis(
                f"path-{idx}-contradiction", relations, query.predicate, contradiction_score,
                negated_result=not query.negated, origin="lexical-path-prior",
            )
            choices.extend([
                WorldChoice(support_h, f"path-{idx}:support", support_score),
                WorldChoice(contradiction_h, f"path-{idx}:contradiction", contradiction_score),
            ])
            if contradiction_score > best_single_score:
                best_single_score = contradiction_score
                best_single = contradiction_h

            # B3 is deliberately existential: can the correct conflicting explanation
            # survive as at least one internally consistent possible world?
            if path_covers_gold(path, perturbs):
                probe = build_possible_worlds(
                    facts,
                    [[WorldChoice(contradiction_h, f"path-{idx}:contradiction", contradiction_score)]],
                    reasoner,
                    {"context1": 0.5, "context2": 0.5, "kg": 0.5},
                    max_worlds=4,
                )
                if probe:
                    status = reasoner.verify(probe[0].facts, query).status
                    if status in {"CONTRADICTED", "BOTH"}:
                        b3_gold_world = True
                        b3_exact_loc = True

        if best_single is not None:
            single_worlds = build_possible_worlds(
                facts,
                [[WorldChoice(best_single, "best-single", best_single_score)]],
                reasoner,
                max_worlds=4,
            )
            if single_worlds:
                b2_conflict |= reasoner.verify(single_worlds[0].facts, query).status in {"CONTRADICTED", "BOTH"}

        if choices:
            # One uncertain semantic slot: worlds compete over which path interpretation
            # should explain the query.  An explicit unresolved world prevents forced truth.
            choices.append(WorldChoice.unresolved(confidence=0.50))
            worlds = build_possible_worlds(
                facts,
                [choices],
                reasoner,
                {"context1": 0.5, "context2": 0.5, "kg": 0.5},
                max_worlds=64,
            )
            world_count += len(worlds)
            marginal = truth_marginal(worlds, query, reasoner)
            masses.append({
                "support": marginal.support,
                "contradiction": marginal.contradiction,
                "unresolved": marginal.unresolved,
                "both": marginal.both,
            })
            # Conflict is selected only when opposing-world mass beats both direct
            # support and unresolved mass.  This is stricter than existential B3.
            b4_conflict |= marginal.contradiction + marginal.both > max(marginal.support, marginal.unresolved)

    return {
        "id": row.get("id"),
        "b1_static_tableau_conflict": b1_conflict,
        "b2_single_best_relation_conflict": b2_conflict,
        "b3_gold_world_recall": b3_gold_world,
        "b3_structured_exact_loc": b3_exact_loc,
        "b4_weighted_world_conflict": b4_conflict,
        "world_count": world_count,
        "marginals": masses,
    }


def main() -> None:
    ontology = Ontology.from_yaml("config/magic_ontology_rules.yaml")
    per_subset = []
    all_rows = []
    for conflict_count, expected_n in FILES:
        filename = f"{conflict_count}-multi-hop_conflict.json"
        rows = download_json(f"{MAGIC_BASE}/{filename}")
        evaluated = [x for row in rows if (x := evaluate_row(row, ontology)) is not None]
        all_rows.extend(evaluated)
        n = len(evaluated)
        def rate(key: str) -> float:
            return sum(bool(x[key]) for x in evaluated) / n if n else 0.0
        per_subset.append({
            "file": filename,
            "n": n,
            "expected_n": expected_n,
            "b1_static_tableau_conflict_recall": rate("b1_static_tableau_conflict"),
            "b2_single_best_relation_conflict_recall": rate("b2_single_best_relation_conflict"),
            "b3_gold_world_recall": rate("b3_gold_world_recall"),
            "b3_structured_exact_loc": rate("b3_structured_exact_loc"),
            "b4_weighted_world_conflict_recall": rate("b4_weighted_world_conflict"),
            "mean_world_count": sum(x["world_count"] for x in evaluated) / n if n else 0.0,
        })

    n = len(all_rows)
    def overall(key: str) -> float:
        return sum(bool(x[key]) for x in all_rows) / n if n else 0.0

    result = {
        "benchmark": "MAGIC multi-hop structured conflict cases",
        "n": n,
        "method": "Rashomon Worlds first ablation",
        "protocol_warning": (
            "All evaluated rows are conflict cases. Reported conflict values are recall, not full ID accuracy. "
            "structured_exact_loc is an internal strict analogue: all released perturb_triplet facts must occur on a retained conflicting proof path. "
            "It is not the paper's natural-language LOC metric."
        ),
        "leakage_policy": (
            "No row IDs, rel_id labels, gold answer labels, or sample-specific rules are used to generate relation hypotheses. "
            "B4 uses only a fixed broad lexical polarity prior over relation names."
        ),
        "overall": {
            "b1_static_tableau_conflict_recall": overall("b1_static_tableau_conflict"),
            "b2_single_best_relation_conflict_recall": overall("b2_single_best_relation_conflict"),
            "b3_gold_world_recall": overall("b3_gold_world_recall"),
            "b3_structured_exact_loc": overall("b3_structured_exact_loc"),
            "b4_weighted_world_conflict_recall": overall("b4_weighted_world_conflict"),
            "mean_world_count": sum(x["world_count"] for x in all_rows) / n if n else 0.0,
        },
        "per_subset": per_subset,
        "rows": all_rows,
    }
    out = Path("results/magic_possible_worlds_metrics.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
