from __future__ import annotations

from dataclasses import dataclass


SignedAtom = str
Clause = frozenset[SignedAtom]


def negate(literal: SignedAtom) -> SignedAtom:
    return literal[1:] if literal.startswith("~") else f"~{literal}"


@dataclass(frozen=True)
class HornRule:
    antecedents: tuple[SignedAtom, ...]
    conclusion: SignedAtom


def rules_to_clauses(facts: list[SignedAtom], rules: list[HornRule]) -> list[Clause]:
    clauses: list[Clause] = [frozenset([fact]) for fact in facts]
    for rule in rules:
        clause = {negate(x) for x in rule.antecedents}
        clause.add(rule.conclusion)
        clauses.append(frozenset(clause))
    return clauses


class ClauseTableau:
    """Small semantic-tableau/DPLL backend for ground clauses.

    A branch is closed when it contains complementary literals.  The implementation
    performs unit propagation and branches on an unresolved literal.  It is used for
    the external logical benchmarks so that the benchmark is not merely the
    forward-closure checker used by the original CONAN PoC.
    """

    def satisfiable(self, clauses: list[Clause], assumptions: list[SignedAtom] | None = None) -> bool:
        work = list(clauses)
        for lit in assumptions or []:
            work.append(frozenset([lit]))
        return self._dpll(work, {})

    def entails(self, clauses: list[Clause], query: SignedAtom) -> bool:
        return not self.satisfiable(clauses, [negate(query)])

    def classify(self, clauses: list[Clause], query: SignedAtom) -> str:
        if self.entails(clauses, query):
            return "True"
        if self.entails(clauses, negate(query)):
            return "False"
        return "Unknown"

    def _dpll(self, clauses: list[Clause], assignment: dict[str, bool]) -> bool:
        simplified = self._simplify(clauses, assignment)
        if simplified is None:
            return False
        if not simplified:
            return True

        while True:
            units = [next(iter(c)) for c in simplified if len(c) == 1]
            if not units:
                break
            changed = False
            for lit in units:
                atom = lit[1:] if lit.startswith("~") else lit
                value = not lit.startswith("~")
                if atom in assignment and assignment[atom] != value:
                    return False
                if atom not in assignment:
                    assignment = dict(assignment)
                    assignment[atom] = value
                    changed = True
            if not changed:
                break
            simplified = self._simplify(simplified, assignment)
            if simplified is None:
                return False
            if not simplified:
                return True

        clause = min(simplified, key=len)
        lit = next(iter(clause))
        atom = lit[1:] if lit.startswith("~") else lit
        preferred = not lit.startswith("~")
        for value in (preferred, not preferred):
            branch = dict(assignment)
            branch[atom] = value
            if self._dpll(simplified, branch):
                return True
        return False

    @staticmethod
    def _simplify(clauses: list[Clause], assignment: dict[str, bool]) -> list[Clause] | None:
        result: list[Clause] = []
        for clause in clauses:
            satisfied = False
            remaining: set[str] = set()
            for lit in clause:
                atom = lit[1:] if lit.startswith("~") else lit
                positive = not lit.startswith("~")
                if atom not in assignment:
                    remaining.add(lit)
                elif assignment[atom] == positive:
                    satisfied = True
                    break
            if satisfied:
                continue
            if not remaining:
                return None
            result.append(frozenset(remaining))
        return result
