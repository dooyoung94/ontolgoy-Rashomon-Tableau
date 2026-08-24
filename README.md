# Rashomon Worlds

## Provenance-Aware Possible-World Reasoning for Multi-Hop Conflict and Truth Adjudication

> **Research thesis:** When multi-hop evidence conflicts and relation semantics are incomplete, committing early to one interpretation can discard viable explanations. Rashomon Worlds preserves incompatible but internally consistent interpretations as possible worlds, verifies each world logically, and then adjudicates truth across worlds using provenance-aware reliability.

## Core model

```text
Conflicting Provenanced Claims
            ↓
     Multi-hop Candidates
            ↓
 Uncertain Relation Semantics
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

A world is represented as:

```text
W = {claims, sources, relation interpretations, derivations/proofs}
```

and is retained only when `Tableau(W) = SAT`. Relation composition is not automatically promoted to a hard ontology axiom; uncertain compositions are represented as defeasible `RelationHypothesis` / `PathRelationHypothesis` choices that may differ between worlds.

## Central research question

> **Does preserving multiple internally consistent worlds, then ranking them with provenance-aware reliability, improve multi-hop conflict localization and truth adjudication compared with early single-world commitment?**

- **H1 — World construction:** uncertain relation interpretations recover valid multi-hop explanations that static ontology rules leave unresolved.
- **H2 — Delayed commitment:** retaining multiple consistent worlds avoids losing viable conflict explanations through early commitment.
- **H3 — World adjudication:** source + relation + proof reliability can select the correct world/truth better than majority, source-only, or single-proof scoring.

---

# First measured experiment — MAGIC multi-hop structured track

Validated on all released MAGIC multi-hop conflict rows:

- **588 rows**
- **1,056 query-level conflicts**
- workflow run: **32725453943**
- artifact: **9519356207**

Important protocol boundary: these released files are conflict cases, so the structured conflict numbers below are **recall**, not full MAGIC ID accuracy. `structured exact LOC` is our strict provenance diagnostic: every `original_triplet[i]` must be matched to a conflicting retained path covering its paired `perturb_triplet[i]`. It is **not** the published natural-language MAGIC LOC metric.

| Variant | Row conflict recall | Query conflict recall | Gold-world query recall | Structured row exact LOC |
|---|---:|---:|---:|---:|
| **B1 Static Tableau** | **5.44%** | 4.45% | — | — |
| **B2 Early-commit single world** | **29.93%** | 22.63% | — | — |
| **B3 Possible-world retention** | — | — | **39.39%** | **29.42%** |
| **B4 Weighted possible worlds** | **22.79%** | 16.86% | — | **7.14%** |

Additional complexity measurements:

- mean candidate paths per query: **1.46**
- mean retained worlds per query: **4.10**
- mean retained worlds per row: **7.36**

Measured summary: [`results/magic_possible_worlds_summary.json`](./results/magic_possible_worlds_summary.json)

### What the result actually says

The result is **not** “multiverse automatically beats everything.” It separates two problems that the previous design mixed together:

1. **World generation works better than static proof closure.** B3 can preserve an exact paired gold conflict explanation for **39.39% of query conflicts**, while static Tableau directly verifies only **4.45%** at query level.
2. **World ranking is currently the bottleneck.** With only a weak fixed lexical relation prior and equal source reliability, B4 selects conflict on **22.79%** of rows and exact paired localization on only **7.14%**.
3. **Naive weighting is not enough.** B4 is below B2's **29.93%** row conflict recall. Therefore H3 is **not yet supported** by MAGIC. This negative result is retained rather than tuned away.
4. MAGIC does not provide meaningful source-reliability variation for this structured track. Therefore the next adjudication experiment belongs on a truth-discovery dataset such as DAFNA, while MAGIC remains the primary world-construction/localization diagnostic.

The empirical decomposition is now:

```text
candidate discovery
      ↓
world construction / gold-world retention
      ↓
world ranking
      ↓
truth adjudication
```

The current experiment shows that the largest immediate gap is **gold world retained (39.39%) → correctly selected/localized (7.14% exact row LOC)**, not simply graph path discovery.

---

# Published MAGIC peer reference

Published peers read natural-language contexts and are evaluated with official ID/LOC. Their weighted multi-hop values are reference-only and must not be directly ranked against our structured diagnostics.

| Published peer | Weighted ID | Weighted LOC |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | **78.40%** | **47.28%** |
| **5-model mean** | **54.34%** | **29.25%** |

A fair peer-comparable experiment still requires the same natural-language input/output protocol. The current structured exact LOC should not be described as official MAGIC LOC.

---

# Prior research baseline

The repository previously focused on an ontology-guided bidirectional Tableau. That work is retained as prior baseline, not the final research claim.

Prior MAGIC structured multi-hop diagnostics:

| Prior component | Result |
|---|---:|
| Direct heuristic detection | 33.16% |
| Bidirectional candidate-path coverage | 68.03% |
| Strict ontology-verified contradiction | 5.44% |

The 68.03% value is candidate path coverage, **not accuracy**. The 5.44% strict contradiction value motivated treating uncertain relation interpretation as a world variable instead of continually hardcoding ontology composition rules.

---

# Dataset roles in the new paper

## MAGIC — world construction and localization

Primary questions:

- Is the correct conflicting explanation present among retained worlds?
- Are all query-specific gold perturb paths localized?
- How quickly does the number of possible worlds grow with conflict count?
- Can a non-leaking relation-semantic model improve world ranking?

## DAFNA-EA Books — world-level truth adjudication

Primary question:

> Once competing worlds are available, does real source reliability improve gold truth recovery?

Existing prior same-protocol result:

| Prior method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| Previous Rashomon atomic resolution | **61.00%** | **82.88%** |
| TruthFinder | 57.00% | 66.85% |
| AccuSim | 57.00% | 66.18% |
| 2-Estimates | 54.00% | 65.28% |
| 3-Estimates | 53.00% | 65.45% |
| Accu | 53.00% | 65.45% |

The 61.00% value is a prior-method result. It is not claimed as a Rashomon Worlds result until the new world-level DAFNA evaluator is executed.

LogicNLI and FOLIO remain reasoning-engine sanity checks rather than headline peer benchmarks.

---

# Implementation

Core files:

```text
src/rashomon_tableau/possible_worlds.py
    RelationHypothesis
    PathRelationHypothesis
    WorldChoice
    PossibleWorld
    build_possible_worlds(...)
    truth_marginal(...)

scripts/evaluate_magic_possible_worlds.py
    B1/B2/B3/B4 MAGIC multi-hop ablation
```

Current world weighting is deliberately simple and ablatable:

```text
world_weight ∝ relation_support × source_support
```

The first MAGIC experiment uses equal source reliability and a fixed, broad lexical prior over relation names. No row IDs, `rel_id` labels, gold conflict labels, or sample-specific composition rules are used to score candidate relation interpretations. Gold perturb groups are used only after prediction for localization evaluation.

---

# Research boundary

This work does not claim that possible-world semantics, Tableau, knowledge graphs, rule mining, or source reliability are new independently. The intended contribution is the focused framework and empirical decomposition:

> **source-provenanced conflicting multi-hop claims + uncertain relation interpretations + Tableau-consistent possible worlds + reliability-weighted world/truth adjudication.**

The strongest final claim remains conditional on the next experiments: improve non-leaking world ranking and validate world-level truth adjudication with real source reliability.
