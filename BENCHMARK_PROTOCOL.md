# Benchmark Protocol — Rashomon Worlds

## Purpose

This document defines how to test the revised research claim without mixing prior metrics or creating unfair peer comparisons.

The central question is:

> **Do multiple Tableau-consistent, provenance-weighted worlds improve multi-hop conflict localization and truth adjudication over single-world commitment?**

---

## 1. Dataset Roles

### MAGIC
Primary role: **multi-hop conflict identification, localization, and world construction**.

Required outputs:

- official conflict ID;
- official exact LOC;
- candidate-world count;
- consistent-world count;
- gold-world recall;
- relation-interpretation accuracy;
- proof/provenance localization accuracy;
- unresolved mass.

### DAFNA-EA Books
Primary role: **truth adjudication across conflicting sources/worlds**.

Required outputs:

- exact truth accuracy;
- author F1;
- calibration / confidence quality where possible;
- source-only vs world-level reliability ablation.

### LogicNLI / FOLIO
Secondary role only: **reasoning-engine sanity checks**.

They must not be used as headline evidence that the Possible-World method outperforms natural-language peer systems.

---

## 2. Prior Baselines vs New Results

The following values are historical repository baselines and must remain labeled as such:

### Prior MAGIC structured diagnostic

| Metric | Multi-hop |
|---|---:|
| direct heuristic detection | 33.16% |
| bidirectional candidate-path coverage | 68.03% |
| strict ontology-verified contradiction | 5.44% |

These are three different metrics. In particular, 68.03% is **not** ID or LOC.

### Prior DAFNA same-protocol result

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| prior Rashomon atomic resolution | 61.00% | 82.88% |
| TruthFinder | 57.00% | 66.85% |
| AccuSim | 57.00% | 66.18% |

The new Possible-World method gets a new row only after a new evaluator is executed.

---

## 3. MAGIC Published Peer Reference

Weighted from the official N=1..4 multi-hop subgroup values and counts:

| Peer | ID | LOC |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | 78.40% | 47.28% |
| 5-model mean | 54.34% | 29.25% |

### Comparability rule

Published peers use natural-language contexts. A structured-triplet Rashomon Worlds evaluator is a **separate track** unless the same text input and output protocol is reproduced.

Never compare:

```text
68.03% path coverage  vs  78.40% MAGIC ID
```

as if they were the same metric.

---

## 4. Core Ablation

All new-method claims should come from this progression:

| ID | Variant | Relation semantics | World model | Weighting |
|---|---|---|---|---|
| B0 | Direct | direct claims | one | none |
| B1 | Static Tableau | hard ontology | one | none |
| B2 | Adaptive Relation | hard + defeasible candidates | one selected interpretation | relation confidence |
| B3 | Possible Worlds | hard + defeasible candidates | multiple consistent worlds | uniform |
| B4 | Rashomon Worlds | hard + defeasible candidates | multiple consistent worlds | source + relation + proof/evidence |

The critical comparisons are:

- `B2 > B1`: uncertain relation semantics helps beyond static ontology;
- `B3 > B2`: delaying commitment to multiple worlds helps beyond picking one candidate;
- `B4 > B3`: provenance-aware reliability helps beyond uniform possible worlds.

If those gains are absent, the central research hypothesis is not supported.

---

## 5. World Metrics

### World coverage
Fraction of examples where at least one admissible candidate world is generated.

### Gold-world recall
Fraction of examples where at least one generated world contains the gold-compatible relation/claim interpretation.

### Consistent-world precision
Among generated admissible worlds, proportion matching gold-compatible semantics when such annotation can be derived fairly.

### Relation interpretation accuracy
Accuracy of the selected or highest-mass relation interpretation.

### Truth marginal
For query `q`:

```text
P(q)
P(not q)
P(BOTH)
P(UNRESOLVED)
```

These masses must sum to 1 after world normalization.

### Early-commitment error
Cases where B2 chooses the wrong interpretation but B3/B4 retains a gold-compatible world.

This metric directly tests the paper's delayed-commitment claim.

---

## 6. Relation-Hypothesis Protocol

A relation hypothesis may come from:

- external ontology/property metadata;
- rule induction on a training graph;
- development-only learned relation patterns;
- another candidate generator.

### Forbidden

- hand-writing a rule after reading a test example;
- using sample IDs or answer labels in rules;
- promoting benchmark-specific patterns to hard ontology axioms;
- selecting candidate rules using test LOC/ID labels.

### Preferred evaluation

```text
external/train relation source
        ↓
induce candidate semantics
        ↓
freeze hypotheses / generator
        ↓
run MAGIC test evaluation
```

Where possible, add relation-held-out or domain-held-out experiments.

---

## 7. Peer Comparison Table

The final paper should separate tracks instead of forcing one leaderboard.

### Track A — MAGIC natural-language peer comparison

| Method | Input | ID | LOC |
|---|---|---:|---:|
| published LLM peers | natural language | published | published |
| Rashomon Worlds text track | natural language | measured | measured |

### Track B — Structured reasoning ablation

| Method | ID analogue | LOC/proof | Gold-world recall | Unresolved mass |
|---|---:|---:|---:|---:|
| B0 | measured | measured | — | measured |
| B1 | measured | measured | measured | measured |
| B2 | measured | measured | measured | measured |
| B3 | measured | measured | measured | measured |
| B4 | measured | measured | measured | measured |

### Track C — DAFNA truth adjudication

| Method | Truth Accuracy | Author F1 |
|---|---:|---:|
| majority / local baselines | measured | measured |
| TruthFinder / Accu family | official same-protocol | official same-protocol |
| prior Rashomon | historical | historical |
| Rashomon Worlds | measured | measured |

---

## 8. Improvement Reporting

Only report improvement between metrics with identical definitions and protocols.

Allowed example:

```text
B3 MAGIC LOC = 41.0
B4 MAGIC LOC = 46.0
Improvement = +5.0 percentage points
```

Not allowed:

```text
old path coverage 68.03
new ID 70.0
improvement +1.97
```

because the metrics differ.

Report both absolute percentage-point improvement and relative improvement when useful.

---

## 9. Reproducibility Requirements

Each measured new result must record:

- dataset version/source;
- exact split;
- relation-hypothesis source;
- whether hypotheses are frozen before evaluation;
- maximum world count / pruning policy;
- scoring coefficients or weighting rule;
- random seed where applicable;
- code commit;
- workflow run/artifact when executed in CI.

---

## 10. Current Status

Implemented:

- PossibleWorld model;
- RelationHypothesis model;
- alternative-world enumeration;
- unresolved semantic branch;
- Tableau consistency pruning;
- source/relation baseline weighting;
- truth marginalization;
- unit tests.

Not yet measured for the new method:

- MAGIC official ID;
- MAGIC official LOC;
- MAGIC gold-world recall;
- DAFNA Possible-World truth accuracy;
- calibrated full B4 reliability function.

Until those runs exist, historical measurements remain baseline evidence only.
