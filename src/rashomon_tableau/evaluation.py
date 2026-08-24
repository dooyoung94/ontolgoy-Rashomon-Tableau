from __future__ import annotations

from collections import Counter, defaultdict

from .models import BenchmarkCase, Prediction
from .rashomon import rashomon_explanations
from .tableau import RelationalTableau


def classify_case(case: BenchmarkCase, reasoner: RelationalTableau) -> Prediction:
    a = reasoner.check(case.facts_a)
    b = reasoner.check(case.facts_b)
    union_facts = case.facts_a + case.facts_b
    u = reasoner.check(union_facts)

    if not a.satisfiable or not b.satisfiable:
        predicted, scope = "contradiction", "intra"
    elif not u.satisfiable:
        predicted, scope = "contradiction", "inter"
    elif {x.positive_key() for x in case.facts_a} != {x.positive_key() for x in case.facts_b}:
        predicted, scope = "divergence", None
    else:
        predicted, scope = "consistent", None

    explanations = rashomon_explanations(union_facts, reasoner) if not u.satisfiable else []
    return Prediction(case.case_id, case.label, predicted, case.subtype, case.story, case.perspective_a, case.perspective_b, a.satisfiable, b.satisfiable, u.satisfiable, len(explanations), {
        "scope": scope,
        "clashes": [{"kind": c.kind, "message": c.message, "rules": c.rules, "literals": [x.text() for x in c.literals]} for c in u.clashes],
        "rashomon_explanations": explanations,
    })


def classification_metrics(predictions: list[Prediction]) -> dict:
    labels = sorted({p.gold for p in predictions} | {p.predicted for p in predictions})
    total = len(predictions)
    correct = sum(p.gold == p.predicted for p in predictions)
    per_class = {}
    for label in labels:
        tp = sum(p.gold == label and p.predicted == label for p in predictions)
        fp = sum(p.gold != label and p.predicted == label for p in predictions)
        fn = sum(p.gold == label and p.predicted != label for p in predictions)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(p.gold == label for p in predictions)}
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(per_class) if per_class else 0.0
    by_subtype = defaultdict(list)
    for p in predictions:
        by_subtype[p.subtype].append(p)
    subtype_metrics = {subtype: {"n": len(items), "accuracy": sum(x.gold == x.predicted for x in items) / len(items), "gold": dict(Counter(x.gold for x in items)), "predicted": dict(Counter(x.predicted for x in items))} for subtype, items in by_subtype.items()}
    implicit = [p for p in predictions if p.subtype.startswith("implicit_")]
    return {"n": total, "accuracy": correct / total if total else 0.0, "macro_f1": macro_f1, "per_class": per_class, "by_subtype": subtype_metrics, "implicit_contradiction_recall": (sum(p.predicted == "contradiction" for p in implicit) / len(implicit) if implicit else None)}


def relation_extraction_metrics(gold_sets, pred_sets) -> dict:
    tp = fp = fn = 0
    for gold, pred in zip(gold_sets, pred_sets):
        tp += len(gold & pred); fp += len(pred - gold); fn += len(gold - pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
