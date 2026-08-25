# When Not to Prune: Preserving Conflicting Multi-Hop Evidence

## Core claim

Multi-hop reasoning can expose several plausible paths, including evidence that supports and contradicts the same claim. If a conflicting branch is removed during search, a downstream verifier cannot recover it.

This repository therefore studies **preservation before resolution**:

> **When is fixed-width pruning unsafe, and how can a reasoner preserve useful competing evidence without simply keeping everything?**

```text
Query / Claim
    ↓
Multi-hop expansion
    ↓
Semantic scorer (DeBERTa first)
    ↓
Competing candidate paths
    ↓
Fixed Top-K  vs  delayed/adaptive preservation
    ↓
Preserved reasoning state
    ↓
Future work: semantic/logical resolution
```

The current paper is `Preserve`. Ontology/Tableau-based truth resolution is a later `Resolve` stage.

---

## 1. What differs from ToG-style pruning?

ToG already performs repeated graph exploration and keeps a beam. The distinction is therefore not `one path vs many paths`.

Fixed-width pruning:

```text
P_k = TopK(C_k, s_theta, K)
```

Rashomon-inspired best-relative retention:

```text
s* = max_p s_theta(p,q)
R_eps = {p | s_theta(p,q) >= s* - eps}
```

Scale-aware relative-loss variant:

```text
L(p)=1-s(p)
R_eps = {p | L(p) <= (1+eps)L*}
```

Exploratory boundary-aware delayed pruning:

```text
cutoff = score of the K-th candidate
P = {p | s(p) >= cutoff - eps}
```

The boundary variant asks a particularly direct pruning question:

> **If the K-th and (K+1)-th paths are nearly tied, is the fixed rank boundary sufficient reason to delete the latter?**

No policy is assumed superior a priori.

---

## 2. What counts as successful preservation?

For MAGIC query `i`, let `G_i^-` be the externally defined contradictory evidence path family from the paired `perturb_triplet` provenance.

A query is evaluated for pruning only when:

```text
G_i^- intersects C_i != empty
```

so that the gold conflict evidence was recoverable **before** pruning.

Then:

```text
ConflictPathSurvival_i = 1[selected_i intersects G_i^-]
ConflictInformationLoss_i = 1 - ConflictPathSurvival_i
```

This separates retrieval failure from pruning-caused information loss.

### Retained-set validity

Preservation alone is insufficient. Extra paths can be noise.

For this benchmark-specific task a retained path is externally valid when it covers the paired MAGIC gold perturb evidence (`gold_path=true`). We therefore also report:

```text
Retained Gold Precision
Retained Gold Recall
Retained Gold F1
Invalid Retention Rate
Average retained width / expansion cost
```

Important caveat: a MAGIC non-gold path may still be semantically useful evidence. Here `precision` means precision for the benchmark's paired conflict evidence, not universal truth or usefulness.

The actual optimization problem is therefore three-way:

```text
Conflict preservation
        ×
Retained-set validity
        ×
Search cost
```

---

## 3. Dataset roles

| Dataset | Role |
|---|---|
| **WN18RR** | generic premature-pruning / iterative-search stress test |
| **MAGIC multi-hop conflict** | external-gold conflicting-evidence preservation and retained-set validity |

WN18RR is not treated as an explicit contradiction benchmark.

---

## 4. DeBERTa remains meaningful

DeBERTa is not the pruning algorithm. It is the first semantic verifier producing:

```text
D(p,q) = (Support, Contradiction, Unresolved)
```

For side-agnostic conflict preservation on MAGIC we use:

```text
r(p,q)=Support+Contradiction=1-Unresolved
```

so strong support and strong contradiction are both considered worth preserving.

Existing executed MAGIC semantic-verifier result (`588 rows / 1,056 queries`):

| Metric | Weak lexical prior | DeBERTa | Gain |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71pp** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68pp** |
| Structured exact LOC | 7.14% | **15.48%** | **+8.33pp** |

Source run `32730398659`, artifact `9521415589`.

This is evidence that DeBERTa contributes meaningful semantic path discrimination when candidate paths exist. It is not evidence that DeBERTa alone solves graph search.

---

## 5. WN18RR findings

### 5.1 Relation-level frozen-score diagnostic

| Policy | Gold survival | Avg width |
|---|---:|---:|
| Top-1 | 16% | 1.00 |
| Top-3 | 32% | 3.00 |
| Top-5 | 40% | 5.00 |
| Additive eps=.05 | 42% | 3.82 |
| Additive eps=.10 | **58%** | 5.08 |
| No pruning | 100% | 11.00 |

This was a positive candidate-retention signal, not iterative search.

### 5.2 Iterative search: naive additive rule fails

10-query iterative pilot:

| Policy | Search success | Pruning regret | Avg width |
|---|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 |
| Top-5 | 60% | 40% | 3.88 |
| Additive eps=.05 | 40% | 60% | 2.65 |
| Additive eps=.10 | 40% | 60% | 3.62 |

This falsified the naive claim that `best - epsilon` is automatically better.

### 5.3 Scale-aware relative loss partially recovers the failure

Executed run `32813194834`, artifact `9550550657`:

| Policy | Search success | Pruning regret | Avg width | Avg expanded |
|---|---:|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 | 21.3 |
| Top-5 | 60% | 40% | 3.88 | 28.3 |
| Additive eps=.10 | 40% | 60% | 3.62 | 28.5 |
| Relative-loss eps=.25 | 50% | 50% | 4.09 | 31.4 |
| **Relative-loss eps=.50** | **70%** | **30%** | **5.97** | 31.4 |

The scale-aware rule can recover viable paths, but the gain is not free: it requires substantially larger active width. With `n=10`, this remains a pilot rather than a final superiority claim.

---

## 6. MAGIC external-gold preservation + validity

Latest executed validity ablation:

```text
Run      32817516186
Artifact 9551919328
Digest   sha256:3f83fbe18da5c43c94e8f12493c166fd685c873f232cfd6d233f97e9c37bb4c8
```

Protocol:

```text
588 rows
1,056 queries
618 queries with candidate paths
420 queries with an externally-gold conflict path recoverable before pruning
```

### 6.1 Full recoverable set: n=420

| Policy | Survival ↑ | Gold precision ↑ | Gold recall ↑ | F1 ↑ | Avg width ↓ |
|---|---:|---:|---:|---:|---:|
| Top-1 | 80.71% | **80.71%** | 80.52% | **80.62%** | **1.00** |
| Top-3 | 94.76% | 59.38% | 94.77% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 98.10% | 70.54% | 1.79 |
| Additive eps=.05 | 94.76% | 54.00% | 94.54% | 68.74% | 1.75 |
| Additive eps=.10 | 97.14% | 50.18% | 97.15% | 66.18% | 1.94 |
| Relative-loss eps=.25 | 83.81% | 74.26% | 83.61% | 78.66% | 1.13 |
| **Boundary Top-3 + .01** | **97.86%** | 55.30% | **97.86%** | 70.67% | **1.77** |
| Boundary Top-5 + .01 | 98.81% | 52.93% | 98.81% | 68.93% | 1.87 |
| No pruning | 100% | 46.67% | 100% | 63.64% | 2.15 |

This table answers the user's key validity question directly: **keeping more paths increases recall/survival but generally reduces benchmark-gold precision.**

Notable exploratory result:

```text
Top-3:               survival 94.76%, width 1.60
Boundary Top-3+.01:  survival 97.86%, width 1.77
```

The boundary extension gains `+3.10pp` survival for only `+0.17` retained paths on average. In paired survival outcomes it rescued 13 queries that Top-3 lost, while Top-3 rescued none that boundary Top-3 lost (`exact two-sided sign p=0.000244`; exploratory, not a final confirmatory test).

### 6.2 High branching exposes the preservation problem

For queries with at least five candidate paths (`n=32`):

| Policy | Survival ↑ | Gold precision ↑ | F1 ↑ | Avg width ↓ |
|---|---:|---:|---:|---:|
| Top-3 | 37.50% | 12.50% | 18.75% | 3.00 |
| Top-5 | 75.00% | **15.00%** | **25.00%** | 5.00 |
| Additive eps=.05 | 84.38% | 11.95% | 20.93% | 7.06 |
| Additive eps=.10 | **96.88%** | 11.52% | 20.60% | 8.41 |
| Boundary Top-5+.01 | 84.38% | 13.78% | 23.68% | 6.13 |
| No pruning | 100% | 10.26% | 18.60% | 9.75 |

So broad epsilon preservation does exactly what it is supposed to do on survival, but also preserves considerable noise. This prevents an invalid conclusion such as `more retained = better reasoning`.

Paired survival outcomes for `paths >=5`:

```text
Rashomon eps=.10 only succeeds: 8
Top-5 only succeeds:          1
Both:                        23
Neither:                       0
exact two-sided sign p = 0.0391
```

Treat this as exploratory evidence because the subset is small (`n=32`) and epsilon was examined among multiple policies.

---

## 7. Branching vs score ambiguity

Top-2 score margin was added as an ambiguity diagnostic. Quartile boundaries among branching recoverable cases are approximately:

```text
Q1: 0.00197
Q2: 0.01307
Q3: 0.04769
```

Very small margins co-occur with larger candidate sets. However, this dataset does **not** yet establish that score ambiguity independently causes pruning failure after controlling for branching.

Therefore the supported claim is:

```text
high branching → fixed-width pruning risk increases
```

while:

```text
score ambiguity → independent risk factor
```

remains a hypothesis for a larger controlled experiment.

---

## 8. Current empirical claim

The strongest defensible conclusion is:

> **Fixed-width pruning is usually adequate when the candidate set is small, but can irreversibly remove recoverable conflicting evidence in high-branching multi-hop reasoning. Broader near-optimal preservation substantially increases conflict-path survival in that regime, but its extra retained paths reduce external-gold precision and increase search cost. The pruning problem should therefore be optimized over preservation, retained-set validity, and cost rather than survival alone.**

The newest boundary-aware result suggests a more precise method direction:

> **Delay pruning specifically around the Top-K decision boundary instead of broadly retaining every candidate close to the global best.**

This is currently an exploratory extension, not yet the final claimed algorithm.

---

## 9. Next required experiment

1. Run boundary-aware Top-K on a larger iterative search set, not only frozen MAGIC candidates.
2. Compare Top-K, global Rashomon, relative-loss, boundary-aware, and no-prune at matched search budgets.
3. Report `survival + gold precision/recall/F1 + active/expansion cost` together.
4. Increase high-branching sample size and pre-register/fix epsilon before the final test split.
5. Repeat with one structural/path scorer to test scorer independence.
6. Only after preservation is established, pass surviving competing hypotheses to the later semantic/logical resolution stage.

Core files:

```text
scripts/evaluate_magic_conflict_preservation.py
scripts/evaluate_iterative_pruning_search_incremental.py
scripts/evaluate_iterative_pruning_relative_loss.py
results/magic_conflict_preservation_summary.json
.github/workflows/magic-conflict-preservation-ablation.yml
```
