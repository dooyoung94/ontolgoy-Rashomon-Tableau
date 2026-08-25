# Prune or Preserve? Preserving Competing Evidence in Multi-Hop KG Reasoning

## Core claim

Multi-hop reasoning can expose several plausible paths, including evidence that supports and contradicts the same claim. If one branch is removed during search, no downstream verifier can recover it.

This project therefore studies a narrower problem than final conflict resolution:

> **When is pruning unsafe, and can near-optimal hypothesis retention preserve competing evidence until a later verification stage?**

```text
Query / Claim
    ↓
Multi-hop expansion
    ↓
Semantic / structural scorer
    ↓
Competing candidate paths
    ↓
┌───────────────────────────┐
│ Fixed Top-K pruning       │
│            vs             │
│ Near-optimal preservation │
└───────────────────────────┘
    ↓
Preserved reasoning state
    ↓
Future work: semantic/logical resolution
```

The current paper is **Preserve**. Tableau/ontology-based conflict resolution is a follow-up **Resolve** stage.

---

## 1. Relation to ToG

ToG already performs repeated graph search and pruning and keeps multiple candidates. Our distinction is not `single path vs multiple paths`.

For candidate set `C_k` and scorer `s_theta`:

```text
Fixed Top-K:
P_k = TopK(C_k, s_theta, K)
```

A Rashomon-inspired score-band policy instead keeps candidates sufficiently close to the current best:

```text
s* = max_p s_theta(p,q)
R_epsilon = {p | s_theta(p,q) >= s* - epsilon}
```

The research question is therefore:

```text
How many paths should survive?
        ↓
not a constant answer
        ↓
Does risk depend on branching / score ambiguity?
```

We do **not** claim that Rashomon pruning is uniformly superior to Top-K. The executed experiments show that the useful regime is more specific.

---

## 2. What is being preserved?

For claim `q`, suppose the search space contains evidence supporting the claim and a contradictory path supplied by an external benchmark.

The current paper does not decide which side is true. It measures whether the contradictory/competing evidence remains available after pruning.

For an externally-gold conflict path family `G_i`:

```text
ConflictPathSurvival_i = 1[selected_paths_i intersects G_i]
ConflictInformationLoss_i = 1 - ConflictPathSurvival_i
```

The no-pruning condition establishes recoverability first. A query is included in the primary pruning analysis only when at least one externally-gold conflict path existed before pruning.

This separates:

```text
retrieval failure
from
pruning-caused information loss
```

---

## 3. Dataset roles

| Dataset | Role |
|---|---|
| **WN18RR** | generic premature-pruning and iterative-search stress test |
| **MAGIC multi-hop conflict** | external-gold conflicting-evidence preservation test |

WN18RR is not treated as a strong contradiction benchmark. MAGIC supplies the key conflict-bearing evaluation because its released `original_triplet` and paired `perturb_triplet` define the competing evidence independently of DeBERTa.

---

## 4. DeBERTa is retained as a semantic verifier

DeBERTa is **not** the proposed pruning algorithm and is not claimed to be a competitive generic WN18RR KGC model.

It remains useful as a semantic path verifier producing:

```text
Support / Contradiction / Unresolved
```

Existing executed MAGIC result (`588 rows / 1,056 queries`):

| Metric | Weak lexical prior | DeBERTa | Gain |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71pp** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68pp** |
| Structured exact LOC | 7.14% | **15.48%** | **+8.33pp** |

Source run: `32730398659`  
Source artifact: `9521415589`

This result is retained as evidence that DeBERTa contributes meaningful semantic verification when useful candidate paths are available. It is **not** evidence that DeBERTa alone solves multi-hop search.

---

## 5. WN18RR: relation-hypothesis diagnostic

Frozen DeBERTa scores on the executed 50-row 2–4 hop subset:

| Policy | Gold survival | Avg active hypotheses |
|---|---:|---:|
| Top-1 | 16% | 1.00 |
| Top-3 | 32% | 3.00 |
| Top-5 | 40% | 5.00 |
| Rashomon eps=.05 | **42%** | 3.82 |
| Rashomon eps=.10 | **58%** | 5.08 |
| No pruning | 100% | 11.00 |

This showed a positive **candidate-retention signal**, but it was not iterative search.

Stored:

```text
results/wn18rr_pruning_policy_ablation_50.json
```

---

## 6. WN18RR: iterative-search negative result

We then moved the pruning operator inside repeated 2–4 hop search.

10-query incremental pilot:

| Policy | Search success | Query pruning regret | Avg width | Avg expanded |
|---|---:|---:|---:|---:|
| Top-1 | 20% | 80% | 1.00 | 10.9 |
| **Top-3** | **60%** | **40%** | 2.67 | 21.3 |
| **Top-5** | **60%** | **40%** | 3.88 | 28.1 |
| Additive Rashomon .05 | 40% | 60% | 2.65 | 23.7 |
| Additive Rashomon .10 | 40% | 60% | 3.59 | 28.5 |

This is an important negative result:

> **A raw best-minus-epsilon rule is not automatically better.**

When scorer values are poorly calibrated or confidently wrong, a score-band policy can also remove viable paths. The paper therefore treats scorer calibration and candidate-space regime as part of the pruning problem rather than hiding them.

---

## 7. MAGIC conflict-evidence preservation — executed result

New ablation run: `32815760029`  
Artifact: `9551317704`  
Digest: `sha256:f94720659fe26f1634288ad8c572fdd73ce311b9a791d9ba248aef78c281b85a`

Protocol:

- source: frozen DeBERTa MAGIC path scores;
- 588 rows / 1,056 queries;
- 618 queries had at least one candidate path;
- **420 queries had an externally-gold MAGIC conflict path recoverable before pruning**;
- gold definition: `perturb_triplet` provenance, attached only after DeBERTa scoring;
- pruning score: `support + contradiction = 1 - unresolved`, so selection does not privilege either side.

### 7.1 Overall recoverable set: n=420

| Policy | Gold conflict-path survival ↑ | Conflict information loss ↓ | Avg selected paths |
|---|---:|---:|---:|
| Top-1 | 80.71% | 19.29% | 1.00 |
| **Top-3** | **94.76%** | 5.24% | 1.60 |
| **Top-5** | **98.10%** | **1.90%** | 1.79 |
| Rashomon eps=.03 | 93.10% | 6.90% | 1.60 |
| Rashomon eps=.05 | 94.76% | 5.24% | 1.75 |
| Rashomon eps=.10 | 97.14% | 2.86% | 1.94 |
| No pruning | 100% | 0% | 2.15 |

**Conclusion:** on the whole recoverable set, fixed Top-5 is already extremely strong. Rashomon is **not uniformly superior**.

### 7.2 High-branching regime

The main signal appears when the candidate set becomes crowded.

| Recoverable subset | Top-3 | Top-5 | Rashomon .03 | Rashomon .05 | Rashomon .10 |
|---|---:|---:|---:|---:|---:|
| paths >=3, n=81 | 72.84% | 90.12% | 76.54% | 83.95% | **91.36%** |
| paths >=4, n=46 | 52.17% | 82.61% | 82.61% | 84.78% | **93.48%** |
| paths >=5, n=32 | 37.50% | 75.00% | 81.25% | 84.38% | **96.88%** |

This is the strongest result for the current thesis.

For `paths >= 5`:

```text
Top-3:        37.5% survival
Top-5:        75.0% survival
Rashomon .10: 96.9% survival
No pruning:  100.0%
```

The gain is not free: Rashomon .10 retains 8.41 paths on average in this subset versus 5.0 for Top-5. The paper therefore studies a **preservation-cost trade-off**, not accuracy alone.

Stored summary:

```text
results/magic_conflict_preservation_summary.json
```

Reproduction:

```text
scripts/evaluate_magic_conflict_preservation.py
.github/workflows/magic-conflict-preservation-ablation.yml
```

---

## 8. Current empirical claim

The evidence now supports a narrower, more defensible claim:

> **Fixed-width pruning causes measurable loss of recoverable conflicting evidence. The risk becomes much larger as candidate branching increases. Near-optimal score-band retention can substantially reduce that loss in high-branching regimes, but it is not universally superior and requires additional search cost and well-behaved scores.**

So the contribution is not:

```text
Rashomon > Top-K everywhere
```

It is:

```text
pruning risk is regime-dependent
        +
high branching makes fixed width brittle
        +
adaptive preservation can protect competing evidence
```

---

## 9. Current hypotheses

### H1 — Premature pruning exists

Recoverable evidence can disappear solely because of pruning.

```text
ConflictInformationLoss(Top-K) > 0
```

### H2 — Branching amplifies pruning risk

```text
ConflictInformationLoss(Top-K | branching high)
>
ConflictInformationLoss(Top-K | branching low)
```

The MAGIC result directly supports this direction: Top-3 survival drops from 94.76% overall to 37.50% when at least five candidate paths compete.

### H3 — Adaptive preservation helps in the difficult regime

In high-branching candidate sets, near-optimal score-band retention can preserve more externally-gold conflict evidence than the fixed-width baseline.

### H4 — Preservation has a cost

Any gain must be reported jointly with active-path/expansion/model-scoring cost.

### H5 — Semantic scoring remains imperfect

DeBERTa is useful on MAGIC, but scorer error/calibration can reverse the benefit of a pruning rule, as seen in the iterative WN18RR pilot.

---

## 10. What this paper does NOT claim

- It does not determine which conflicting claim is ultimately true.
- It does not claim full ToG superiority.
- It does not claim Rashomon pruning is always better than fixed Top-K.
- It does not claim DeBERTa is a strong standalone WN18RR relation predictor.
- It does not use Tableau as the current paper's main contribution.

The next paper can take the preserved competing evidence and perform:

```text
Preserved evidence
→ semantic S/C/U verification
→ possible worlds
→ ontology / Tableau constraints
→ conflict resolution
```

**Preserve first. Resolve later.**
