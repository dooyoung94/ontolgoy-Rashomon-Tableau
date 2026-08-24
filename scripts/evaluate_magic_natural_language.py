from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

from rashomon_tableau.deberta_world_scorer import DebertaWorldScorer
from rashomon_tableau.graph_paths import bidirectional_candidate_paths
from rashomon_tableau.models import Literal
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.openai_frontend import (
    OpenAIResponsesClient,
    direct_magic_judgment,
    extract_claims,
    score_worlds_batch,
)
from rashomon_tableau.possible_worlds import PathRelationHypothesis, WorldChoice, build_possible_worlds, truth_marginal
from rashomon_tableau.tableau import RelationalTableau

MAGIC_BASE = "https://raw.githubusercontent.com/HYU-NLP/MAGIC/main/dataset/multi-hop"
FILES = [
    "1-multi-hop_conflict.json",
    "2-multi-hop_conflict.json",
    "3-multi-hop_conflict.json",
    "4-multi-hop_conflict.json",
]


def norm(x: str) -> str:
    return re.sub(r"\s+", " ", x.strip().lower())


def download_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def extracted_literals(claims: list[dict], source: str) -> list[Literal]:
    out: list[Literal] = []
    for claim in claims:
        if claim.get("source") != source:
            continue
        out.append(
            Literal(
                norm(claim["relation"]),
                norm(claim["subject"]),
                norm(claim["object"]),
                bool(claim.get("negated", False)),
                story=str(claim.get("sentence_id", 0)),
                source=source,
            )
        )
    return out


def literal_text(x: Literal) -> str:
    neg = "NOT " if x.negated else ""
    return f"{neg}{x.subject} --{x.predicate}--> {x.object} [source={x.source}, sentence={x.story}]"


def _normalize_scores(support: float, contradiction: float, unresolved: float) -> tuple[float, float, float]:
    total = max(1e-9, support + contradiction + unresolved)
    return support / total, contradiction / total, unresolved / total


def build_rashomon_judgment(
    client,
    context1: str,
    context2: str,
    max_hops: int = 4,
    world_scorer: DebertaWorldScorer | None = None,
    extracted_response=None,
) -> dict:
    """Extract query/path candidates, score them, and detect existential conflict.

    The possible-world marginal is retained as a diagnostic/ablation signal, but it
    no longer controls the MAGIC binary decision. MAGIC asks whether at least one
    factual conflict exists, so a single query-path pair whose contradiction score
    dominates both support and unresolved is sufficient for a positive decision.
    """
    extracted = extracted_response or extract_claims(client, context1, context2)
    extraction_was_shared = extracted_response is not None
    claims = extracted.data["claims"]
    c1 = extracted_literals(claims, "context1")
    c2 = extracted_literals(claims, "context2")

    ontology = Ontology()
    reasoner = RelationalTableau(ontology)
    usage = {
        "input_tokens": 0 if extraction_was_shared else extracted.usage.input_tokens,
        "output_tokens": 0 if extraction_was_shared else extracted.usage.output_tokens,
        "calls": 0 if extraction_was_shared else 1,
        "shared_extraction": extraction_was_shared,
    }
    scorer_name = "deberta-v3" if world_scorer is not None else "same-llm-batch"

    prepared: list[dict] = []
    batch_items: list[dict] = []
    for q_index, query in enumerate(c1):
        paths = bidirectional_candidate_paths(
            c2, query.subject, query.object, max_hops=max_hops, max_paths_per_direction=8
        )
        for p_index, path in enumerate(paths):
            prefix = f"q{q_index}-p{p_index}"
            query_repr = literal_text(query)
            evidence_repr = [literal_text(x) for x in path.literals]
            prepared.append({
                "id": prefix,
                "q_index": q_index,
                "query": query,
                "path": path,
                "query_repr": query_repr,
                "evidence_repr": evidence_repr,
            })
            if world_scorer is None:
                batch_items.append({"id": prefix, "query": query_repr, "world_evidence": evidence_repr})

    score_map: dict[str, tuple[float, float, float]] = {}
    if world_scorer is None:
        if batch_items:
            batch = score_worlds_batch(client, batch_items)
            usage["input_tokens"] += batch.usage.input_tokens
            usage["output_tokens"] += batch.usage.output_tokens
            usage["calls"] += 1
            returned = batch.data.get("scores", [])
            returned_ids = [str(x.get("id")) for x in returned]
            expected_ids = [str(x["id"]) for x in batch_items]
            if len(returned_ids) != len(set(returned_ids)):
                raise RuntimeError("Batch world scorer returned duplicate ids")
            if set(returned_ids) != set(expected_ids):
                raise RuntimeError(
                    f"Batch world scorer id mismatch: expected={expected_ids[:20]} returned={returned_ids[:20]}"
                )
            for item in returned:
                score_map[str(item["id"])] = (
                    float(item["support"]),
                    float(item["contradiction"]),
                    float(item["unresolved"]),
                )
    else:
        for item in prepared:
            nli = world_scorer.score(item["query_repr"], item["evidence_repr"])
            score_map[item["id"]] = (nli.support, nli.contradiction, nli.unresolved)

    by_query: dict[int, list[dict]] = {}
    for item in prepared:
        by_query.setdefault(item["q_index"], []).append(item)

    candidates: list[dict] = []
    dominant_paths: list[dict] = []
    all_scored_paths: list[dict] = []
    for q_index, query in enumerate(c1):
        items = by_query.get(q_index, [])
        if not items:
            continue
        choices: list[WorldChoice] = []
        path_meta: dict[str, dict] = {}
        for item in items:
            prefix = item["id"]
            path = item["path"]
            raw_support, raw_contradiction, raw_unresolved = score_map[prefix]
            support, contradiction, unresolved = _normalize_scores(
                raw_support, raw_contradiction, raw_unresolved
            )
            relations = tuple(x.predicate for x in path.literals)
            start = path.literals[0].subject
            end = path.literals[-1].object
            swap = path.direction == "REVERSE"
            support_h = PathRelationHypothesis(
                f"{prefix}-support", relations, query.predicate, support,
                negated_result=query.negated, origin=f"{scorer_name}-world-scorer",
                start=start, end=end, swap_endpoints=swap,
            )
            contradiction_h = PathRelationHypothesis(
                f"{prefix}-contradiction", relations, query.predicate, contradiction,
                negated_result=not query.negated, origin=f"{scorer_name}-world-scorer",
                start=start, end=end, swap_endpoints=swap,
            )
            choices.extend([
                WorldChoice(support_h, f"{prefix}:support", support),
                WorldChoice(contradiction_h, f"{prefix}:contradiction", contradiction),
                WorldChoice.unresolved(f"{prefix}:unresolved", unresolved),
            ])
            meta = {
                "id": prefix,
                "query": literal_text(query),
                "query_sentence_id": int(query.story or 0),
                "direction": path.direction,
                "sentence_ids": sorted({int(x.story) for x in path.literals if x.story is not None}),
                "raw_scores": {
                    "support": raw_support,
                    "contradiction": raw_contradiction,
                    "unresolved": raw_unresolved,
                },
                "scores": {"support": support, "contradiction": contradiction, "unresolved": unresolved},
                "path": item["evidence_repr"],
            }
            path_meta[prefix] = meta
            all_scored_paths.append(meta)
            if contradiction > max(support, unresolved):
                dominant_paths.append(meta)

        # Retain the previous possible-world calculation only for diagnostics.
        worlds = build_possible_worlds(c2, [choices], reasoner, {"context2": 1.0}, max_worlds=128)
        marginal = truth_marginal(worlds, query, reasoner)
        conflict_mass = marginal.contradiction + marginal.both
        candidates.append({
            "query": literal_text(query),
            "query_sentence_id": int(query.story or 0),
            "support_mass": marginal.support,
            "contradiction_mass": conflict_mass,
            "unresolved_mass": marginal.unresolved,
            "world_count": len(worlds),
            "max_path_contradiction": max((x["scores"]["contradiction"] for x in path_meta.values()), default=0.0),
            "paths": path_meta,
        })

    ranked = sorted(candidates, key=lambda x: x["max_path_contradiction"], reverse=True)
    best_dominant = max(dominant_paths, key=lambda x: x["scores"]["contradiction"], default=None)
    best_any = max(all_scored_paths, key=lambda x: x["scores"]["contradiction"], default=None)
    conflict = best_dominant is not None

    locations = []
    if best_dominant is not None:
        locations.append({"source": "context1", "sentence_id": best_dominant["query_sentence_id"]})
        locations.extend(
            {"source": "context2", "sentence_id": x}
            for x in best_dominant["sentence_ids"]
        )

    return {
        "conflict_detected": conflict,
        "locations": locations,
        "confidence": best_dominant["scores"]["contradiction"] if best_dominant else (
            best_any["scores"]["contradiction"] if best_any else 0.0
        ),
        "decision_rule": "existential_dominant_path_contradiction",
        "best_contradiction_path": best_dominant or best_any,
        "candidate_queries": len(c1),
        "evaluated_query_paths": len(prepared),
        "usage": usage,
        "world_scorer": scorer_name,
        "candidates": ranked[:10],
        "extracted_claims": claims,
    }


def run(args) -> dict:
    client = OpenAIResponsesClient(model=args.model)
    deberta = DebertaWorldScorer() if args.deberta else None
    cache_path = Path(args.cache)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict] = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                existing[row["key"]] = row

    output_rows: list[dict] = []
    processed = 0
    scorer_suffix = "deberta" if args.deberta else "llm"
    for filename in FILES:
        rows = download_json(f"{MAGIC_BASE}/{filename}")
        for row in rows:
            if args.limit and processed >= args.limit:
                break
            key = f"{filename}:{row.get('id')}:{args.model}:{scorer_suffix}:batch-v3"
            if key in existing:
                output_rows.append(existing[key])
                processed += 1
                continue
            direct = direct_magic_judgment(client, row["context1"], row["context2"])
            rashomon = build_rashomon_judgment(client, row["context1"], row["context2"], args.max_hops, deberta)
            record = {
                "key": key,
                "file": filename,
                "id": row.get("id"),
                "model": args.model,
                "direct": direct.data,
                "direct_usage": direct.usage.__dict__,
                "rashomon": rashomon,
                "gold": {
                    "original_triplet": row.get("original_triplet"),
                    "perturb_triplet": row.get("perturb_triplet"),
                },
            }
            with cache_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            output_rows.append(record)
            processed += 1
        if args.limit and processed >= args.limit:
            break

    direct_id = sum(bool(x["direct"]["conflict_detected"]) for x in output_rows) / len(output_rows) if output_rows else 0.0
    rashomon_id = sum(bool(x["rashomon"]["conflict_detected"]) for x in output_rows) / len(output_rows) if output_rows else 0.0
    summary = {
        "track": "MAGIC natural-language same-input conflict detection",
        "n": len(output_rows),
        "model": args.model,
        "world_scorer": scorer_suffix,
        "decision_rule": "existential_dominant_path_contradiction",
        "direct_conflict_recall": direct_id,
        "rashomon_worlds_conflict_recall": rashomon_id,
        "gain_pp": 100 * (rashomon_id - direct_id),
        "metric_warning": "All released files in this run are conflict cases, so detection is recall. LOC remains blind human-scored for peer comparison.",
        "generation_policy": "Neither direct nor candidate-path prediction receives original_triplet or perturb_triplet. Gold structured fields are attached only after prediction for scoring/audit.",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.4-mini-2026-03-17"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-hops", type=int, default=4)
    parser.add_argument("--deberta", action="store_true")
    parser.add_argument("--cache", default="results/magic_natural_language_predictions.jsonl")
    parser.add_argument("--out", default="results/magic_natural_language_summary.json")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
