from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from openrca_mr.masking import mask_relation_types
from openrca_mr.metrics import (
    exact_root_set,
    node_metrics,
    process_path_reachability,
    relation_classification_metrics,
    root_hit_at_k,
    service_edge_metrics,
)
from openrca_mr.models import REL_CAUSAL, REL_MASKED
from openrca_mr.openrca2 import load_normalized_cases


def _prompt(case) -> str:
    relations = []
    for e in case.known_edges:
        relations.append({"source": e.source, "relation": e.relation, "target": e.target})
    evidence = []
    for e in case.evidence:
        evidence.append({
            "node": e.node,
            "kind": e.kind,
            "signal": e.signal,
            "abnormality": round(e.abnormality, 4),
            "timestamp": e.timestamp,
            "text": e.text,
        })
    return f"""You are evaluating causal propagation in a microservice incident.
All source-target endpoint pairs were observed by telemetry collectors. Some relation labels are hidden as {REL_MASKED}.
For every masked pair, decide whether its incident-specific relation is causal_propagates_to or non_causal_dependency.
Then rank up to three likely root-cause services. Do not invent endpoint pairs that are not listed.

Observed relations:
{json.dumps(relations, ensure_ascii=False)}

Telemetry evidence:
{json.dumps(evidence, ensure_ascii=False)}

Observed symptom services:
{json.dumps(case.symptom_nodes, ensure_ascii=False)}

Return JSON only with exactly this schema:
{{"causal_pairs":[["source","target"]],"root_causes":["service"]}}
"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("LLM response did not contain a JSON object")
    return json.loads(text[start : end + 1])


def _mean(rows: list[dict], key: str):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def run(data: str, out: str, model: str, mask_ratio: float, seed: int, limit: int) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for the LLM baseline")
    from openai import OpenAI

    client = OpenAI()
    cases = load_normalized_cases(data)
    if limit:
        cases = cases[:limit]

    rows = []
    for case in cases:
        visible, masked_truth = mask_relation_types(case, mask_ratio, seed)
        response = client.responses.create(model=model, input=_prompt(visible))
        parsed = _parse_json(response.output_text)
        causal_pairs = parsed.get("causal_pairs") or []
        predicted = [(str(x[0]), REL_CAUSAL, str(x[1])) for x in causal_pairs if isinstance(x, list) and len(x) >= 2]
        # Preserve visible causal ontology facts in the final graph, exactly as
        # the symbolic pipeline does.
        predicted.extend(e.key() for e in visible.known_edges if e.relation == REL_CAUSAL)
        roots = [str(x) for x in (parsed.get("root_causes") or [])][:3]

        relation = relation_classification_metrics(predicted, masked_truth)
        edge = service_edge_metrics(predicted, case.gold_edges)
        node = node_metrics(predicted, case.gold_edges)
        rows.append({
            "case_id": case.case_id,
            "relation_accuracy": relation.accuracy,
            "relation_precision": relation.precision,
            "relation_recall": relation.recall,
            "relation_f1": relation.f1,
            "node_f1": node.f1,
            "edge_f1": edge.f1,
            "process_path_reachability": process_path_reachability(
                predicted, roots, case.gold_root_causes, case.gold_alarm_nodes or case.symptom_nodes
            ),
            "root_exact_set": exact_root_set(roots, case.gold_root_causes),
            "root_hit_at_1": root_hit_at_k(roots, case.gold_root_causes, 1),
            "root_hit_at_3": root_hit_at_k(roots, case.gold_root_causes, 3),
        })

    keys = [k for k in rows[0] if k != "case_id"] if rows else []
    result = {
        "baseline": "llm_relation_recovery",
        "model": model,
        "mask_mode": "relation",
        "mask_ratio": mask_ratio,
        "seed": seed,
        "n": len(rows),
        "summary": {k: _mean(rows, k) for k in keys},
        "rows": rows,
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.6"))
    p.add_argument("--mask-ratio", type=float, default=0.40)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    run(args.data, args.out, args.model, args.mask_ratio, args.seed, args.limit)


if __name__ == "__main__":
    main()
