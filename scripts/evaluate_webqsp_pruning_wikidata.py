from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from rashomon_tableau.deberta_world_scorer import DebertaWorldScorer


USER_AGENT = "BADP-WebQSP-Pilot/0.1 (research; GitHub Actions)"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"


@dataclass(frozen=True)
class Edge:
    head: str
    relation: str
    tail: str
    head_label: str
    relation_label: str
    tail_label: str


PathT = tuple[Edge, ...]
EdgeKey = tuple[str, str, str]


@dataclass
class PolicyState:
    name: str
    family: str
    kind: str
    value: float
    boundary_k: int | None = None
    max_width: int = 10
    active: list[PathT] = field(default_factory=list)
    selected_paths: list[PathT] = field(default_factory=list)
    expanded: int = 0
    selected: int = 0
    steps: int = 0
    answer_regret: bool = False
    answer_regret_events: int = 0
    answer_hits: set[str] = field(default_factory=set)
    top_scored_path: PathT | None = None
    top_scored_value: float = -1.0


def norm(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_set(text: str) -> set[str]:
    return {x for x in norm(text).split() if len(x) >= 2}


def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0


def chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class WikidataClient:
    def __init__(self, sleep_seconds: float = 0.15, retries: int = 4):
        self.sleep_seconds = sleep_seconds
        self.retries = retries
        self.entities: dict[str, dict] = {}
        self.labels: dict[str, str] = {}
        self.http_calls = 0

    def _get(self, params: dict[str, str]) -> dict:
        url = WIKIDATA_API + "?" + urllib.parse.urlencode(params)
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self.http_calls += 1
                    data = json.loads(resp.read().decode("utf-8"))
                time.sleep(self.sleep_seconds)
                return data
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep((attempt + 1) * 1.0)
        raise RuntimeError(f"Wikidata request failed after retries: {last_exc}")

    def ensure_entities(self, ids: set[str]) -> None:
        missing = sorted(x for x in ids if x and x not in self.entities)
        for batch in chunks(missing, 40):
            data = self._get(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "labels|claims",
                    "languages": "en",
                    "format": "json",
                }
            )
            for entity_id, obj in data.get("entities", {}).items():
                self.entities[entity_id] = obj
                label = obj.get("labels", {}).get("en", {}).get("value")
                if label:
                    self.labels[entity_id] = label

    def ensure_labels(self, ids: set[str]) -> None:
        missing = sorted(x for x in ids if x and x not in self.labels)
        for batch in chunks(missing, 50):
            data = self._get(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "labels",
                    "languages": "en",
                    "format": "json",
                }
            )
            for entity_id, obj in data.get("entities", {}).items():
                label = obj.get("labels", {}).get("en", {}).get("value")
                self.labels[entity_id] = label or entity_id

    def outgoing_edges(self, qids: set[str], question: str, max_edges_per_node: int) -> dict[str, list[Edge]]:
        self.ensure_entities(qids)
        raw_by_head: dict[str, list[tuple[str, str]]] = {}
        property_ids: set[str] = set()
        tail_ids: set[str] = set()

        for qid in sorted(qids):
            obj = self.entities.get(qid, {})
            raw: list[tuple[str, str]] = []
            for pid, statements in sorted(obj.get("claims", {}).items()):
                for statement in statements:
                    snak = statement.get("mainsnak", {})
                    if snak.get("snaktype") != "value":
                        continue
                    value = snak.get("datavalue", {}).get("value")
                    if not isinstance(value, dict):
                        continue
                    target = value.get("id")
                    if not isinstance(target, str) or not target.startswith("Q"):
                        continue
                    if target == qid:
                        continue
                    raw.append((pid, target))
                    property_ids.add(pid)
                    tail_ids.add(target)
            raw_by_head[qid] = raw

        self.ensure_labels(property_ids | tail_ids | qids)
        qtokens = token_set(question)
        out: dict[str, list[Edge]] = {}
        for qid, raw in raw_by_head.items():
            scored: list[tuple[float, str, str, Edge]] = []
            for pid, tail in raw:
                relation_label = self.labels.get(pid, pid)
                tail_label = self.labels.get(tail, tail)
                head_label = self.labels.get(qid, qid)
                text_tokens = token_set(relation_label + " " + tail_label)
                lexical = len(qtokens & text_tokens) / max(1, len(qtokens))
                edge = Edge(qid, pid, tail, head_label, relation_label, tail_label)
                scored.append((-lexical, pid, tail, edge))
            scored.sort(key=lambda x: (x[0], x[1], x[2]))
            out[qid] = [x[3] for x in scored[:max_edges_per_node]]
        return out


def path_key(path: PathT) -> tuple[EdgeKey, ...]:
    return tuple((e.head, e.relation, e.tail) for e in path)


def path_nodes(path: PathT) -> set[str]:
    nodes: set[str] = set()
    for edge in path:
        nodes.add(edge.head)
        nodes.add(edge.tail)
    return nodes


def evidence_text(edge: Edge) -> str:
    return f"{edge.head_label} -- {edge.relation_label} --> {edge.tail_label}."


def path_score(path: PathT, edge_scores: dict[EdgeKey, float]) -> float:
    if not path:
        return 0.0
    vals = [edge_scores[(e.head, e.relation, e.tail)] for e in path]
    return sum(vals) / len(vals)


def score_new_edges(
    scorer: DebertaWorldScorer,
    question: str,
    paths: list[PathT],
    edge_scores: dict[EdgeKey, float],
    batch_size: int,
) -> int:
    missing: dict[EdgeKey, Edge] = {}
    for path in paths:
        if not path:
            continue
        edge = path[-1]
        key = (edge.head, edge.relation, edge.tail)
        if key not in edge_scores:
            missing[key] = edge
    if not missing:
        return 0
    edges = [missing[k] for k in sorted(missing)]
    scores = scorer.score_many(
        [question] * len(edges),
        [[evidence_text(edge)] for edge in edges],
        batch_size=max(1, batch_size),
    )
    for edge, score in zip(edges, scores):
        edge_scores[(edge.head, edge.relation, edge.tail)] = score.support
    return len(edges)


def policy_templates() -> dict[str, PolicyState]:
    return {
        "top3": PolicyState("top3", "fixed", "topk", 3, max_width=3),
        "top5": PolicyState("top5", "fixed", "topk", 5, max_width=5),
        "global_0.05": PolicyState("global_0.05", "global", "global", 0.05),
        "global_0.10": PolicyState("global_0.10", "global", "global", 0.10),
        "relative_0.25": PolicyState("relative_0.25", "relative", "relative", 0.25),
        "relative_0.50": PolicyState("relative_0.50", "relative", "relative", 0.50),
        "badp_top3_0.005": PolicyState("badp_top3_0.005", "badp_top3", "boundary", 0.005, boundary_k=3),
        "badp_top3_0.010": PolicyState("badp_top3_0.010", "badp_top3", "boundary", 0.010, boundary_k=3),
        "badp_top5_0.010": PolicyState("badp_top5_0.010", "badp_top5", "boundary", 0.010, boundary_k=5),
        "badp_top5_0.050": PolicyState("badp_top5_0.050", "badp_top5", "boundary", 0.050, boundary_k=5),
    }


def select(paths: list[PathT], state: PolicyState, scores: dict[EdgeKey, float]) -> list[PathT]:
    ranked = sorted(paths, key=lambda p: (-path_score(p, scores), path_key(p)))
    if not ranked:
        return []
    if state.kind == "topk":
        return ranked[: int(state.value)]
    if state.kind == "global":
        threshold = path_score(ranked[0], scores) - state.value
    elif state.kind == "relative":
        best = path_score(ranked[0], scores)
        threshold = 1.0 - (1.0 + state.value) * (1.0 - best)
    elif state.kind == "boundary":
        k = int(state.boundary_k or 1)
        if len(ranked) <= k:
            return ranked
        threshold = path_score(ranked[k - 1], scores) - state.value
    else:
        raise ValueError(state.kind)
    return [p for p in ranked if path_score(p, scores) >= threshold][: state.max_width]


def answer_names(row: dict) -> list[str]:
    names: set[str] = set()
    for parse in row.get("Parses", []):
        if parse.get("AnnotatorComment", {}).get("ParseQuality") not in (None, "Complete"):
            continue
        for answer in parse.get("Answers", []):
            if answer.get("AnswerType") == "Entity" and answer.get("EntityName"):
                names.add(str(answer["EntityName"]))
    return sorted(names)


def inferential_hops(row: dict) -> int | None:
    hops = [len(p.get("InferentialChain", [])) for p in row.get("Parses", []) if p.get("InferentialChain")]
    return min(hops) if hops else None


def choose_rows(rows: list[dict], limit: int, max_gold_answers: int, max_hops: int) -> list[dict]:
    selected = []
    for row in rows:
        qids = sorted(row.get("qid_topic_entity", {}).keys())
        gold = answer_names(row)
        hop = inferential_hops(row)
        if not qids or not gold or hop is None or hop > max_hops or len(gold) > max_gold_answers:
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def summarize_policy(records: list[dict], name: str) -> dict:
    rows = [r["policies"][name] for r in records]
    if not rows:
        return {}
    return {
        "n": len(rows),
        "search_success": mean(float(x["search_success"]) for x in rows),
        "answer_hit_at_1": mean(float(x["hit_at_1"]) for x in rows),
        "macro_retrieval_f1": mean(float(x["answer_f1"]) for x in rows),
        "macro_answer_recall": mean(float(x["answer_recall"]) for x in rows),
        "answer_pruning_regret_rate": mean(float(x["answer_pruning_regret"]) for x in rows),
        "avg_active_width": mean(float(x["avg_active_width"]) for x in rows),
        "avg_expanded_candidates": mean(float(x["expanded_candidates"]) for x in rows),
        "avg_selected_candidates": mean(float(x["selected_candidates"]) for x in rows),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--webqsp", required=True)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--max-hops", type=int, default=2)
    ap.add_argument("--max-edges-per-node", type=int, default=30)
    ap.add_argument("--max-gold-answers", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--output", default="results/webqsp_wikidata_pruning_pilot.json")
    args = ap.parse_args()

    raw_rows = json.loads(Path(args.webqsp).read_text(encoding="utf-8"))
    rows = choose_rows(raw_rows, args.limit, args.max_gold_answers, args.max_hops)
    scorer = DebertaWorldScorer(device=args.device)
    client = WikidataClient()
    records: list[dict] = []
    total_nli = 0

    for idx, row in enumerate(rows):
        question = str(row.get("RawQuestion") or row.get("ProcessedQuestion") or "").strip()
        starts = sorted(row.get("qid_topic_entity", {}).keys())
        gold_names = answer_names(row)
        gold_norm = {norm(x) for x in gold_names}
        states = policy_templates()
        for state in states.values():
            state.active = []
        edge_scores: dict[EdgeKey, float] = {}

        # Virtual root: one empty path per topic entity is represented by a one-edge expansion at depth 1.
        frontier_starts = set(starts)
        initial_edges = client.outgoing_edges(frontier_starts, question, args.max_edges_per_node)
        first_paths: list[PathT] = []
        for start in starts:
            for edge in initial_edges.get(start, []):
                first_paths.append((edge,))
        first_paths = sorted({path_key(p): p for p in first_paths}.values(), key=path_key)
        total_nli += score_new_edges(scorer, question, first_paths, edge_scores, args.batch_size)

        for state in states.values():
            state.active = select(first_paths, state, edge_scores)
            state.expanded += len(first_paths)
            state.selected += len(state.active)
            state.steps += 1
            state.selected_paths.extend(state.active)
            pre_answer = any(norm(p[-1].tail_label) in gold_norm for p in first_paths)
            post_answer = any(norm(p[-1].tail_label) in gold_norm for p in state.active)
            if pre_answer and not post_answer:
                state.answer_regret = True
                state.answer_regret_events += 1
            for p in state.active:
                if norm(p[-1].tail_label) in gold_norm:
                    state.answer_hits.add(norm(p[-1].tail_label))
                s = path_score(p, edge_scores)
                if s > state.top_scored_value:
                    state.top_scored_value = s
                    state.top_scored_path = p

        for depth in range(2, args.max_hops + 1):
            endpoint_qids: set[str] = set()
            for state in states.values():
                endpoint_qids.update(p[-1].tail for p in state.active if p)
            if not endpoint_qids:
                break
            edges_by_head = client.outgoing_edges(endpoint_qids, question, args.max_edges_per_node)

            candidate_sets: dict[str, list[PathT]] = {}
            union: dict[tuple[EdgeKey, ...], PathT] = {}
            for name, state in states.items():
                candidates: list[PathT] = []
                for path in state.active:
                    seen = path_nodes(path)
                    for edge in edges_by_head.get(path[-1].tail, []):
                        if edge.tail in seen:
                            continue
                        np = (*path, edge)
                        candidates.append(np)
                        union[path_key(np)] = np
                candidate_sets[name] = sorted({path_key(p): p for p in candidates}.values(), key=path_key)

            if not union:
                break
            total_nli += score_new_edges(scorer, question, list(union.values()), edge_scores, args.batch_size)

            for name, state in states.items():
                candidates = candidate_sets[name]
                chosen = select(candidates, state, edge_scores)
                state.expanded += len(candidates)
                state.selected += len(chosen)
                state.steps += 1
                state.active = chosen
                state.selected_paths.extend(chosen)
                pre_answer = any(norm(p[-1].tail_label) in gold_norm for p in candidates)
                post_answer = any(norm(p[-1].tail_label) in gold_norm for p in chosen)
                if pre_answer and not post_answer:
                    state.answer_regret = True
                    state.answer_regret_events += 1
                for p in chosen:
                    if norm(p[-1].tail_label) in gold_norm:
                        state.answer_hits.add(norm(p[-1].tail_label))
                    s = path_score(p, edge_scores)
                    if s > state.top_scored_value:
                        state.top_scored_value = s
                        state.top_scored_path = p

        rec = {
            "question_id": row.get("QuestionId"),
            "question": question,
            "topic_qids": starts,
            "gold_answers": gold_names,
            "reference_hops": inferential_hops(row),
            "policies": {},
        }
        for name, state in states.items():
            retained_names = sorted({norm(p[-1].tail_label) for p in state.selected_paths if p})
            matched = set(retained_names) & gold_norm
            precision = len(matched) / len(retained_names) if retained_names else 0.0
            recall = len(matched) / len(gold_norm) if gold_norm else 0.0
            top1 = norm(state.top_scored_path[-1].tail_label) if state.top_scored_path else ""
            rec["policies"][name] = {
                "search_success": bool(state.answer_hits),
                "hit_at_1": bool(top1 and top1 in gold_norm),
                "top1_answer": state.top_scored_path[-1].tail_label if state.top_scored_path else None,
                "predicted_answers": sorted(matched),
                "retained_endpoint_count": len(retained_names),
                "answer_precision": precision,
                "answer_recall": recall,
                "answer_f1": f1(precision, recall),
                "answer_pruning_regret": state.answer_regret,
                "answer_pruning_regret_events": state.answer_regret_events,
                "avg_active_width": state.selected / state.steps if state.steps else 0.0,
                "expanded_candidates": state.expanded,
                "selected_candidates": state.selected,
            }
        records.append(rec)
        print(f"completed {idx + 1}/{len(rows)} {row.get('QuestionId')} wikidata_http={client.http_calls} nli={total_nli}")

    summary = {name: summarize_policy(records, name) for name in policy_templates()}
    output = {
        "protocol": {
            "dataset": "WebQSP official ToG data file",
            "kg": "Wikidata live entity statements via qid_topic_entity",
            "n": len(records),
            "max_hops": args.max_hops,
            "max_edges_per_node": args.max_edges_per_node,
            "candidate_prefilter": "common deterministic lexical-overlap prefilter before all pruning policies",
            "scorer": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli; edge entailment support; path score=mean edge support",
            "comparison_scope": "in-framework pruning-policy pilot on WebQSP questions; not a reproduction of published ToG/PoG end-to-end numbers",
            "answer_matching": "case/punctuation-normalized Wikidata entity label vs WebQSP gold EntityName",
            "pruning_regret": "answer-level regret: a gold answer endpoint existed before pruning at a depth but none survived the pruning operator",
            "limitations": [
                "Wikidata is used instead of the Freebase setup used by several peers.",
                "Only outgoing entity-valued Wikidata statements are explored.",
                "A common lexical prefilter caps candidate edges per node.",
                "No LLM final answer generator is used; metrics are retrieval/search metrics.",
            ],
        },
        "summary": summary,
        "diagnostics": {
            "wikidata_http_calls": client.http_calls,
            "unique_edge_nli_scores": total_nli,
        },
        "records": records,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(out)


if __name__ == "__main__":
    main()
