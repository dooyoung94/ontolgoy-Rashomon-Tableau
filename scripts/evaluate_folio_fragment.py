from __future__ import annotations

import itertools
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

from rashomon_tableau.clause_tableau import ClauseTableau, negate

FOLIO_URL = "https://raw.githubusercontent.com/Yale-LILY/FOLIO/main/data/v0.0/folio-validation.jsonl"
OUT = Path("results/folio_fragment_metrics.json")

Atom = tuple[str, tuple[str, ...], bool]  # predicate, args, negated
Rule = tuple[tuple[Atom, ...], tuple[Atom, ...], tuple[str, ...]]


def strip_outer(s: str) -> str:
    s = s.strip()
    changed = True
    while changed and s.startswith("(") and s.endswith(")"):
        depth = 0
        changed = False
        for i, ch in enumerate(s):
            if ch == "(": depth += 1
            elif ch == ")": depth -= 1
            if depth == 0 and i != len(s) - 1:
                break
        else:
            s = s[1:-1].strip(); changed = True
    return s


def split_top(s: str, op: str) -> list[str]:
    parts, start, depth = [], 0, 0
    for i, ch in enumerate(s):
        if ch == "(": depth += 1
        elif ch == ")": depth -= 1
        elif ch == op and depth == 0:
            parts.append(s[start:i].strip()); start = i + 1
    parts.append(s[start:].strip())
    return parts


def parse_atom(s: str) -> Atom | None:
    s = strip_outer(s.strip())
    neg = False
    if s.startswith("¬"):
        neg = True; s = strip_outer(s[1:].strip())
        if any(x in s for x in ["∧", "∨", "→", "↔", "⊕"]):
            return None
    m = re.match(r"^([^\s(]+)\s*\((.*)\)$", s)
    if not m:
        return None
    pred = m.group(1).strip()
    args = tuple(x.strip() for x in m.group(2).split(","))
    if not pred or not args or any(not a for a in args):
        return None
    return pred, args, neg


def remove_quantifiers(s: str) -> tuple[str, tuple[str, ...]]:
    s = s.strip(); vars_: list[str] = []
    while True:
        m = re.match(r"^∀\s*([A-Za-z][A-Za-z0-9_]*)\s*(.*)$", s)
        if not m: break
        vars_.append(m.group(1)); s = m.group(2).strip()
    return strip_outer(s), tuple(vars_)


def parse_formula(s: str):
    s, vars_ = remove_quantifiers(s)
    if any(op in s for op in ["∃", "∨", "⊕", "↔", "⟷", "⟺"]):
        return None
    parts = split_top(s, "→")
    if len(parts) > 2:
        return None
    if len(parts) == 2:
        lhs = [parse_atom(x) for x in split_top(strip_outer(parts[0]), "∧")]
        rhs = [parse_atom(x) for x in split_top(strip_outer(parts[1]), "∧")]
        if any(x is None for x in lhs + rhs):
            return None
        return ("rule", tuple(lhs), tuple(rhs), vars_)
    atoms = [parse_atom(x) for x in split_top(s, "∧")]
    if any(x is None for x in atoms):
        return None
    return ("facts", tuple(atoms), vars_)


def atom_key(atom: Atom, subst: dict[str, str] | None = None) -> str:
    pred, args, neg = atom
    subst = subst or {}
    grounded = tuple(subst.get(a, a) for a in args)
    core = f"{pred}({','.join(grounded)})"
    return f"~{core}" if neg else core


def constants_of(atom: Atom, variables: set[str]) -> set[str]:
    return {a for a in atom[1] if a not in variables}


def build_clauses(parsed_premises, query: Atom):
    facts: list[Atom] = []
    rules: list[Rule] = []
    constants: set[str] = set(query[1])
    for item in parsed_premises:
        if item[0] == "facts":
            atoms, vars_ = item[1], item[2]
            if vars_:
                return None
            facts.extend(atoms)
            for a in atoms: constants |= constants_of(a, set())
        else:
            _, lhs, rhs, vars_ = item
            rules.append((lhs, rhs, vars_))
            all_atoms = list(lhs) + list(rhs)
            for a in all_atoms: constants |= constants_of(a, set(vars_))
    if not constants:
        constants.add("_c0")

    clauses: list[frozenset[str]] = [frozenset([atom_key(a)]) for a in facts]
    for lhs, rhs, vars_ in rules:
        domains = [sorted(constants)] * len(vars_)
        for values in itertools.product(*domains) if vars_ else [()]:
            subst = dict(zip(vars_, values))
            for conclusion in rhs:
                clause = {negate(atom_key(a, subst)) for a in lhs}
                clause.add(atom_key(conclusion, subst))
                clauses.append(frozenset(clause))
    return clauses, facts


def direct_fact_predict(facts: list[Atom], query: Atom) -> str:
    q = atom_key(query); opp = negate(q)
    keys = {atom_key(x) for x in facts}
    if q in keys: return "True"
    if opp in keys: return "False"
    return "Unknown"


def forward_predict(parsed_premises, query: Atom) -> str:
    facts: set[str] = set()
    rules: list[Rule] = []
    constants: set[str] = set(query[1])
    for item in parsed_premises:
        if item[0] == "facts":
            atoms, vars_ = item[1], item[2]
            if vars_: return "Unknown"
            for a in atoms:
                facts.add(atom_key(a)); constants |= constants_of(a, set())
        else:
            _, lhs, rhs, vars_ = item
            rules.append((lhs, rhs, vars_))
            for a in list(lhs)+list(rhs): constants |= constants_of(a, set(vars_))
    changed = True
    while changed:
        changed = False
        for lhs, rhs, vars_ in rules:
            for values in itertools.product(sorted(constants), repeat=len(vars_)) if vars_ else [()]:
                subst = dict(zip(vars_, values))
                if all(atom_key(a, subst) in facts for a in lhs):
                    for c in rhs:
                        k = atom_key(c, subst)
                        if k not in facts:
                            facts.add(k); changed = True
    q = atom_key(query); opp = negate(q)
    if q in facts: return "True"
    if opp in facts: return "False"
    return "Unknown"


def metrics(gold: list[str], pred: list[str]) -> dict:
    labels = ["True", "False", "Unknown"]
    correct = sum(a == b for a, b in zip(gold, pred))
    per = {}
    for label in labels:
        tp = sum(g == label and p == label for g,p in zip(gold,pred))
        fp = sum(g != label and p == label for g,p in zip(gold,pred))
        fn = sum(g == label and p != label for g,p in zip(gold,pred))
        pr = tp/(tp+fp) if tp+fp else 0.0
        rc = tp/(tp+fn) if tp+fn else 0.0
        f1 = 2*pr*rc/(pr+rc) if pr+rc else 0.0
        per[label] = {"precision":pr,"recall":rc,"f1":f1,"support":sum(g==label for g in gold)}
    return {
        "n":len(gold),
        "accuracy":correct/len(gold) if gold else 0.0,
        "macro_f1":sum(v["f1"] for v in per.values())/3 if gold else 0.0,
        "per_class":per,
    }


def load_rows():
    with urllib.request.urlopen(FOLIO_URL, timeout=60) as r:
        return [json.loads(line) for line in r.read().decode("utf-8").splitlines() if line.strip()]


def main():
    rows = load_rows()
    supported = []
    unsupported = []
    for idx,row in enumerate(rows):
        parsed = [parse_formula(x) for x in row["premises-FOL"]]
        query_parsed = parse_formula(row["conclusion-FOL"])
        query = None
        if query_parsed and query_parsed[0] == "facts" and not query_parsed[2] and len(query_parsed[1]) == 1:
            query = query_parsed[1][0]
        if query is None or any(x is None for x in parsed):
            unsupported.append(idx); continue
        built = build_clauses(parsed, query)
        if built is None:
            unsupported.append(idx); continue
        supported.append((idx,row,parsed,query,built))

    tableau = ClauseTableau()
    gold=[]; direct=[]; forward=[]; semantic=[]
    for idx,row,parsed,query,(clauses,facts) in supported:
        g = "Unknown" if row["label"] == "Uncertain" else row["label"]
        gold.append(g)
        direct.append(direct_fact_predict(facts,query))
        forward.append(forward_predict(parsed,query))
        semantic.append(tableau.classify(clauses, atom_key(query)))

    # Conservative full-set score: unsupported examples abstain as Unknown.
    full_gold=[]; full_sem=[]
    supported_map={idx:pred for (idx,*_),pred in zip(supported,semantic)}
    for idx,row in enumerate(rows):
        g = "Unknown" if row["label"] == "Uncertain" else row["label"]
        full_gold.append(g); full_sem.append(supported_map.get(idx,"Unknown"))

    result = {
        "dataset":"FOLIO v0.0 validation",
        "source":FOLIO_URL,
        "total_examples":len(rows),
        "supported_fragment_examples":len(supported),
        "coverage":len(supported)/len(rows) if rows else 0.0,
        "supported_definition":"Ground facts/conjunctions plus universal Horn implications with explicit negation; single ground-literal query; no existential, disjunction, XOR or biconditional.",
        "label_distribution_supported":dict(Counter(gold)),
        "direct_fact_baseline":metrics(gold,direct),
        "forward_horn_baseline":metrics(gold,forward),
        "semantic_clause_tableau":metrics(gold,semantic),
        "rashomon_tableau_logical_core":metrics(gold,semantic),
        "full_validation_conservative":metrics(full_gold,full_sem),
        "interpretation":"On a single-context dataset, perspective indexing and Rashomon selection do not change the class label; this experiment validates the logical core. Multi-context gains are measured in the separate scope ablation.",
        "unsupported_example_indices":unsupported,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__ == "__main__":
    # Explicit branch marker: this code path is identical to main and exists only
    # to trigger the reproducible pull-request benchmark workflow.
    main()
