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
- **H3 — World adjudication:** a stronger world scorer / posterior reliability model should recover the correct explanation or truth more reliably than weak early commitment.

---

# Measured result 1 — MAGIC multi-hop structured track

Validated on **588 conflict rows / 1,056 query-level conflicts**.

| Variant | Row conflict recall | Query conflict recall | Gold-world query recall | Structured row exact LOC |
|---|---:|---:|---:|---:|
| B1 Static Tableau | **5.44%** | 4.45% | — | — |
| B2 Early-commit single world | **29.93%** | 22.63% | — | — |
| B3 Possible-world retention | — | — | **39.39%** | **29.42%** |
| B4 Weak lexical weighting | **22.79%** | **16.86%** | — | **7.14%** |
| **B5 Rashomon + DeBERTa-v3 world scorer** | **41.50%** | **31.53%** | — | **15.48%** |

DeBERTa-v3 selected the paired gold conflict path for **22.06%** of query conflicts. Relative to the identical candidate-world pipeline with the weak lexical scorer, changing only the ranking/scoring layer produced:

- row conflict recall: **22.79% → 41.50% (+18.70 pp)**
- query conflict recall: **16.86% → 31.53% (+14.68 pp)**
- structured exact localization: **7.14% → 15.48% (+8.33 pp)**

This is direct evidence that the earlier world-selection layer was a real bottleneck: candidate-world generation is held fixed while a stronger discriminative scorer substantially improves which worlds are selected.

Complexity remains approximately **1.46 candidate paths/query** and **4.09 retained worlds/query**.

**Metric boundary:** the released structured multi-hop files used here are conflict cases, so these conflict values are recall, not published MAGIC ID accuracy. `structured exact LOC` is an internal provenance diagnostic based on paired `original_triplet[i] ↔ perturb_triplet[i]`; it is not the paper's natural-language human-scored LOC metric.

Measured summaries:

- [`results/magic_possible_worlds_summary.json`](./results/magic_possible_worlds_summary.json)
- [`results/magic_deberta_worlds_summary.json`](./results/magic_deberta_worlds_summary.json)

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

Measured gains for the marginal method:

- vs prior Atomic: **+1.00 pp exact**, **+1.25 pp Author F1**
- vs hard early commitment: **+1.00 pp exact**, **+0.08 pp Author F1**
- vs official TruthFinder: **+5.00 pp exact**
- vs official AccuSim: **+5.00 pp exact**

The main DAFNA bottleneck remains visible in **93% gold-world coverage → 62% exact selection**. As with MAGIC, the evidence points to world ranking/calibration rather than simply generating more worlds.

Measured summary: [`results/dafna_possible_worlds_summary.json`](./results/dafna_possible_worlds_summary.json)

---

# Natural-language MAGIC method-effect study

The next direct peer-comparable experiment uses the original MAGIC natural-language contexts. The research question is not which LLM is strongest; it is whether the **same base LLM** improves after adding Rashomon Worlds.

For every model, the runner compares:

1. `Direct`
2. `Compute-Matched Direct`
3. `Rashomon Worlds + same-LLM world scorer`
4. `Rashomon Worlds + DeBERTa-v3 world scorer`

`Compute-Matched Direct` is the main control for the fact that the Rashomon pipeline may use more LLM calls/tokens. Gold MAGIC triplets and localization labels are unavailable to every prediction condition and are attached only after prediction for audit/evaluation.

### Current 2026 model track

- GPT-5.5
- GPT-5.4 mini
- Claude Sonnet 5
- Mistral Small 4
- Llama 3.3 70B Instruct

### Historical MAGIC reproduction track

- Mixtral 8x7B
- Llama 3.1 70B
- Claude 3.5 Haiku
- GPT-4o-mini
- o1

Historical and current models are reported in separate tables. Retired historical checkpoints are never silently replaced by newer family members.

Natural-language LOC follows MAGIC's manual/blinded scoring design. The repository exports blinded sentence-level predictions rather than inventing an automatic LOC judge.

Runner and configuration:

```text
scripts/run_magic_peer_matrix.py
config/magic_peer_model_matrix.yaml
config/magic_peer_env.example
.github/workflows/magic-live-model-matrix.yml
```

No multi-model live result is claimed until the corresponding provider credentials/endpoints are supplied and the paired runs are executed.

---

# What the experiments jointly establish

```text
MAGIC structured
  candidate worlds retained
      ↓
  world scorer quality
      ↓
  conflict / localization selection

DAFNA
  competing truth worlds
      ↓
  source reliability posterior
      ↓
  final truth adjudication

MAGIC natural language (next live track)
  same base LLM
      ↓
  Direct vs Compute-Matched vs Rashomon
      ↓
  model-agnostic method effect
```

The current evidence supports a narrower paper claim:

> **Possible worlds preserve viable multi-hop explanations that static reasoning misses, and final performance is strongly controlled by world ranking. A discriminative DeBERTa-v3 scorer materially improves structured MAGIC selection, while posterior-aware reliability gives a smaller but measurable truth-adjudication gain on DAFNA.**

The remaining direct peer question is whether the same advantage persists across multiple LLMs on MAGIC's natural-language ID/LOC protocol.

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

src/rashomon_tableau/deberta_world_scorer.py
  DebertaWorldScorer
  WorldNliScore

src/rashomon_tableau/peer_llm.py
  provider-neutral LLM adapters

scripts/evaluate_magic_possible_worlds.py
scripts/evaluate_magic_deberta_worlds.py
scripts/evaluate_dafna_possible_worlds.py
scripts/run_magic_peer_matrix.py
```

---

# Research boundary

This work does **not** claim possible-world semantics, Tableau reasoning, DeBERTa, knowledge graphs, or source reliability are individually new. DeBERTa is an interchangeable world-ranking component, not a separate novelty claim.

The contribution under evaluation is the problem-specific framework:

> **source-provenanced conflicting multi-hop claims + uncertain relation interpretations + Tableau-consistent possible worlds + explicit world scoring/posterior adjudication.**

Everything else is evaluated as a component or implementation choice under controlled ablations.
