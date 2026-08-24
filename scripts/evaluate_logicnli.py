from __future__ import annotations

import io
import json
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

URL = 'https://raw.githubusercontent.com/omnilabNLP/LogicNLI/main/dataset/LogicNLI_sim.zip'
OUT = Path('results/logicnli_metrics.json')

Atom = tuple[str, str, str]  # subject, predicate, sign


def atom(subject: str, predicate: str, sign: str) -> Atom:
    return (subject, predicate, sign)


def opposite(a: Atom) -> Atom:
    return (a[0], a[1], '-' if a[2] == '+' else '+')


def constants(instance: dict) -> list[str]:
    names = {v[0] for v in instance['facts'].values()}
    for rule in instance['rules'].values():
        for side in ('p', 'q'):
            for entry in rule[side]['fact']:
                if entry[0] not in {'all', 'exist'}:
                    names.add(entry[0])
    for st in instance['statements'].values():
        names.add(st[0])
    return sorted(names)


def local_expr_matches(expr: dict, state: set[Atom], person: str) -> bool:
    vals = []
    for subj, pred, sign in expr['fact']:
        if subj == 'all':
            vals.append(atom(person, pred, sign) in state)
        elif subj == 'exist':
            # handled by global_expr_matches
            return False
        else:
            vals.append(atom(subj, pred, sign) in state)
    conj = expr.get('conj', 'none')
    if not vals:
        return False
    return any(vals) if conj == 'or' else all(vals)


def global_expr_matches(expr: dict, state: set[Atom], people: list[str]) -> tuple[bool, list[str]]:
    entries = expr['fact']
    has_all = any(e[0] == 'all' for e in entries)
    has_exist = any(e[0] == 'exist' for e in entries)

    if has_exist:
        # LogicNLI existential templates express that at least one person satisfies
        # the local conjunction/disjunction of existential predicates.
        vals_by_person = []
        for p in people:
            vals = []
            for subj, pred, sign in entries:
                if subj == 'exist':
                    vals.append(atom(p, pred, sign) in state)
                elif subj == 'all':
                    vals.append(atom(p, pred, sign) in state)
                else:
                    vals.append(atom(subj, pred, sign) in state)
            ok = any(vals) if expr.get('conj') == 'or' else all(vals)
            vals_by_person.append((p, ok))
        matched = [p for p, ok in vals_by_person if ok]
        return bool(matched), matched

    if has_all:
        matched = [p for p in people if local_expr_matches(expr, state, p)]
        return bool(matched), matched

    vals = [atom(subj, pred, sign) in state for subj, pred, sign in entries]
    ok = any(vals) if expr.get('conj') == 'or' else all(vals)
    return ok, []


def derive_side(expr: dict, people: list[str], bound_people: list[str]) -> list[Atom] | None:
    # A disjunctive consequent does not license choosing either disjunct under
    # forward reasoning, so abstain from deriving it.
    if expr.get('conj') == 'or' and len(expr['fact']) > 1:
        return None
    out: list[Atom] = []
    entries = expr['fact']
    for subj, pred, sign in entries:
        if subj == 'all':
            targets = bound_people or people
            out.extend(atom(p, pred, sign) for p in targets)
        elif subj == 'exist':
            # Existential conclusions require a witness that the dataset does not
            # identify. We conservatively do not invent one.
            return None
        else:
            out.append(atom(subj, pred, sign))
    return out


def apply_direction(src: dict, dst: dict, state: set[Atom], people: list[str]) -> set[Atom]:
    ok, matched = global_expr_matches(src, state, people)
    if not ok:
        return set()
    derived = derive_side(dst, people, matched)
    return set(derived or [])


def closure(instance: dict) -> set[Atom]:
    state = {atom(v[0], v[1], v[2]) for v in instance['facts'].values()}
    people = constants(instance)
    changed = True
    rounds = 0
    while changed and rounds < 100:
        rounds += 1
        changed = False
        for rule in instance['rules'].values():
            additions = apply_direction(rule['p'], rule['q'], state, people)
            if rule['type'] == 'equ':
                additions |= apply_direction(rule['q'], rule['p'], state, people)
            new = additions - state
            if new:
                state |= new
                changed = True
    return state


def label_from_state(st: list, state: set[Atom], dual: bool) -> str:
    q = atom(st[0], st[1], st[2])
    nq = opposite(q)
    q_true = q in state
    nq_true = nq in state
    if dual and q_true and nq_true:
        return 'self_contradiction'
    # Single-path decision stops as soon as one support path for the statement is
    # found, which is the exact information loss the Paradox label is designed to expose.
    if q_true:
        return 'entailment'
    if nq_true:
        return 'contradiction'
    return 'neutral'


def direct_state(instance: dict) -> set[Atom]:
    return {atom(v[0], v[1], v[2]) for v in instance['facts'].values()}


def metrics(gold: list[str], pred: list[str]) -> dict:
    labels = ['entailment', 'contradiction', 'neutral', 'self_contradiction']
    per = {}
    for label in labels:
        tp = sum(g == label and p == label for g,p in zip(gold,pred))
        fp = sum(g != label and p == label for g,p in zip(gold,pred))
        fn = sum(g == label and p != label for g,p in zip(gold,pred))
        precision = tp/(tp+fp) if tp+fp else 0.0
        recall = tp/(tp+fn) if tp+fn else 0.0
        f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
        per[label] = {'precision':precision,'recall':recall,'f1':f1,'support':sum(g==label for g in gold)}
    return {
        'n': len(gold),
        'accuracy': sum(g==p for g,p in zip(gold,pred))/len(gold) if gold else 0.0,
        'macro_f1': sum(per[x]['f1'] for x in labels)/len(labels) if gold else 0.0,
        'per_class': per,
        'prediction_distribution': dict(Counter(pred)),
    }


def load_test() -> dict:
    with urllib.request.urlopen(URL, timeout=60) as r:
        raw = r.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        return json.loads(z.read('LogicNLI_sim/test_logic.json').decode('utf-8'))


def main():
    data = load_test()
    gold=[]; direct=[]; single=[]; dual=[]
    for instance in data.values():
        c = closure(instance)
        d = direct_state(instance)
        for key, st in instance['statements'].items():
            gold.append(instance['labels'][key])
            direct.append(label_from_state(st, d, dual=True))
            single.append(label_from_state(st, c, dual=False))
            dual.append(label_from_state(st, c, dual=True))

    m_direct = metrics(gold,direct)
    m_single = metrics(gold,single)
    m_dual = metrics(gold,dual)
    result = {
        'dataset':'LogicNLI_sim test_logic',
        'source':URL,
        'contexts':len(data),
        'statements':len(gold),
        'gold_distribution':dict(Counter(gold)),
        'direct_fact_dual_check':m_direct,
        'single_path_forward_reasoner':m_single,
        'dual_proof_rashomon_style_reasoner':m_dual,
        'gain_dual_vs_single_pp':{
            'accuracy':100*(m_dual['accuracy']-m_single['accuracy']),
            'macro_f1':100*(m_dual['macro_f1']-m_single['macro_f1']),
            'self_contradiction_f1':100*(m_dual['per_class']['self_contradiction']['f1']-m_single['per_class']['self_contradiction']['f1']),
        },
        'semantics_note':'LogicNLI defines Paradox/self_contradiction when both s and not-s are derivable. The dual-proof decision checks both proof directions instead of stopping after one supported path.',
        'implementation_note':'This evaluator implements LogicNLI structured forward semantics for implication/equivalence, conjunction/disjunction antecedents, universal-variable templates, named constants, and existential antecedents. Disjunctive or existential consequents are handled conservatively without inventing a witness/disjunct.'
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
