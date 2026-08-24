from __future__ import annotations

import json
from pathlib import Path

from evaluate_magic_possible_worlds import (
    FILES,
    MAGIC_BASE,
    download_json,
    fact_key,
    flatten,
    make_hypothesis,
    merge_paths,
    parse_originals,
    path_covers_gold,
    perturb_groups,
)
from rashomon_tableau.deberta_world_scorer import DebertaWorldScorer
from rashomon_tableau.graph_paths import bidirectional_candidate_paths
from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.possible_worlds import WorldChoice, build_possible_worlds, truth_marginal
from rashomon_tableau.tableau import RelationalTableau


def literal_text(x: Literal) -> str:
    neg = "not " if x.negated else ""
    return f"{neg}{x.subject} {x.predicate} {x.object}"


def evaluate_query_deberta(
    query: Literal,
    gold_perturb: list[Literal],
    facts: list[Literal],
    closure: list[Literal],
    reasoner: RelationalTableau,
    scorer: DebertaWorldScorer,
    max_hops: int = 4,
) -> dict:
    raw_paths = bidirectional_candidate_paths(facts, query.subject, query.object, max_hops=max_hops)
    closure_paths = bidirectional_candidate_paths(closure, query.subject, query.object, max_hops=max_hops)
    paths = merge_paths(raw_paths, closure_paths)[:12]

    choices: list[WorldChoice] = []
    choice_gold: dict[str, bool] = {}
    query_text = literal_text(query)
    path_scores: list[dict] = []

    for idx, path in enumerate(paths):
        evidence = [literal_text(edge) for edge in path.literals]
        score = scorer.score(query_text, evidence)
        support_h = make_hypothesis(path, query, idx, "support", score.support)
        contradiction_h = make_hypothesis(path, query, idx, "contradiction", score.contradiction)
        support_label = f"path-{idx}:support"
        contradiction_label = f"path-{idx}:contradiction"
        unresolved_label = f"path-{idx}:unresolved"
        choices.extend([
            WorldChoice(support_h, support_label, score.support),
            WorldChoice(contradiction_h, contradiction_label, score.contradiction),
            WorldChoice.unresolved(unresolved_label, score.unresolved),
        ])
        choice_gold[contradiction_label] = path_covers_gold(path, gold_perturb)
        path_scores.append({
            "path": [literal_text(x) for x in path.literals],
            "support": score.support,
            "contradiction": score.contradiction,
            "unresolved": score.unresolved,
            "gold_path": choice_gold[contradiction_label],
        })

    if not choices:
        return {
            "conflict": False,
            "gold_loc": False,
            "path_count": 0,
            "world_count": 0,
            "marginal": {"support": 0.0, "contradiction": 0.0, "unresolved": 1.0, "both": 0.0},
            "path_scores": [],
        }

    worlds = build_possible_worlds(
        facts,
        [choices],
        reasoner,
        {"context1": 1.0, "context2": 1.0, "kg": 1.0},
        max_worlds=96,
    )
    marginal = truth_marginal(worlds, query, reasoner)
    conflict_mass = marginal.contradiction + marginal.both
    conflict = conflict_mass > max(marginal.support, marginal.unresolved)

    conflicting_worlds = [
        world for world in worlds
        if world.choices and reasoner.verify(world.facts, query).status in {"CONTRADICTED", "BOTH"}
    ]
    gold_loc = False
    selected_label = None
    if conflict and conflicting_worlds:
        best = max(conflicting_worlds, key=lambda w: w.weight)
        selected_label = best.choices[0].label
        gold_loc = bool(choice_gold.get(selected_label, False))

    return {
        "conflict": conflict,
        "gold_loc": gold_loc,
        "selected_label": selected_label,
        "path_count": len(paths),
        "world_count": len(worlds),
        "marginal": {
            "support": marginal.support,
            "contradiction": marginal.contradiction,
            "unresolved": marginal.unresolved,
            "both": marginal.both,
        },
        "path_scores": path_scores,
    }


def evaluate_row(row: dict, ontology: Ontology, scorer: DebertaWorldScorer) -> dict | None:
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
        evaluate_query_deberta(query, gold, facts, list(closure), reasoner, scorer)
        for query, gold in zip(originals, groups)
    ]
    return {
        "id": row.get("id"),
        "query_count": len(queries),
        "row_conflict": any(q["conflict"] for q in queries),
        "row_exact_loc": all(q["gold_loc"] for q in queries),
        "queries": queries,
    }


def summarize(rows: list[dict]) -> dict:
    queries = [q for row in rows for q in row["queries"]]
    n = len(rows)
    nq = len(queries)
    return {
        "rows": n,
        "queries": nq,
        "row_conflict_recall": sum(r["row_conflict"] for r in rows) / n if n else 0.0,
        "query_conflict_recall": sum(q["conflict"] for q in queries) / nq if nq else 0.0,
        "structured_row_exact_loc": sum(r["row_exact_loc"] for r in rows) / n if n else 0.0,
        "query_gold_path_selection": sum(q["gold_loc"] for q in queries) / nq if nq else 0.0,
        "mean_worlds_per_query": sum(q["world_count"] for q in queries) / nq if nq else 0.0,
        "mean_paths_per_query": sum(q["path_count"] for q in queries) / nq if nq else 0.0,
    }


def main() -> None:
    ontology = Ontology.from_yaml("config/magic_ontology_rules.yaml")
    scorer = DebertaWorldScorer()
    all_rows = []
    per_subset = []
    for conflict_count, expected_n in FILES:
        filename = f"{conflict_count}-multi-hop_conflict.json"
        raw_rows = download_json(f"{MAGIC_BASE}/{filename}")
        evaluated = [x for row in raw_rows if (x := evaluate_row(row, ontology, scorer)) is not None]
        all_rows.extend(evaluated)
        per_subset.append({"file": filename, "expected_n": expected_n, **summarize(evaluated)})

    result = {
        "benchmark": "MAGIC multi-hop structured conflict cases",
        "method": "Rashomon Worlds + DeBERTa-v3 NLI world scorer",
        "deberta_model": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        "protocol_warning": (
            "This is a structured world-ranking diagnostic using released MAGIC triplets. "
            "Conflict values are recall on conflict rows; structured exact LOC is not the paper's natural-language human-scored LOC."
        ),
        "gold_policy": "Gold perturb paths are used only after scoring to evaluate whether the selected conflicting world covers the paired gold evidence.",
        "overall": summarize(all_rows),
        "per_subset": per_subset,
        "rows": all_rows,
    }
    out = Path("results/magic_deberta_worlds_metrics.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
