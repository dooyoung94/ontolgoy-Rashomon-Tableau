from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from rashomon_tableau.graph_paths import CandidatePath, bidirectional_candidate_paths
from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.possible_worlds import PathRelationHypothesis, WorldChoice, build_possible_worlds, truth_marginal
from rashomon_tableau.tableau import RelationalTableau

MAGIC_BASE = "https://raw.githubusercontent.com/HYU-NLP/MAGIC/main/dataset/multi-hop"
FILES = [(1, 300), (2, 158), (3, 80), (4, 50)]
NEGATIVE_CUES = ("not ", "distinct", "disjoint", "different", "opposite", "excluding", "does not", "incompatible", "incongruent")
POSITIVE_CUES = ("equivalent", "same", "part of", "contains", "instance of", "subclass of")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def parse_literal(text: str, source: str | None = None) -> Literal | None:
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    parts = [norm(x) for x in text.split("|")]
    if len(parts) != 3 or not all(parts):
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


def parse_originals(value) -> list[Literal]:
    if isinstance(value, str):
        lit = parse_literal(value, "context1")
        return [lit] if lit else []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                lit = parse_literal(item, "context1")
                if lit:
                    out.append(lit)
        return out
    return []


def perturb_groups(value, expected: int) -> list[list[Literal]]:
    """Preserve MAGIC's original_triplet[i] <-> perturb_triplet[i] pairing."""
    if expected == 1:
        return [flatten(value, "context2")]
    if isinstance(value, list) and len(value) == expected and all(isinstance(item, list) for item in value):
        return [flatten(item, "context2") for item in value]
    # Conservative fallback: do not manufacture a pairing that is not present.
    return [[] for _ in range(expected)]


def download_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def semantic_scores(path_relations: tuple[str, ...]) -> tuple[float, float, float]:
    """Fixed label-free lexical prior for the first possible-world ablation.

    These are intentionally weak priors over relation names, not gold-derived
    ontology rules.  Later experiments should replace them with frozen external
    relation metadata or train-only rule induction.
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


def path_key(path: CandidatePath) -> tuple:
    return path.direction, tuple(fact_key(x) for x in path.literals)


def merge_paths(*groups: list[CandidatePath]) -> list[CandidatePath]:
    out = []
    seen = set()
    for group in groups:
        for path in group:
            key = path_key(path)
            if key not in seen:
                seen.add(key)
                out.append(path)
    return out


def path_covers_gold(path: CandidatePath, perturb: list[Literal]) -> bool:
    if not perturb:
        return False
    keys = {fact_key(x) for x in path.literals}
    return all(fact_key(x) in keys for x in perturb)


def make_hypothesis(path: CandidatePath, query: Literal, idx: int, kind: str, score: float) -> PathRelationHypothesis:
    return PathRelationHypothesis(
        name=f"path-{idx}-{kind}",
        relations=tuple(edge.predicate for edge in path.literals),
        result=query.predicate,
        confidence=score,
        negated_result=(query.negated if kind == "support" else not query.negated),
        origin="fixed-lexical-path-prior",
        start=path.literals[0].subject,
        end=path.literals[-1].object,
        swap_endpoints=path.direction == "REVERSE",
    )


def evaluate_query(
    query: Literal,
    gold_perturb: list[Literal],
    facts: list[Literal],
    closure: list[Literal],
    reasoner: RelationalTableau,
    max_hops: int,
) -> dict:
    base = reasoner.verify(facts, query)
    b1_conflict = base.status in {"CONTRADICTED", "BOTH"}

    # Raw paths preserve released evidence provenance; closure paths add hard
    # ontology-supported candidates.  Deduplication prevents duplicate world mass.
    raw_paths = bidirectional_candidate_paths(facts, query.subject, query.object, max_hops=max_hops)
    closure_paths = bidirectional_candidate_paths(closure, query.subject, query.object, max_hops=max_hops)
    paths = merge_paths(raw_paths, closure_paths)[:12]

    choices: list[WorldChoice] = []
    choice_gold: dict[str, bool] = {}
    single_candidates: list[tuple[float, str, PathRelationHypothesis | None]] = []
    existential_gold_world = False

    for idx, path in enumerate(paths):
        relations = tuple(edge.predicate for edge in path.literals)
        support_score, contradiction_score, unresolved_score = semantic_scores(relations)
        support_h = make_hypothesis(path, query, idx, "support", support_score)
        contradiction_h = make_hypothesis(path, query, idx, "contradiction", contradiction_score)
        support_label = f"path-{idx}:support"
        contradiction_label = f"path-{idx}:contradiction"
        unresolved_label = f"path-{idx}:unresolved"

        choices.extend([
            WorldChoice(support_h, support_label, support_score),
            WorldChoice(contradiction_h, contradiction_label, contradiction_score),
            WorldChoice.unresolved(unresolved_label, unresolved_score),
        ])
        single_candidates.extend([
            (support_score, support_label, support_h),
            (contradiction_score, contradiction_label, contradiction_h),
            (unresolved_score, unresolved_label, None),
        ])
        gold = path_covers_gold(path, gold_perturb)
        choice_gold[contradiction_label] = gold

        if gold:
            probe = build_possible_worlds(
                facts,
                [[WorldChoice(contradiction_h, contradiction_label, contradiction_score)]],
                reasoner,
                {"context1": 0.5, "context2": 0.5, "kg": 0.5},
                max_worlds=2,
            )
            if probe and reasoner.verify(probe[0].facts, query).status in {"CONTRADICTED", "BOTH"}:
                existential_gold_world = True

    # B2: early-commit single-world baseline.  It chooses one highest-probability
    # interpretation across support/contradiction/unresolved rather than forcing ¬q.
    b2_conflict = b1_conflict
    b2_choice = "static"
    if single_candidates:
        score, label, hypothesis = max(single_candidates, key=lambda x: (x[0], x[1].endswith(":unresolved")))
        b2_choice = label
        if hypothesis is not None:
            worlds = build_possible_worlds(facts, [[WorldChoice(hypothesis, label, score)]], reasoner, max_worlds=2)
            if worlds:
                b2_conflict = reasoner.verify(worlds[0].facts, query).status in {"CONTRADICTED", "BOTH"}
        else:
            b2_conflict = b1_conflict

    b4_conflict = b1_conflict
    b4_gold_loc = False
    world_count = 0
    marginal_dict = {"support": 0.0, "contradiction": 0.0, "unresolved": 1.0, "both": 0.0}
    if choices:
        worlds = build_possible_worlds(
            facts,
            [choices],
            reasoner,
            {"context1": 0.5, "context2": 0.5, "kg": 0.5},
            max_worlds=96,
        )
        world_count = len(worlds)
        marginal = truth_marginal(worlds, query, reasoner)
        marginal_dict = {
            "support": marginal.support,
            "contradiction": marginal.contradiction,
            "unresolved": marginal.unresolved,
            "both": marginal.both,
        }
        b4_conflict = marginal.contradiction + marginal.both > max(marginal.support, marginal.unresolved)

        conflicting_worlds = []
        for world in worlds:
            status = reasoner.verify(world.facts, query).status
            if status in {"CONTRADICTED", "BOTH"} and world.choices:
                conflicting_worlds.append(world)
        if b4_conflict and conflicting_worlds:
            best = max(conflicting_worlds, key=lambda w: w.weight)
            b4_gold_loc = choice_gold.get(best.choices[0].label, False)

    return {
        "b1_conflict": b1_conflict,
        "b2_conflict": b2_conflict,
        "b2_choice": b2_choice,
        "b3_gold_world": existential_gold_world,
        "b4_conflict": b4_conflict,
        "b4_gold_loc": b4_gold_loc,
        "path_count": len(paths),
        "world_count": world_count,
        "marginal": marginal_dict,
    }


def evaluate_row(row: dict, ontology: Ontology, max_hops: int = 4) -> dict | None:
    originals = parse_originals(row.get("original_triplet"))
    groups = perturb_groups(row.get("perturb_triplet"), len(originals))
    subgraph = flatten(row.get("subgraph"), "kg")
    if not originals or len(groups) != len(originals) or any(not group for group in groups):
        return None

    reasoner = RelationalTableau(ontology)
    all_perturbs = [fact for group in groups for fact in group]
    facts = subgraph + all_perturbs
    closure, _ = ontology.forward_chain(facts)

    queries = [
        evaluate_query(query, gold, facts, list(closure), reasoner, max_hops)
        for query, gold in zip(originals, groups)
    ]

    return {
        "id": row.get("id"),
        "query_count": len(queries),
        "b1_row_conflict": any(q["b1_conflict"] for q in queries),
        "b2_row_conflict": any(q["b2_conflict"] for q in queries),
        "b3_all_gold_worlds": all(q["b3_gold_world"] for q in queries),
        "b4_row_conflict": any(q["b4_conflict"] for q in queries),
        "b4_all_gold_loc": all(q["b4_gold_loc"] for q in queries),
        "world_count": sum(q["world_count"] for q in queries),
        "queries": queries,
    }


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    query_rows = [q for row in rows for q in row["queries"]]
    nq = len(query_rows)
    rate = lambda key: sum(bool(row[key]) for row in rows) / n if n else 0.0
    qrate = lambda key: sum(bool(q[key]) for q in query_rows) / nq if nq else 0.0
    return {
        "rows": n,
        "queries": nq,
        "b1_static_tableau_row_conflict_recall": rate("b1_row_conflict"),
        "b1_static_tableau_query_conflict_recall": qrate("b1_conflict"),
        "b2_early_commit_row_conflict_recall": rate("b2_row_conflict"),
        "b2_early_commit_query_conflict_recall": qrate("b2_conflict"),
        "b3_gold_world_query_recall": qrate("b3_gold_world"),
        "b3_structured_row_exact_loc": rate("b3_all_gold_worlds"),
        "b4_weighted_world_row_conflict_recall": rate("b4_row_conflict"),
        "b4_weighted_world_query_conflict_recall": qrate("b4_conflict"),
        "b4_structured_row_exact_loc": rate("b4_all_gold_loc"),
        "mean_world_count_per_row": sum(row["world_count"] for row in rows) / n if n else 0.0,
        "mean_world_count_per_query": sum(q["world_count"] for q in query_rows) / nq if nq else 0.0,
        "mean_candidate_paths_per_query": sum(q["path_count"] for q in query_rows) / nq if nq else 0.0,
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
        per_subset.append({"file": filename, "expected_n": expected_n, **summarize(evaluated)})

    result = {
        "benchmark": "MAGIC multi-hop structured conflict cases",
        "method": "Rashomon Worlds corrected first ablation",
        "protocol_warning": (
            "The released multi-hop files evaluated here contain conflict rows, so conflict metrics are recall rather than full ID accuracy. "
            "B3/B4 structured exact localization is row-level: every original_triplet[i] must be localized through its paired perturb_triplet[i]. "
            "This remains a structured provenance diagnostic and is not the paper's natural-language LOC metric."
        ),
        "leakage_policy": (
            "No row IDs, rel_id labels, gold conflict labels, or sample-specific composition rules are used to score relation interpretations. "
            "Gold perturb groups are used only after prediction to evaluate path localization."
        ),
        "ablation_definition": {
            "B1": "static hard ontology + Tableau",
            "B2": "single-world early commitment to the highest fixed lexical relation interpretation, including unresolved",
            "B3": "possible-world existential retention: whether at least one consistent conflicting world covers the paired gold perturb path",
            "B4": "weighted possible-world marginalization using the same fixed lexical relation prior; equal source reliability in MAGIC",
        },
        "overall": summarize(all_rows),
        "per_subset": per_subset,
        "rows": all_rows,
    }
    out = Path("results/magic_possible_worlds_metrics.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
