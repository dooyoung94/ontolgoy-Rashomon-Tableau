# Rashomon Worlds

## Provenance-Aware Possible-World Reasoning for Multi-Hop Conflict and Truth Adjudication

> **Thesis:** when multi-hop evidence conflicts and relation semantics are incomplete, committing early to one interpretation can discard viable explanations. Rashomon Worlds preserves incompatible but internally consistent interpretations as possible worlds, then adjudicates across them using provenance and reliability.

```text
Conflicting Claims
      ↓
Multi-hop Candidates
      ↓
Uncertain Relation Interpretations
      ↓
┌──────────┼──────────┐
World 1  World 2   World K
  SAT       SAT       SAT
└────── Tableau ──────┘
      ↓
World Reliability / Posterior
      ↓
Truth Adjudication
```

A world is `W = {claims, sources, relation interpretations, derivations/proofs}`. Uncertain relation composition is a defeasible world variable, not automatically a hard ontology axiom.

## Research hypotheses

- **H1 — World construction:** possible worlds should preserve valid multi-hop explanations that static ontology reasoning leaves unresolved.
- **H2 — Delayed commitment:** retaining alternatives should avoid losing viable explanations through early single-world selection.
- **H3 — World adjudication:** marginalizing source reliability over competing worlds should improve truth recovery over early MAP commitment and source-only/atomic baselines.

---

# Measured result 1 — MAGIC multi-hop structured track

Validated on **588 conflict rows / 1,056 query-level conflicts**.

| Variant | Row conflict recall | Query conflict recall | Gold-world query recall | Structured row exact LOC |
|---|---:|---:|---:|---:|
| B1 Static Tableau | **5.44%** | 4.45% | — | — |
| B2 Early-commit single world | **29.93%** | 22.63% | — | — |
| B3 Possible-world retention | — | — | **39.39%** | **29.42%** |
| B4 Weakly weighted worlds | **22.79%** | 16.86% | — | **7.14%** |

Complexity: **1.46 candidate paths/query**, **4.10 retained worlds/query**, **7.36 worlds/row**.

Interpretation:

- H1 receives positive evidence: possible worlds retain substantially more gold conflict explanations than static Tableau can formally close.
- H2 is supported as a *retention* claim: viable explanations survive rather than being eliminated by one early interpretation.
- MAGIC also exposes a negative result: weak lexical/equal-source weighting does **not** select the right world reliably. B4 is below B2 on row conflict recall.
- Therefore world generation and world ranking are separate research problems.

**Metric boundary:** the released structured multi-hop files used here are conflict cases, so these conflict values are recall, not published MAGIC ID accuracy. `structured exact LOC` is an internal provenance diagnostic based on paired `original_triplet[i] ↔ perturb_triplet[i]`; it is not the paper's natural-language LOC metric.

Measured summary: [`results/magic_possible_worlds_summary.json`](./results/magic_possible_worlds_summary.json)

Published natural-language MAGIC peer reference remains a separate track:

| Peer | Weighted ID | Weighted LOC |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | **78.40%** | **47.28%** |
| 5-model mean | **54.34%** | **29.25%** |

Do not directly rank those natural-language ID/LOC numbers against the structured diagnostics above.

---

# Measured result 2 — DAFNA-EA Books truth adjudication

Same 100-book `AuthorsNamesList` gold subset, **1,999 collapsed source-object claims / 227 sources**, with shared benchmark-side person normalization. Gold truth is never used for candidate-world generation, world scoring, or source-reliability updates.

Candidate generation contains the gold truth world for **93.00%** of books, with **27.94 candidate worlds/book** on average.

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds — Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds — Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds — Uniform | 58.00% | 80.38% |
| TruthFinder — official DAFNA-EA | 57.00% | 66.85% |
| AccuSim — official DAFNA-EA | 57.00% | 66.18% |
| 2-Estimates — official DAFNA-EA | 54.00% | 65.28% |
| 3-Estimates — official DAFNA-EA | 53.00% | 65.45% |
| Accu — official DAFNA-EA | 53.00% | 65.45% |

Measured gains for the proposed marginal method:

- vs prior Atomic: **+1.00 pp exact**, **+1.25 pp Author F1**
- vs hard early commitment: **+1.00 pp exact**, **+0.08 pp Author F1**
- vs official TruthFinder: **+5.00 pp exact**
- vs official AccuSim: **+5.00 pp exact**

This is modest, not a large-effect result. It is the first direct evidence for H3: **updating source reliability over the posterior of multiple worlds slightly outperforms updating against only the current MAP world**.

The main remaining bottleneck is visible in the gap **93% gold-world coverage → 62% exact selection**. The next improvement target is ranking/calibration, not simply generating more worlds.

Measured summary: [`results/dafna_possible_worlds_summary.json`](./results/dafna_possible_worlds_summary.json)

---

# What the two datasets jointly establish

```text
MAGIC
  candidate/path uncertainty
      ↓
  world construction
      ↓
  gold explanation retention

DAFNA
  competing truth worlds
      ↓
  source reliability
      ↓
  marginal world adjudication
```

The current evidence therefore supports a narrower and cleaner paper claim:

> **Possible worlds improve preservation of plausible multi-hop conflict explanations, and posterior-aware reliability gives a small but measurable truth-adjudication gain over early commitment. The dominant remaining problem is selecting the correct world from a high-coverage candidate set.**

This is intentionally different from claiming that “Ontology + KG + Tableau + reliability” as a technology stack is novel.

---

# Prior baseline

The repository's earlier ontology-guided bidirectional Tableau is retained only as prior work/diagnostic:

| Prior MAGIC component | Multi-hop |
|---|---:|
| Direct heuristic | 33.16% |
| Bidirectional candidate-path coverage | 68.03% |
| Strict ontology-verified contradiction | 5.44% |

`68.03%` is candidate-path coverage, not accuracy. The large gap between path discovery and formal closure motivated treating uncertain relation semantics as alternative worlds instead of hardcoding more composition rules.

---

# Core implementation

```text
src/rashomon_tableau/possible_worlds.py
  RelationHypothesis
  PathRelationHypothesis
  WorldChoice
  PossibleWorld
  build_possible_worlds(...)
  truth_marginal(...)

src/rashomon_tableau/truth_worlds.py
  TruthWorld
  candidate_truth_worlds(...)
  score_worlds(...)
  possible_world_truth_resolution(...)

scripts/evaluate_magic_possible_worlds.py
scripts/evaluate_dafna_possible_worlds.py
```

DAFNA candidate truth worlds are generated from observed author sets plus bounded combinations of source-supported atomic authors. Three ranking modes are evaluated on the identical candidate space: uniform, hard/MAP reliability, and marginal/posterior reliability.

---

# Research boundary

This work does **not** claim possible-world semantics, Tableau reasoning, knowledge graphs, rule mining, or source reliability are individually new. The contribution under evaluation is their problem-specific integration:

> **source-provenanced conflicting multi-hop claims + uncertain relation interpretations + Tableau-consistent possible worlds + posterior-aware reliability for truth adjudication.**

The next scientifically useful step is not benchmark-specific rule tuning. It is a non-leaking world-ranking model using frozen external relation semantics and calibrated provenance/reliability, followed by a natural-language MAGIC track under the published ID/LOC protocol.
