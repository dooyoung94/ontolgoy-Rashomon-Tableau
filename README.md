# Boundary-Aware Delayed Pruning for Multi-Hop Knowledge Graph Reasoning

## Research claim

Multi-hop graph reasoning must prune candidate paths to control combinatorial growth. Fixed-width beam search solves the cost problem by retaining the top `K` paths, but its cutoff is purely cardinality-based: the `(K+1)`-th path is removed even when its score is nearly indistinguishable from the `K`-th path. Because pruning is irreversible, this can destroy evidence that a later semantic or logical verifier would need.

This project studies one focused question:

> **Can pruning be delayed only when the Top-K decision boundary is uncertain, reducing pruning-caused information loss without broadly retaining every near-optimal path?**

The current paper is about **Preservation**, not final truth resolution. Tableau/ontology reasoning is future `Resolve` work.

---

## 1. Search formulation

Let a query be `q`, graph be `G`, and active partial paths at depth `k` be `P_k`.

Expansion:

```text
C_(k+1) = Expand(P_k, G)
```

A scorer assigns each candidate path:

```text
s_theta(p,q) in [0,1]
```

The current WN18RR iterative experiment uses DeBERTa edge support and mean path score:

```text
s_theta(p,q) = (1 / |p|) * sum_e s_theta(e,q)
```

The scorer is held fixed across pruning policies. The experimental variable is the retention operator.

---

## 2. Pruning policies

### Fixed Top-K

```text
P_(k+1)^TopK = TopK(C_(k+1), s_theta, K)
```

This is the ToG-style fixed-beam control.

### Global additive Rashomon band

Let:

```text
s* = max_p s_theta(p,q)
```

Then:

```text
R_eps = {p in C : s_theta(p,q) >= s* - eps}
```

This preserves candidates close to the global best.

### Relative-loss Rashomon band

Define loss:

```text
L(p,q) = 1 - s_theta(p,q)
L*     = min_p L(p,q)
```

Retain:

```text
R_eps^loss = {p in C : L(p,q) <= (1+eps)L*}
```

Equivalently:

```text
s(p,q) >= s* - eps(1-s*)
```

This makes tolerance dependent on score scale.

### Proposed: Boundary-Aware Delayed Pruning

Sort candidate scores:

```text
s_(1) >= s_(2) >= ... >= s_(|C|)
```

For a fixed anchor budget `K`, define the Top-K cutoff:

```text
b_K = s_(K)
```

and retain:

```text
B_(K,delta) = {p in C : s_theta(p,q) >= b_K - delta}
```

when `|C| > K`; otherwise retain all candidates.

Interpretation:

```text
Top-K core
+
only paths that are nearly tied with the pruning boundary
```

The key distinction is not `fixed vs adaptive` in general. Recent work already uses adaptive pruning. The proposed principle is specifically **boundary uncertainty**: rank `K+1` should not be deleted solely because of cardinality when the scorer does not clearly separate it from rank `K`.

---

## 3. What the paper measures

### 3.1 Search Success

For query `i`:

```text
Success_i = 1[the retained search reaches target evidence within hop budget]
```

### 3.2 Pruning Regret

At depth `k`, let `C_ik` be candidates before pruning and `P_ik` the retained set. A partial path is viable if it can still reach the target within the remaining hop budget.

```text
PR_ik = 1[
  at least one viable path exists in C_ik
  AND no viable path remains in P_ik
]
```

Query-level pruning regret is one if this occurs at any depth.

### 3.3 Viable-prefix Survival

```text
VPS_k = post-pruning viable cases / pre-pruning viable cases
```

### 3.4 Retained-set validity

Keeping more states is not automatically better. For iterative WN18RR, a retained partial path is operationally valid when it can still reach the target within the remaining hop budget.

```text
ViabilityPrecision = viable retained paths / retained paths
ViabilityRecall    = viable retained paths / viable candidate paths
ViabilityF1        = harmonic mean(precision, recall)
```

For MAGIC, externally injected `perturb_triplet` provenance is used instead of graph reachability, giving benchmark-gold preservation precision/recall/F1.

### 3.5 Search Cost

Primary cost measures:

```text
Average Active Width
Average Expanded Candidates
NLI scoring calls
```

The paper therefore evaluates:

```text
Preservation / Search Success
        x
Retained-set Validity
        x
Search Cost
```

---

## 4. Cost-matched evaluation

Comparing `Top-5` with an adaptive method that keeps ten paths is not sufficient evidence.

The new iterative experiment therefore uses two fixed-width budget anchors:

```text
Anchor A: Top-3
Anchor B: Top-5
```

Adaptive families are swept:

```text
Global epsilon:   .01 / .03 / .05 / .10
Relative loss:    .10 / .25 / .50
Boundary delta:   .001 / .005 / .010 / .020 / .050
```

For each family and anchor, the setting with average active width nearest the anchor is identified. The comparison reports:

```text
Search-success delta
Pruning-regret delta
Viability precision / recall / F1 delta
Average-width gap
Expansion-cost gap
```

Important: hyperparameter matching on the evaluation set is exploratory. Final confirmatory evaluation must tune on development data and freeze the selected parameter before test evaluation.

Implementation:

```text
scripts/evaluate_iterative_pruning_budgeted.py
.github/workflows/wn18rr-iterative-pruning-budgeted.yml
```

Current execution:

```text
Run 32818825584
50 deterministic WN18RR 2-4 hop queries
```

---

## 5. Existing empirical evidence

### MAGIC external-gold conflict preservation

On 420 recoverable MAGIC conflict queries:

| Policy | Conflict survival | Gold precision | Gold F1 | Avg width |
|---|---:|---:|---:|---:|
| Top-3 | 94.76% | 59.38% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 70.54% | 1.79 |
| Global eps=.10 | 97.14% | 50.18% | 66.18% | 1.94 |
| Relative-loss eps=.25 | 83.81% | 74.26% | 78.66% | 1.13 |
| **Boundary Top-3 + .01** | **97.86%** | 55.30% | 70.67% | **1.77** |
| No pruning | 100% | 46.67% | 63.64% | 2.15 |

Boundary Top-3 rescued 13 recoverable conflict queries that fixed Top-3 lost, while Top-3 rescued none lost by the boundary rule. This result is exploratory because the boundary rule was introduced after inspecting earlier ablations.

High branching is the strongest current risk factor. For MAGIC queries with at least five candidate paths (`n=32`), Top-5 conflict survival falls to 75.0%, while global eps=.10 reaches 96.88%, but with much larger width and lower gold precision. This establishes why survival, validity, and cost must be reported together.

### Previous iterative WN18RR pilot

| Policy | Search success | Regret | Avg width |
|---|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 |
| Top-5 | 60% | 40% | 3.88 |
| Global eps=.10 | 40% | 60% | 3.62 |
| Relative-loss eps=.50 | **70%** | **30%** | 5.97 |

This showed that naive global score bands can fail and that score-scale calibration matters, but the relative-loss gain was purchased with substantially more active states. The new 50-query cost-matched experiment directly addresses that weakness.

---

## 6. Peer group

The paper should be compared against two groups rather than one leaderboard.

| Peer | Main mechanism | Why relevant | Difference from this work |
|---|---|---|---|
| **Think-on-Graph (ToG), ICLR 2024** | iterative KG beam search with repeated relation/entity pruning | canonical fixed-width graph-search reference | fixed Top-N boundary rather than explicit K/K+1 uncertainty |
| **Think-on-Graph 2.0, ICLR 2025** | iterative hybrid graph + context retrieval | stronger ToG-family KGQA system | broader retrieval architecture; not a pruning-policy isolation study |
| **Paths-over-Graph (PoG), 2024** | dynamic multi-hop exploration + three-stage pruning | path-level pruning peer | combines graph/LLM/PLM filtering rather than studying pruning regret directly |
| **FastToG, AAAI 2025** | community search + coarse/fine community pruning | efficiency-oriented graph pruning | prunes communities rather than testing boundary uncertainty of path beams |
| **Query-driven adaptive graph retrieval, Electronics 2026** | query complexity + path-score-distribution adaptive K | closest adaptive-pruning peer | adaptivity itself is therefore not our novelty; our target is boundary-induced irreversible loss |
| **Flow-RAG, KBS 2026** | distribution-aware adaptive pruning via score-distribution boundary | strongest recent adaptive-scale warning | learned flow/retrieval framework; our study isolates the pruning operator and measures pruning regret/retained validity |

Peer-group implication:

> **Do not claim “first adaptive pruning.”**

The defensible contribution is narrower:

> **formalize and measure pruning-caused information loss, then test whether uncertainty specifically at the Top-K cutoff is a useful delayed-pruning criterion under matched search cost.**

---

## 7. Direct-comparison metrics for a later KGQA benchmark

WN18RR tests search-policy mechanics but is not apples-to-apples with ToG-family KGQA. A direct peer experiment should use a shared benchmark such as WebQSP/CWQ and report:

| Dimension | Metrics |
|---|---|
| End-task | Exact Match / F1 / Hits@1 as appropriate |
| Evidence retrieval | gold path/supporting-fact recall, precision, F1 |
| Pruning | viable/gold path survival by depth, pruning regret |
| Efficiency | expanded nodes/paths, average beam width, LLM/NLI calls, context tokens, latency |
| Trade-off | success or answer F1 versus expansion/context budget; Pareto frontier |
| Robustness | results by hop depth, branching factor, score margin/ambiguity |

This avoids comparing our WN18RR search-success numbers directly with published KGQA answer accuracy.

---

## 8. Intended contribution

If the iterative cost-matched experiment confirms the current signal, the paper contribution becomes:

1. **Pruning Regret**: an explicit measure of irreversible loss caused by pruning when viable evidence existed before selection.
2. **Boundary-Aware Delayed Pruning**: retain Top-K plus only candidates whose score is indistinguishable from the K-th cutoff within `delta`.
3. **Validity-aware evaluation**: measure whether preserved paths remain operationally/gold valid rather than reporting candidate count or survival alone.
4. **Budget-matched analysis**: compare fixed and adaptive policies at similar active-search cost and report the success-validity-cost Pareto frontier.

The claim is deliberately not `Rashomon > Top-K`. It is:

> **A fixed cardinality boundary can be an unsafe decision rule when the scorer cannot confidently distinguish the K-th and adjacent candidates; selective delay at that boundary may reduce irreversible evidence loss more efficiently than broad global preservation.**
