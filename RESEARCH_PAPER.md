# Boundary-Aware Delayed Pruning for Multi-Hop Knowledge Graph Reasoning

## Abstract

Multi-hop knowledge-graph reasoning requires aggressive search-space control. Fixed-width beam search is a common solution: after each expansion, only the highest-scoring `K` paths survive. The rule is efficient but creates an irreversible cardinality boundary. A path ranked `K+1` is removed even when its score is nearly indistinguishable from rank `K`, although later hops may reveal that the removed path was the only viable or contradictory evidence chain. This work studies **pruning-caused information loss** separately from final answer generation and asks whether pruning should be delayed specifically when the score boundary itself is uncertain.

We formalize **Pruning Regret**, which occurs when at least one viable reasoning prefix exists before selection but no viable prefix remains afterward. We compare fixed Top-K beam search with global near-optimal score bands, relative-loss bands, and a proposed **Boundary-Aware Delayed Pruning (BADP)** operator. BADP preserves the Top-K core and additionally retains only candidates whose score lies within `delta` of the K-th cutoff. Unlike broad global preservation, the operator targets the actual irreversible decision boundary. Evaluation considers three axes jointly: evidence/search survival, retained-set validity, and search cost.

Existing experiments motivate the formulation. On 420 recoverable MAGIC multi-hop conflict queries, fixed Top-3 preserves 94.76% of externally identified conflict paths, while an exploratory boundary-aware Top-3 rule reaches 97.86% with average retained width increasing from 1.60 to 1.77. Broad global retention obtains high survival in high-branching cases but also retains substantially more non-gold paths. A prior 10-query iterative WN18RR pilot further shows that a naive global score band can underperform Top-K and that scale-aware retention can recover search success only at additional cost. The main confirmatory direction is therefore not “adaptive pruning is better,” since recent graph-retrieval work already uses adaptive pruning. The narrower hypothesis is that **uncertainty at the Top-K cutoff is a distinct source of irreversible search error and can be handled by selective delayed commitment under a matched search budget**.

---

## 1. Research Question

Given a graph `G`, query `q`, and a sequence of multi-hop candidate expansions, the study asks:

> **When the scorer cannot clearly distinguish the K-th path from adjacent candidates, can selective delay of the Top-K pruning decision reduce pruning regret at comparable search cost?**

The paper separates two stages:

```text
Current study: Preserve viable / competing evidence during search
Future study:  Resolve competing evidence semantically or logically
```

The contribution is therefore about the **search-state transition operator**, not Tableau reasoning, final truth resolution, or a new semantic encoder.

---

## 2. Problem Formulation

Let the knowledge graph be

```text
G = (V,E,R)
```

and let `P_k` denote the active partial paths after depth `k`.

### 2.1 Expansion

At depth `k+1`:

```text
C_(k+1) = Expand(P_k, G)
```

where `C_(k+1)` is the set of candidate extensions before pruning.

### 2.2 Path scoring

A scorer assigns:

```text
s_theta(p,q) in [0,1]
```

The current iterative WN18RR implementation uses DeBERTa support for each newly explored edge and aggregates path evidence as:

```text
s_theta(p,q) = (1 / |p|) sum_(e in p) s_theta(e,q)
```

The scorer is identical for every pruning policy in a comparison. This isolates the effect of the retention operator.

---

## 3. Retention Operators

### 3.1 Fixed-width Top-K

Sort candidates so that:

```text
s_(1) >= s_(2) >= ... >= s_(|C|)
```

Fixed-width pruning retains:

```text
T_K(C) = {p_(1), ..., p_(min(K,|C|))}
```

or equivalently:

```text
P_(k+1)^TopK = TopK(C_(k+1), s_theta, K)
```

The cutoff is determined by cardinality alone.

### 3.2 Global additive near-optimality

Let:

```text
s* = max_(p in C) s_theta(p,q)
```

Then:

```text
R_eps(C) = {p in C : s_theta(p,q) >= s* - eps}
```

This is the original Rashomon-inspired ablation. It preserves candidates near the global best, but can either become too narrow when scores are poorly calibrated or too broad when many candidates cluster near the maximum.

### 3.3 Relative-loss near-optimality

Define:

```text
L(p,q) = 1 - s_theta(p,q)
L*     = min_(p in C) L(p,q)
```

Retain:

```text
R_eps^loss(C) = {p in C : L(p,q) <= (1+eps)L*}
```

Since `L*=1-s*`, the equivalent score threshold is:

```text
s_theta(p,q) >= s* - eps(1-s*)
```

This makes the allowed score gap depend on the current confidence scale.

### 3.4 Proposed Boundary-Aware Delayed Pruning

Let `b_K(C)` be the K-th ranked score:

```text
b_K(C) = s_(K),  if |C| >= K
```

For uncertainty tolerance `delta >= 0`:

```text
B_(K,delta)(C)
  = {p in C : s_theta(p,q) >= b_K(C) - delta},  if |C| > K
  = C,                                           otherwise
```

Thus:

```text
B_(K,0) contains the Top-K core
```

and `delta>0` delays deletion only for candidates adjacent to the actual beam boundary.

An equivalent decomposition is:

```text
B_(K,delta)(C)
= T_K(C)
  union
  {p_(j), j>K : s_(K)-s_(j) <= delta}
```

This formulation captures the intended decision rule directly:

> A candidate should not be irreversibly deleted solely because it is ranked `K+1` when the scorer provides insufficient separation from rank `K`.

### 3.5 Boundary uncertainty

Define the immediate boundary margin:

```text
Delta_K(C) = s_(K) - s_(K+1)
```

for `|C|>K`.

Small `Delta_K` indicates a near-tie at the pruning decision. BADP can therefore also be interpreted as a rank-boundary uncertainty rule.

The current implementation uses score inclusion `s >= s_(K)-delta`, which may preserve more than `K+1` paths if several candidates cluster near the cutoff.

---

## 4. Failure Mode: Pruning Regret

A partial path is **viable** at depth `k` if it can still reach the target evidence/entity within the remaining hop budget.

Let:

```text
v_k(p)=1
```

when path `p` is viable, otherwise `0`.

For candidate set `C_k` and retained set `P_k`, define depth-level pruning regret:

```text
PR_(i,k)
 = 1[
      exists p in C_(i,k) with v_k(p)=1
      AND
      for all p in P_(i,k), v_k(p)=0
    ]
```

Query-level pruning regret is:

```text
QPR_i = 1[max_k PR_(i,k) = 1]
```

and dataset regret rate:

```text
QPR = (1/N) sum_i QPR_i
```

This metric has an important interpretation under frozen graph, scorer, hop budget, and candidate generation:

```text
viable evidence existed before pruning
+
only the retention policy changed
+
viable evidence disappeared afterward
=
pruning-caused irreversible information loss
```

---

## 5. Retained-Set Validity

Survival alone is insufficient because no-pruning trivially maximizes survival.

### 5.1 Iterative graph-search validity

At every pruning step define:

```text
V_C = {p in C : v_k(p)=1}
V_P = {p in P : v_k(p)=1}
```

Then:

```text
ViabilityPrecision = |V_P| / |P|
ViabilityRecall    = |V_P| / |V_C|
ViabilityF1        = 2PR / (P+R)
```

These quantify whether the retained search state contains useful prefixes rather than only additional states.

### 5.2 MAGIC external-gold validity

For the MAGIC conflict benchmark, viability is evaluated independently using released conflict provenance. Let `G_i^-` be the externally identified perturb-path family.

A query is recoverable when:

```text
G_i^- intersect C_i != empty
```

Conflict Path Survival:

```text
CPS_i = 1[G_i^- intersect P_i != empty]
```

Conflict Information Loss:

```text
CIL_i = 1 - CPS_i
```

and retained-set gold precision/recall are:

```text
Precision_gold = |P intersect G^-| / |P|
Recall_gold    = |P intersect G^-| / |G^-|
```

Gold comes from MAGIC provenance and is attached after DeBERTa scoring, avoiding scorer-defined evaluation labels.

---

## 6. Search Cost and Budget Matching

Let:

```text
W = (1/K_steps) sum_k |P_k|
```

be mean active width and:

```text
X = sum_k |C_k|
```

be total candidate expansions.

We also record unique semantic scoring calls.

The optimization is multi-objective:

```text
maximize SearchSuccess / EvidenceSurvival
maximize RetainedValidity
minimize ActiveWidth / ExpansionCost
```

### 6.1 Budget anchors

We use fixed beams as cost anchors:

```text
A_3 = Top-3
A_5 = Top-5
```

For each adaptive policy family `F`, parameter grid `Lambda_F`, and anchor `A`, choose the exploratory width-matched configuration:

```text
lambda*_F(A)
 = argmin_(lambda in Lambda_F)
   | W(F_lambda) - W(A) |
```

Tie-breaking uses expansion-cost proximity.

The main comparison reports:

```text
Delta Success
Delta Pruning Regret
Delta Viability Precision
Delta Viability Recall
Delta Viability F1
Delta Active Width
Delta Expanded Candidates
```

A Pareto frontier of search success versus expansion cost is also reported.

**Methodological safeguard:** parameter selection on the same evaluation set is exploratory only. A final paper must tune `epsilon/delta` on a development split and freeze them before confirmatory test evaluation.

---

## 7. Hypotheses

### H1 — Fixed-width pruning produces measurable regret

```text
QPR_TopK > 0
```

when viable prefixes exist before pruning.

### H2 — Branching increases fixed-width brittleness

For larger pre-pruning candidate cardinality `|C_k|`, the probability of Top-K pruning regret increases.

```text
P(PR=1 | |C| large) > P(PR=1 | |C| small)
```

This is strongly suggested by the current MAGIC analysis.

### H3 — Boundary uncertainty identifies unsafe Top-K decisions

For small boundary margin:

```text
Delta_K = s_(K)-s_(K+1)
```

fixed Top-K should incur more avoidable regret than when the boundary is clearly separated.

This remains a hypothesis until controlled iterative results are sufficiently large.

### H4 — Boundary-aware delay is more cost-efficient than broad global preservation

At comparable active-search budget:

```text
QPR_BADP <= QPR_GlobalBand
```

and/or:

```text
SearchSuccess_BADP >= SearchSuccess_GlobalBand
```

while preserving higher retained-set validity.

This is the main proposed-method hypothesis.

### H5 — No single policy should dominate all three objectives

The expected outcome is a Pareto trade-off rather than universal dominance:

```text
Preservation <-> Validity <-> Cost
```

This hypothesis is already consistent with MAGIC results.

---

## 8. Experimental Design

### Experiment A — MAGIC conflict preservation

Purpose:
- prove that pruning can delete externally identified competing evidence;
- measure preservation-versus-noise trade-off;
- identify high-branching regimes.

Executed primary set:

```text
588 rows
1,056 queries
618 queries with candidate paths
420 recoverable conflict queries
```

Key result:

| Policy | Conflict survival | Gold precision | Gold F1 | Avg width |
|---|---:|---:|---:|---:|
| Top-3 | 94.76% | 59.38% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 70.54% | 1.79 |
| Global eps=.10 | 97.14% | 50.18% | 66.18% | 1.94 |
| Relative-loss eps=.25 | 83.81% | 74.26% | 78.66% | 1.13 |
| Boundary Top-3+.01 | **97.86%** | 55.30% | 70.67% | **1.77** |
| No pruning | 100% | 46.67% | 63.64% | 2.15 |

The boundary result is exploratory; `delta=.01` was inspected after earlier ablations.

### Experiment B — WN18RR iterative search

Purpose:
- move pruning inside actual repeated path expansion;
- measure search success, pruning regret, viability, and expansion cost.

Previous 10-query pilot:

| Policy | Search success | Query regret | Avg width |
|---|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 |
| Top-5 | 60% | 40% | 3.88 |
| Global eps=.10 | 40% | 60% | 3.62 |
| Relative-loss eps=.50 | 70% | 30% | 5.97 |

This falsifies a simplistic `global Rashomon > Top-K` claim and motivates both cost matching and boundary-specific retention.

### Experiment C — 50-query budget-matched iterative study

Current workflow:

```text
.github/workflows/wn18rr-iterative-pruning-budgeted.yml
scripts/evaluate_iterative_pruning_budgeted.py
Run 32818825584
```

Policy grid:

```text
Top-3 / Top-5
Global epsilon       .01 .03 .05 .10
Relative-loss epsilon .10 .25 .50
Boundary K=3/5 delta .001 .005 .010 .020 .050
No pruning ceiling
```

Primary metrics:

```text
Search Success
Query Pruning Regret
Viable-prefix Survival by depth
Viability Precision / Recall / F1
Average Active Width
Average Expanded Candidates
Semantic scoring calls
Pareto frontier
```

---

## 9. Peer Group and Positioning

The closest work should be separated into **fixed-beam graph reasoning**, **multi-stage pruning**, and **adaptive-scale graph retrieval**.

| Method | Venue/year | Search/pruning idea | Typical task | Relation to this paper |
|---|---|---|---|---|
| **Think-on-Graph (ToG)** | ICLR 2024 | iterative KG beam search; repeated relation/entity ranking and Top-N pruning | KGQA | fixed-width reference; demonstrates that multiple paths are already standard |
| **Think-on-Graph 2.0 (ToG-2)** | ICLR 2025 | tightly coupled graph/context iterative retrieval | knowledge-intensive QA/KGQA | stronger ToG-family system; architecture broader than pruning-policy isolation |
| **Paths-over-Graph (PoG)** | 2024 | dynamic multi-hop path exploration with graph, LLM, and PLM-based three-stage pruning | KGQA | path-pruning peer; focuses retrieval quality rather than pruning regret |
| **Fast Think-on-Graph (FastToG)** | AAAI 2025 | community search with coarse/fine community pruning | KGQA | efficiency peer; pruning unit is community, not Top-K path boundary |
| **Query-Driven Adaptive Graph Retrieval** | Electronics 2026 | adaptive `K*` from query complexity and path score distribution | multi-hop QA | proves adaptive scale is not novel by itself |
| **Flow-RAG** | Knowledge-Based Systems 2026 | distribution-aware context-adaptive pruning boundary using log-space clustering | WebQSP/CWQ KGQA | especially close conceptual peer for dynamic boundaries; learned flow framework differs from operator-level regret study |

### 9.1 What cannot be claimed

The paper must **not** claim:

```text
first adaptive pruning
first multi-path graph reasoning
Top-K always worse
Rashomon always better
```

Recent adaptive methods explicitly change retrieval scale according to query complexity or score distributions.

### 9.2 Proposed novelty claim

The defensible contribution is:

> **Identify the Top-K cutoff as an irreversible uncertainty boundary, quantify the loss it causes through pruning regret, and evaluate a minimal boundary-local delayed-pruning operator under retained-validity and matched-cost constraints.**

The novelty is therefore the combination of:

```text
boundary-local decision criterion
+
pruning-regret formalization
+
retained-set validity
+
budget-matched search evaluation
```

rather than generic adaptivity.

---

## 10. Comparison Metrics against Peer Methods

Direct peer comparison requires a shared KGQA benchmark. WN18RR is retained as a controlled search-policy stress test and should not be compared numerically with published WebQSP/CWQ answer scores.

For a later apples-to-apples WebQSP/CWQ experiment, use:

| Evaluation level | Metrics |
|---|---|
| Final answer | Exact Match, F1, Hits@1 where applicable |
| Evidence/path retrieval | Gold path recall, supporting-fact precision/recall/F1 |
| Pruning behavior | Gold/viable path survival by depth, pruning regret rate |
| Search efficiency | expanded nodes/paths, average active width, scorer/LLM calls |
| Context efficiency | retrieved context tokens, redundant evidence ratio |
| Runtime | retrieval latency, end-to-end latency |
| Robustness | hop depth, branching factor, boundary margin, score ambiguity |
| Trade-off | answer/search success versus expansion/context cost Pareto frontier |

The most important methodological rule is:

> **Compare pruning policies with the same scorer and comparable search budget before attributing gains to the pruning operator.**

---

## 11. Expected Contribution Structure

If Experiment C and a later shared KGQA benchmark confirm the effect, the paper contribution should be written as four points:

1. **Failure definition:** formalize pruning regret as irreversible removal of all viable evidence despite pre-pruning recoverability.
2. **Method:** propose Boundary-Aware Delayed Pruning, which preserves Top-K plus only candidates near the K-th cutoff.
3. **Validity-aware evaluation:** distinguish useful preservation from indiscriminate candidate retention using viable/gold precision, recall, and F1.
4. **Cost-controlled evidence:** evaluate fixed and adaptive policies under matched search budgets and report Pareto trade-offs rather than raw survival alone.

The central claim is intentionally conditional:

> **Fixed-width pruning is efficient when the rank boundary is clear, but can be unsafe when adjacent candidates are score-indistinguishable. Selective delayed commitment at that boundary is a more targeted response than globally retaining all near-best paths.**

---

## 12. References / Peer Group

- Sun, J. et al. **Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph.** ICLR 2024. arXiv:2307.07697.
- Ma, S. et al. **Think-on-Graph 2.0: Deep and Faithful Large Language Model Reasoning with Knowledge-guided Retrieval Augmented Generation.** ICLR 2025. arXiv:2407.10805.
- Tan, X. et al. **Paths-over-Graph: Knowledge Graph Empowered Large Language Model Reasoning.** arXiv:2410.14211, 2024.
- Liang, X.; Gu, Z. **Fast Think-on-Graph: Wider, Deeper and Faster Reasoning of Large Language Model on Knowledge Graph.** AAAI 2025, 39(23), 24558-24566. DOI: 10.1609/aaai.v39i23.34635.
- Wang, H. et al. **A Query-Driven Graph Retrieval Framework with Adaptive Pruning for Multi-Hop Question Answering.** Electronics 2026, 15(6), 1263. DOI: 10.3390/electronics15061263.
- Zhang, W. et al. **Flow-RAG: Retrieval-augmented generation for knowledge graph question answering via gated flow propagation.** Knowledge-Based Systems 348 (2026), 116400. DOI: 10.1016/j.knosys.2026.116400.
