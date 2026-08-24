# Benchmark Protocol — Rashomon Worlds

## Central test

> **Does preserving multiple internally consistent worlds, then adjudicating across them with provenance-aware reliability, improve multi-hop explanation retention and final truth recovery over early single-world commitment?**

The protocol deliberately separates **world construction/localization** from **world ranking/truth adjudication**.

---

## 1. Dataset roles

### MAGIC — world construction and localization

Current structured track uses all released multi-hop conflict files:

- 588 rows;
- 1,056 paired query conflicts.

Required metrics:

- row/query conflict recall;
- gold-world query recall;
- strict structured row exact localization;
- candidate-path count;
- retained-world count.

**Boundary:** because the released structured files in this track are conflict cases, conflict detection values are recall, not full official MAGIC ID accuracy. Structured exact localization requires all `original_triplet[i] ↔ perturb_triplet[i]` pairs to be localized and is not the natural-language MAGIC LOC metric.

A future text track must reproduce the published natural-language input/output protocol before reporting direct ID/LOC peer comparison.

### DAFNA-EA Books — world adjudication

Current same-protocol track:

- 100 gold books;
- `AuthorsNamesList`;
- 1,999 collapsed source-object claims;
- 227 sources;
- shared surname + first-initial benchmark-side normalization.

Required metrics:

- candidate gold-world coverage;
- exact set truth accuracy;
- author F1;
- uniform vs hard/MAP vs marginal reliability ablation;
- official DAFNA-EA peer comparison.

Gold truth is evaluation-only. It must not enter candidate generation, scoring, or source-reliability updates.

### LogicNLI / FOLIO

Reasoning-engine sanity checks only; not headline evidence for the possible-world contribution.

---

## 2. Measured MAGIC structured results

Validated run `32725453943`, artifact `9519356207`.

| Variant | Row conflict recall | Query conflict recall | Gold-world query recall | Structured row exact LOC |
|---|---:|---:|---:|---:|
| B1 Static Tableau | 5.44% | 4.45% | — | — |
| B2 Early-commit single world | 29.93% | 22.63% | — | — |
| B3 Possible-world retention | — | — | **39.39%** | **29.42%** |
| B4 Weakly weighted worlds | 22.79% | 16.86% | — | 7.14% |

Complexity:

- 1.46 candidate paths/query;
- 4.10 retained worlds/query;
- 7.36 worlds/row.

Interpretation rule: B3 supports **retention**, but B4 does not support a claim that naive weighting improves selection. The B4 < B2 result must remain visible.

---

## 3. Measured DAFNA truth-world results

Validated run `32726434311`, artifact `9519739380`.

Candidate generation:

- gold-world coverage: **93.00%**;
- mean candidate worlds/book: **27.94**;
- max candidate worlds: **256**.

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds — Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds — Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds — Uniform | 58.00% | 80.38% |
| TruthFinder, official | 57.00% | 66.85% |
| AccuSim, official | 57.00% | 66.18% |
| 2-Estimates, official | 54.00% | 65.28% |
| 3-Estimates, official | 53.00% | 65.45% |
| Accu, official | 53.00% | 65.45% |

Identical-protocol gains:

- marginal vs hard commitment: **+1.00 pp exact**, **+0.08 pp F1**;
- marginal vs prior atomic: **+1.00 pp exact**, **+1.25 pp F1**;
- marginal vs TruthFinder/AccuSim: **+5.00 pp exact**.

Do not claim global SOTA. Safe scope is the evaluated 100-book AuthorsNamesList subset under shared normalization.

---

## 4. Core ablation definitions

### MAGIC

- **B1 Static Tableau:** hard ontology only, single logical state.
- **B2 Early Commit:** one highest-scoring relation interpretation, including unresolved.
- **B3 Possible Worlds:** retain alternative consistent relation interpretations and evaluate whether the paired gold conflict world survives.
- **B4 Weighted Worlds:** marginalize worlds using the same fixed relation prior; MAGIC sources are treated equally in this first structured experiment.

### DAFNA

All variants use the same candidate world generator.

- **Uniform:** equal source reliability.
- **Hard Commit:** update each source against the current MAP truth world.
- **Marginal Reliability:** update source reliability using expected compatibility over the complete world posterior.

This isolates delayed commitment from candidate generation.

---

## 5. Leakage rules

### Forbidden

- adding a relation rule after seeing a MAGIC test example;
- using row IDs, `rel_id`, gold conflict labels, or gold LOC to score a relation hypothesis;
- using DAFNA gold truth to create or rank candidate author worlds;
- tuning coefficients directly on the reported test set and then presenting the same set as unbiased evaluation.

### Current MAGIC first-ablation policy

Relation interpretation scores use only a frozen broad lexical prior over relation names. Gold perturb groups are read only after prediction to calculate localization.

### Preferred next MAGIC protocol

```text
external ontology / train graph
        ↓
relation-rule induction or semantic model
        ↓
freeze model
        ↓
relation-held-out / domain-held-out evaluation
        ↓
MAGIC test
```

---

## 6. Published MAGIC peer boundary

Natural-language peer references:

| Peer | Weighted ID | Weighted LOC |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | 78.40% | 47.28% |

These values cannot be directly compared with structured `gold-world recall` or `structured exact LOC`. A fair direct comparison requires a Rashomon Worlds natural-language track evaluated with official MAGIC ID/LOC.

---

## 7. Prior repository baseline

Historical MAGIC structured diagnostics:

| Metric | Multi-hop |
|---|---:|
| direct heuristic | 33.16% |
| bidirectional path coverage | 68.03% |
| strict ontology contradiction | 5.44% |

`68.03%` is path coverage, not accuracy or ID. These values explain the research transition but must not be mixed arithmetically with the new metrics.

---

## 8. Improvement reporting

Improvement may be reported only between identical metrics under the same protocol.

Valid:

- DAFNA marginal 62% vs hard 61% exact = **+1.0 pp**.
- DAFNA marginal 62% vs TruthFinder 57% exact = **+5.0 pp** under the shared evaluated subset.

Invalid:

- 68.03% old MAGIC path coverage vs 39.39% gold-world recall;
- structured MAGIC LOC analogue vs published natural-language LOC;
- MAGIC conflict recall vs natural-language ID accuracy.

---

## 9. Reproducibility record

Each headline result must record:

- exact dataset/split;
- candidate-world construction policy;
- source/relation weighting rule;
- maximum world count/pruning policy;
- gold usage policy;
- code commit;
- CI workflow run;
- artifact ID and digest.

Persistent summaries:

- `results/magic_possible_worlds_summary.json`
- `results/dafna_possible_worlds_summary.json`

---

## 10. Current evidence status

- **H1:** supported on MAGIC as explanation-retention evidence.
- **H2:** supported for preserving alternatives; not enough to claim all multi-world ranking is superior, because weak MAGIC B4 ranking is below B2.
- **H3:** modestly supported on DAFNA; marginal reliability improves exact truth accuracy from 61% hard-commit to 62%.

The dominant remaining research gap is **world ranking/calibration**: MAGIC preserves more correct explanation worlds than it selects, and DAFNA has 93% gold-world coverage but only 62% exact final selection.
