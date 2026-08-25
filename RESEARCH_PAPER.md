# Prune or Preserve? Rashomon Delayed Pruning for Multi-Hop Knowledge Graph Reasoning

## Abstract

Multi-hop knowledge-graph reasoning systems repeatedly expand candidate paths and prune them to control search cost. Fixed-width beam pruning is effective for efficiency, but it can remove plausible hypotheses when several candidates receive nearly indistinguishable scores. This paper studies a narrower question: **when should a multi-hop reasoner prune?**

We formulate pruning as a hypothesis-retention problem. Given candidate paths or relation hypotheses scored by a semantic or structural model, fixed Top-K pruning retains a constant number of hypotheses, whereas the proposed Rashomon delayed-pruning rule retains every hypothesis whose score lies within epsilon of the current best score, optionally subject to a computational cap. The resulting active-set size therefore adapts to score ambiguity rather than being fixed in advance.

A first diagnostic experiment reuses the exact DeBERTa scores from an executed 50-example WN18RR 2-4 hop relation benchmark and changes only the pruning policy. Gold survival is 16% for Top-1, 32% for fixed Top-3, and 40% for fixed Top-5. Rashomon pruning with epsilon=0.05 reaches 42% survival with 3.82 active hypotheses on average, slightly exceeding Top-5 while retaining 1.18 fewer hypotheses. With epsilon=0.10, gold survival reaches 58% with an average width of 5.08, compared with 40% at width 5 for fixed Top-5. These results are preliminary relation-hypothesis diagnostics, not yet a full iterative ToG comparison. The next experiment evaluates the policy inside repeated multi-hop search using gold-path survival, pruning regret, search cost, and final task accuracy.

---

## 1. Research Question

The study asks:

> Does fixed-width early pruning discard plausible reasoning hypotheses too aggressively, and can a near-optimal Rashomon retention rule reduce pruning regret at comparable search cost?

The contribution is **not** that multi-hop search should maintain multiple paths; beam-search systems already do this. The proposed distinction is the criterion used to decide which hypotheses survive.

```text
Fixed-width pruning
    keep exactly K highest-ranked hypotheses

Rashomon delayed pruning
    keep every hypothesis currently indistinguishable
    from the best within epsilon
```

---

## 2. Multi-Hop Search

For a query q and graph G, let P_k be the active partial-path set after depth k.

Expansion produces:

```text
C_(k+1) = Expand(P_k, G)
```

Each candidate p receives a score:

```text
s_theta(p,q)
```

The scorer is interchangeable. It may be a semantic model such as DeBERTa, a structural KGE model, a path-reasoning model, or an LLM relevance scorer.

The paper therefore separates:

```text
scoring model
from
pruning policy
```

This separation is essential for controlled comparison.

---

## 3. Baseline: Fixed-Width Pruning

A fixed beam of width K retains:

```text
P_(k+1)^TopK = TopK(C_(k+1), s_theta, K)
```

Its cardinality is fixed by design:

```text
|P_(k+1)^TopK| <= K
```

This is efficient, but ranking uncertainty is ignored. The K-th and (K+1)-th hypotheses are treated differently even if their scores are almost identical.

Example:

```text
p1  0.91
p2  0.90
p3  0.89
p4  0.88
```

With K=3, p4 is removed despite being only 0.03 below the best score.

---

## 4. Proposed Method: Rashomon Delayed Pruning

Let the best candidate score at depth k be:

```text
s*_k = max_p s_theta(p,q)
```

The Rashomon active set is:

```text
R_epsilon^k(q) = {
  p in C_k
  | s_theta(p,q) >= s*_k - epsilon
}
```

The principle is:

> Do not prune a hypothesis if the current scorer cannot separate it from the best hypothesis by more than epsilon.

Unlike Top-K, the number of retained hypotheses adapts to score ambiguity.

Clear score distribution:

```text
0.95, 0.62, 0.44, 0.21
```

A small epsilon may retain only one path.

Ambiguous distribution:

```text
0.91, 0.90, 0.89, 0.88
```

The same epsilon may retain several paths.

For bounded computation, an optional cap can be imposed:

```text
|R_epsilon^k| <= B_max
```

The epsilon rule remains the selection principle; B_max is only a safety constraint.

---

## 5. DeBERTa's Role

DeBERTa is not the proposed algorithm. It is the first scorer used to instantiate s_theta.

For a multi-hop evidence path p and candidate relation r, DeBERTa estimates semantic support:

```text
s_D(p,r) = Support_DeBERTa(p,r)
```

The pruning policy then operates on these scores.

Controlled experiments therefore compare:

```text
same DeBERTa scores + Top-K
vs
same DeBERTa scores + Rashomon
```

A stronger structural/path scorer must later be substituted for DeBERTa to test whether observed gains are scorer-independent.

---

## 6. Pruning Regret

Let p*_(1:k) denote the gold reasoning-path prefix at depth k.

Gold path survival is:

```text
Survive_k = 1[p*_(1:k) is retained after pruning]
```

If the gold hypothesis exists before pruning but is removed by the pruning operator:

```text
PR_k = 1[
  p*_(1:k) in C_k
  AND
  p*_(1:k) not in P_k
]
```

Dataset-level pruning regret is:

```text
PruningRegret_k = mean_i PR_k^(i)
```

The primary hypothesis is:

```text
PruningRegret_Rashomon < PruningRegret_TopK
```

subject to a reasonable increase in search cost.

---

## 7. Search Cost

Retaining more hypotheses is not free. Search efficiency is measured separately from accuracy/survival.

Active-state cost:

```text
Cost_active = sum_k |P_k|
```

Expansion cost:

```text
Cost_expand = sum_k |C_k|
```

For LLM-based scoring, token/call cost should also be recorded.

The paper therefore studies a trade-off rather than survival alone:

```text
Gold survival / pruning regret
vs
search cost
```

---

## 8. Executed WN18RR Diagnostic

### 8.1 Protocol

Source workflow run: `32799621678`  
Source artifact: `9546119681`  
Dataset: WN18RR 50-example hard 2-4 hop relation subset  
Candidate relations: 11  
Scorer: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`

The exact executed DeBERTa support scores are reused. Gold labels are used only after pruning for evaluation.

This experiment changes only the **relation-hypothesis retention policy**. It is not yet an iterative ToG path-search benchmark.

### 8.2 Overall result

| Policy | Gold survival | Pruning regret | Avg active hypotheses |
|---|---:|---:|---:|
| Top-1 | 16% | 84% | 1.00 |
| **Top-3 fixed width** | **32%** | 68% | 3.00 |
| Top-5 fixed width | 40% | 60% | 5.00 |
| Threshold >= 0.7 | 70% | 30% | 7.08 |
| Threshold >= 0.5 | 78% | 22% | 8.40 |
| Rashomon eps=.01 | 16% | 84% | 1.98 |
| Rashomon eps=.03 | 26% | 74% | 3.22 |
| **Rashomon eps=.05** | **42%** | **58%** | **3.82** |
| **Rashomon eps=.10** | **58%** | **42%** | **5.08** |
| No pruning | 100% | 0% | 11.00 |

### 8.3 Cost-matched interpretation

Against fixed Top-3:

```text
Rashomon eps=.05
survival gain = +10pp
average active-set increase = +0.82
```

Against fixed Top-5:

```text
Rashomon eps=.05
survival gain = +2pp
average active-set change = -1.18
```

Thus eps=.05 is Pareto-better than Top-5 in this diagnostic: it preserves slightly more gold while keeping fewer hypotheses on average.

A closer width-matched comparison is:

```text
Top-5:
  survival = 40%
  avg width = 5.00

Rashomon eps=.10:
  survival = 58%
  avg width = 5.08
```

This produces +18pp survival for only +0.08 average active hypotheses.

### 8.4 Hop-level signal

For epsilon=.05:

| Hop | n | Top-1 survival | Rashomon survival | Avg Rashomon size |
|---:|---:|---:|---:|---:|
| 2 | 19 | 5.3% | 36.8% | 5.26 |
| 3 | 23 | 30.4% | 47.8% | 2.91 |
| 4 | 8 | 0.0% | 37.5% | 3.00 |

This suggests that near-optimal retention may protect hypotheses that would otherwise be removed under aggressive ranking, but the sample is too small to establish a monotonic hop-depth effect.

Stored result:

```text
results/wn18rr_pruning_policy_ablation_50.json
```

Reproduction:

```text
scripts/evaluate_pruning_policies.py
```

---

## 9. Relationship to ToG

The proposed method is not contrasted with ToG as "single path versus multiple paths." ToG already maintains a beam and repeatedly performs search and pruning.

The distinction is:

```text
ToG-style fixed-width retention:
  relative rank determines survival

Rashomon delayed pruning:
  near-optimality determines survival
```

Therefore the correct empirical comparison is not the current Top-1 pilot alone. It must place both pruning operators inside the same repeated search process with the same scorer and expansion rules.

The current 50-row result is evidence for the **premature-pruning hypothesis**, not evidence of superiority over full ToG.

---

## 10. Hypotheses

### H1 — Gold survival

```text
GoldSurvival(Rashomon) > GoldSurvival(Fixed Top-K)
```

at comparable average active-set size.

### H2 — Pruning regret

```text
PruningRegret(Rashomon) < PruningRegret(Fixed Top-K)
```

because near-tied hypotheses are not removed solely by a rank boundary.

### H3 — Efficiency

The survival gain remains useful after accounting for active-state, expansion, and model-scoring cost.

### H4 — Scorer independence

The advantage, if real, persists with at least one stronger structural/path scorer rather than appearing only with DeBERTa.

---

## 11. Required Next Experiment

Implement both policies inside identical iterative multi-hop search.

```text
Query
  ↓
Expand
  ↓
Score
  ↓
Top-K OR Rashomon
  ↓
Expand next hop
  ↓
...
```

Conditions:

```text
Top-1
Top-3
Top-5
absolute threshold
Rashomon epsilon sweep
No pruning
```

At each depth report:

```text
Gold Path Survival@k
Pruning Regret@k
Active hypotheses@k
Expanded hypotheses@k
Final relation / QA accuracy
Runtime and scoring cost
```

Then repeat using a stronger KGE/path scorer.

---

## 12. Current Evidence Boundary

Supported now:

- fixed-width policy materially changes gold survival under identical DeBERTa scores;
- epsilon-based retention yields an adaptive active-set size;
- epsilon=.05 exceeds Top-5 survival while using fewer hypotheses on average in the current 50-row diagnostic;
- epsilon=.10 substantially exceeds Top-5 survival at nearly identical average width.

Not supported yet:

- full ToG superiority;
- iterative multi-hop path-pruning advantage;
- final task-accuracy improvement;
- scorer-independent gain;
- statistically robust conclusions on larger datasets.

The paper will claim only what these controlled experiments establish.
