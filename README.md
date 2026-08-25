# Rashomon Delayed Pruning for Multi-Hop KG Reasoning

## Core question

**Does fixed-width early pruning discard plausible reasoning hypotheses too aggressively, and can a Rashomon-style near-optimality rule reduce pruning regret at comparable search cost?**

This repository is now focused on one problem: **pruning policy in multi-hop knowledge-graph reasoning**.

```text
Query / missing relation q=(h,?,t)
        ↓
Multi-hop search / candidate hypotheses
        ↓
Scorer s_theta
(DeBERTa first; KGE/path/LLM interchangeable)
        ↓
┌─────────────────────────────┐
│ Fixed-width Top-K pruning   │
│ vs                          │
│ Rashomon delayed pruning    │
└─────────────────────────────┘
        ↓
Next-hop search
        ↓
Gold survival / pruning regret / cost
```

Tableau, UMLS logic validation, and MAGIC downstream reasoning are no longer part of the core paper. They are follow-up directions.

## 1. Difference from ToG-style search

Both methods perform repeated multi-hop search. The difference is **the operator that decides which hypotheses survive to the next step**.

Fixed-width pruning:

```text
P_(k+1)^TopK = TopK(Expand(P_k,G), s_theta, K)
```

Rashomon delayed pruning:

```text
s*_k = max_p s_theta(p,q)

P_(k+1)^R = {
  p in Expand(P_k,G)
  | s_theta(p,q) >= s*_k - epsilon
}
```

Optional computational cap:

```text
|P_(k+1)^R| <= B_max
```

The distinction is therefore:

```text
Fixed cardinality
vs
score-ambiguity-adaptive cardinality
```

The method does not claim that keeping multiple paths is new. ToG already keeps a beam. The hypothesis is narrower: **near-optimal hypotheses that the current scorer cannot reliably distinguish should not be removed merely because a fixed beam is full.**

## 2. Scorer role

The pruning policy is scorer-agnostic.

```text
s_theta = DeBERTa semantic score
s_theta = KGE structural score
s_theta = path-reasoning score
s_theta = LLM relevance score
```

DeBERTa is the first diagnostic scorer. It is used to measure semantic compatibility between multi-hop evidence and candidate relations. It is not claimed as a competitive WN18RR KGC model.

## 3. Evaluation metrics

For gold hypothesis prefix p*_(1:k):

```text
GoldSurvival_k = 1[p*_(1:k) survives pruning]
```

Pruning regret:

```text
PR_k = 1[
  gold was present before pruning
  AND gold was removed by pruning
]
```

Dataset-level pruning regret is the mean of PR_k.

Search cost is measured by the number of active/expanded hypotheses:

```text
Cost = sum_k |P_k|
```

Primary trade-off:

```text
Gold survival / pruning regret
vs
search cost
```

## 4. Executed 50-row WN18RR pruning diagnostic

Source scorer run: `32799621678`  
Source artifact: `9546119681`  
Dataset: WN18RR hard 2-4 hop relation subset  
Scorer: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`  
Candidate relations: 11

The exact executed DeBERTa support scores were reused. Only the pruning policy changed.

**Important scope:** this is currently a **relation-hypothesis pruning diagnostic**, not yet a full iterative ToG path-search experiment.

| Policy | Gold survival | Pruning regret | Avg active hypotheses |
|---|---:|---:|---:|
| Top-1 | 16% | 84% | 1.00 |
| **Top-3 / ToG-style fixed width** | **32%** | 68% | 3.00 |
| Top-5 | 40% | 60% | 5.00 |
| Threshold >= 0.7 | 70% | 30% | 7.08 |
| Threshold >= 0.5 | 78% | 22% | 8.40 |
| Rashomon eps=0.01 | 16% | 84% | 1.98 |
| Rashomon eps=0.03 | 26% | 74% | 3.22 |
| **Rashomon eps=0.05** | **42%** | **58%** | **3.82** |
| **Rashomon eps=0.10** | **58%** | **42%** | **5.08** |
| No pruning | 100% | 0% | 11.00 |

### Key comparisons

```text
Rashomon eps=.05 vs Top-3
Gold survival: 42% vs 32%  = +10pp
Avg hypotheses: 3.82 vs 3.00 = +0.82
```

```text
Rashomon eps=.05 vs Top-5
Gold survival: 42% vs 40%  = +2pp
Avg hypotheses: 3.82 vs 5.00 = -1.18
```

In this pilot, eps=.05 **dominates Top-5 on both measured axes**: slightly higher gold survival while retaining fewer hypotheses on average.

```text
Rashomon eps=.10 vs Top-5
Gold survival: 58% vs 40%  = +18pp
Avg hypotheses: 5.08 vs 5.00 = +0.08
```

This is the strongest preliminary signal for the new research direction.

### Hop-level signal for eps=.05

| Hop | n | Top-1 survival | Rashomon eps=.05 survival | Avg Rashomon size |
|---:|---:|---:|---:|---:|
| 2 | 19 | 5.3% | 36.8% | 5.26 |
| 3 | 23 | 30.4% | 47.8% | 2.91 |
| 4 | 8 | 0.0% | 37.5% | 3.00 |

Stored result:

```text
results/wn18rr_pruning_policy_ablation_50.json
```

Reproduction script:

```text
scripts/evaluate_pruning_policies.py
```

## 5. What is proven vs not proven

**Supported by the current 50-row diagnostic:**

- Top-1 is an overly aggressive retention policy for these DeBERTa scores.
- Fixed Top-3 improves survival from 16% to 32%.
- Rashomon eps=.05 improves survival further to 42% with 3.82 active hypotheses on average.
- Rashomon eps=.05 retains slightly more gold than Top-5 while retaining fewer hypotheses on average.
- At approximately the same average width as Top-5, eps=.10 retains substantially more gold (58% vs 40%).

**Not proven yet:**

- superiority over the full ToG algorithm;
- iterative gold-path survival at every search depth;
- end-to-end QA / relation-prediction accuracy improvement;
- scorer-independent gains with RotatE, PathCon-style, or LLM scoring;
- full search-cost/token-cost advantage.

## 6. Next experiment

The next experiment must implement the pruning policy **inside iterative multi-hop search**.

Controlled comparison with identical scorer and expansion rules:

```text
Top-1
Top-3 fixed beam
Top-5 fixed beam
absolute threshold
Rashomon eps
No pruning
```

Measure at every depth:

```text
Gold Path Survival@k
Pruning Regret@k
Active hypotheses@k
Expanded triples/path count
Final answer accuracy
```

Then repeat with a stronger structural/path scorer to test whether the effect is scorer-independent.

## 7. Core files

```text
scripts/evaluate_pruning_policies.py
scripts/evaluate_multihop_relation_completion.py
src/rashomon_tableau/kg_multihop_benchmark.py
results/wn18rr_pruning_policy_ablation_50.json
```
