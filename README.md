# Rashomon Worlds

## Provenance-Aware Possible-World Reasoning for Multi-Hop Conflict and Truth Adjudication

> **Research thesis**  
> When multi-hop evidence is conflicting and relation semantics are incomplete, committing early to a single interpretation loses viable explanations. This project preserves mutually incompatible but internally consistent interpretations as weighted possible worlds, verifies each world logically, and adjudicates truth by marginalizing source, relation, evidence, and proof reliability across worlds.

---

## What is new in this research direction?

This repository previously focused on an **Ontology-Guided Bidirectional Tableau**. That work is now treated as a **prior baseline**, not the final research claim.

The new core object is a **PossibleWorld**:

```text
Conflicting Provenanced Claims
            ↓
    Multi-hop Derivations
            ↓
 Uncertain Relation Semantics
            ↓
   Candidate Interpretations
            ↓
┌───────────┼───────────┐
▼           ▼           ▼
World 1   World 2    World K
 SAT        SAT         SAT
│           │           │
└────── Tableau ────────┘
            ↓
 Reliability-Weighted World Adjudication
            ↓
 P(q) / P(¬q) / P(unresolved)
```

A world contains:

```text
W = {claims, sources, relation interpretations, derivations/proofs}
```

and is retained only when:

```text
Tableau(W) = SAT
```

Relation composition is **not forced into the hard ontology**. A composition may instead be represented as a defeasible `RelationHypothesis` and can differ across worlds.

---

# Central Research Question

> **Does preserving multiple internally consistent worlds and ranking them with provenance-aware reliability improve multi-hop conflict localization and truth adjudication compared with early single-world commitment?**

### H1 — World construction
Adaptive relation interpretations should recover valid multi-hop explanations that a static ontology leaves unresolved.

### H2 — Delayed commitment
Multiple consistent worlds should reduce false early decisions compared with selecting one relation interpretation or one proof path immediately.

### H3 — World-level truth adjudication
Combining source reliability, relation reliability, evidence support, and proof consistency at the world level should improve gold truth recovery over majority vote, source-only reliability, or single-proof scoring.

---

# Core Implementation

New module:

```text
src/rashomon_tableau/possible_worlds.py
```

Main abstractions:

- `RelationHypothesis`: defeasible two-hop relation interpretation; not a hard ontology axiom.
- `WorldChoice`: one candidate semantic choice for an uncertainty slot, including an explicit unresolved choice.
- `PossibleWorld`: claims + derived claims + semantic choices + provenance reliability.
- `build_possible_worlds(...)`: enumerates candidate worlds and prunes Tableau-inconsistent worlds.
- `truth_marginal(...)`: computes probability mass over `SUPPORTED / CONTRADICTED / BOTH / UNRESOLVED` across weighted worlds.

Current baseline world weighting is intentionally simple and ablatable:

```text
world_weight ∝ relation_support × source_support
```

The scoring function is a research variable, not a fixed theorem.

---

# Dataset Roles

## MAGIC — Multi-hop conflict / localization

**Purpose in the new paper:**

> Can the method construct and rank the correct conflicting worlds and localize the evidence responsible for the conflict?

Planned primary metrics:

- official MAGIC **ID**
- official MAGIC **LOC**
- world coverage
- gold-world recall
- relation-interpretation accuracy
- proof/provenance localization

### Published MAGIC peer reference

Weighted from the published N=1..4 multi-hop tables using the official subset counts:

| Peer | ID | LOC |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | **78.40%** | **47.28%** |
| **5-model mean** | **54.34%** | **29.25%** |

These peers read natural-language contexts. The new Possible-World track must therefore either reproduce the same input protocol or be reported as a separate structured track.

## DAFNA-EA Books — Truth adjudication

**Purpose in the new paper:**

> Once competing worlds exist, does world-level reliability recover the gold truth better than truth-discovery baselines?

Existing same-protocol prior baseline:

| Prior method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| Previous Rashomon atomic resolution | **61.00%** | **82.88%** |
| TruthFinder | 57.00% | 66.85% |
| AccuSim | 57.00% | 66.18% |
| 2-Estimates | 54.00% | 65.28% |
| 3-Estimates | 53.00% | 65.45% |
| Accu | 53.00% | 65.45% |

**Important:** 61.00% is a previous-method result. It is not claimed as a Possible-World result until the new evaluator is run.

## LogicNLI / FOLIO

These are retained only as **reasoning-engine sanity checks**, not headline peer benchmarks for the new research claim.

---

# Why the old approach became insufficient

Prior measured MAGIC structured results were:

| Prior component | Multi-hop |
|---|---:|
| direct heuristic detection | 33.16% |
| bidirectional candidate-path coverage | 68.03% |
| strict ontology-verified contradiction | 5.44% |

Interpretation:

- path discovery was not the main bottleneck;
- static relation semantics could not justify most discovered paths;
- forcing every ambiguous relation path into one hard ontology produces too many `UNRESOLVED` cases;
- therefore uncertain relation interpretation is now modeled as a **world variable** rather than immediately promoted to an ontology axiom.

These numbers are **prior baseline diagnostics**, not the new method's result.

---

# Experimental Comparison Required for the New Paper

The main ablation should be one coherent progression:

| Variant | Relation semantics | Worlds | Reliability | MAGIC ID/LOC | DAFNA Truth |
|---|---|---|---|---|---|
| B0 Direct | direct only | single | none | measure | measure |
| B1 Static Tableau | hard ontology | single | none | measure | measure |
| B2 Adaptive relation | hard + defeasible candidates | single | relation | measure | measure |
| B3 Possible worlds | hard + defeasible candidates | **multiple** | uniform | measure | measure |
| **B4 Rashomon Worlds** | hard + defeasible candidates | **multiple** | **source + relation + proof** | **target** | **target** |

The paper's strongest empirical claim is valid only if **B4 improves over B1–B3 on the same data and protocol**.

---

# Research Boundary

This work does **not** claim that:

- possible-world semantics is new;
- Tableau reasoning is new;
- rule mining is new;
- knowledge graphs are new;
- source reliability is new.

The intended contribution is their focused combination for this specific problem:

> **source-provenanced conflicting multi-hop claims + uncertain relation interpretations + Tableau-consistent worlds + reliability-weighted truth marginalization.**

Any rule miner, external ontology, embedding model, or LLM is a candidate-generator implementation detail unless an experiment specifically studies it.

---

# Repository Structure

```text
README.md                 # new research overview
RESEARCH_PAPER.md         # manuscript aligned to possible-world thesis
BENCHMARK_PROTOCOL.md     # fair dataset / metric / peer comparison protocol

src/rashomon_tableau/
├── possible_worlds.py    # NEW research core
├── tableau.py            # logical world verifier
├── ontology.py           # hard semantics / prior reasoning support
├── graph_paths.py        # candidate derivation support
└── ...                   # prior baselines and utilities

tests/
├── test_possible_worlds.py
└── test_reasoner.py

results/                  # measured results; prior results remain traceable
```

---

# Status

- Possible-world core: **implemented**
- uncertain relation hypotheses: **implemented**
- Tableau consistency pruning: **implemented**
- source/relation weighted world normalization: **implemented baseline**
- truth marginal over worlds: **implemented**
- MAGIC official ID/LOC for the new method: **not measured yet**
- DAFNA new possible-world evaluator: **not measured yet**

No projected performance number is reported as a measured result.
