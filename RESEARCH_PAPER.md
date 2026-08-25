# When Not to Prune: Preserving Conflicting Multi-Hop Evidence under Search Uncertainty

## Abstract

Multi-hop knowledge-graph reasoning systems repeatedly prune candidate paths to control combinatorial search. Pruning is necessary for efficiency, but it is irreversible: once a competing or contradictory evidence branch is removed, a downstream semantic or logical verifier cannot inspect it. This work separates **preservation** from **resolution** and asks a prior question: **when is it unsafe to prune a reasoning path?**

We compare fixed-width Top-K retention with several uncertainty-aware alternatives under frozen candidate spaces and scorers. Conflict-path survival is evaluated using external MAGIC `perturb_triplet` provenance, not labels produced by the semantic scorer. We additionally measure the validity of retained sets through benchmark-gold precision, recall, F1, and search width, because preserving more paths is not useful if most additions are irrelevant noise.

The experiments reveal a conditional rather than universal result. On 420 MAGIC queries where externally-gold contradictory evidence is recoverable before pruning, fixed Top-5 already preserves 98.10% of gold conflict paths. However, its survival falls to 75.00% when at least five candidate paths compete, while broad epsilon=.10 retention reaches 96.88%. This preservation gain is accompanied by lower gold precision and larger active sets. A new exploratory boundary-aware policy retains candidates close to the actual Top-K cutoff rather than the global best: on the full MAGIC recoverable set, Top-3 survival rises from 94.76% to 97.86% while average retained width increases only from 1.60 to 1.77. Separately, a 10-query iterative WN18RR pilot shows that naive additive score bands can fail, while a scale-aware relative-loss criterion reaches 70% search success versus 60% for Top-3/Top-5, at higher cost. Taken together, the evidence supports a regime-dependent thesis: **fixed-width pruning becomes brittle under high candidate branching, but effective delayed pruning must balance evidence preservation, retained-set validity, and search cost.**

---

## 1. Research problem

Suppose claim `q` induces multiple reasoning paths:

```text
q
├── p1 : supporting evidence
├── p2 : another plausible explanation
├── p3 : contradictory evidence
└── p4 : unresolved / weak evidence
```

The final task may eventually need to decide which side is true, but that decision is impossible if the relevant competing branch was deleted earlier.

The current work therefore studies:

```text
Paper 1: Preserve competing evidence
Paper 2: Resolve preserved competing evidence
```

Research question:

> **Can multi-hop search control combinatorial cost without prematurely destroying useful competing evidence?**

The central failure mode is **pruning-caused information loss**, not final truth-classification error.

---

## 2. Relationship to ToG-style graph search

ToG-style reasoning already performs iterative graph exploration and pruning and keeps multiple candidates. Hence the contribution is not `Top-1 versus multiple paths`.

For active set `P_k`:

```text
C_(k+1) = Expand(P_k,G)
```

and scorer:

```text
s_theta(p,q)
```

fixed-width pruning is:

```text
P_(k+1)^TopK = TopK(C_(k+1), s_theta, K)
```

The K/K+1 boundary is determined by cardinality, irrespective of whether the scores are clearly separated.

### 2.1 Best-relative score band

```text
s* = max_p s_theta(p,q)
R_eps = {p : s_theta(p,q) >= s* - eps}
```

This is the initial Rashomon-inspired preservation rule.

### 2.2 Relative-loss score band

To reduce raw-score-scale sensitivity:

```text
L(p)=1-s(p)
R_eps^loss = {p : L(p) <= (1+eps)L*}
```

### 2.3 Boundary-aware delayed pruning — exploratory

The most direct fixed-beam failure occurs at the pruning boundary itself. Let `s_(K)` be the K-th ranked score. Then:

```text
B_(K,eps) = {p : s(p) >= s_(K) - eps}
```

when at least K candidates exist; otherwise all available candidates are retained.

This means:

```text
Top-K
+
only candidates nearly tied with the K-th cutoff
```

rather than retaining a broad band around the global best.

The boundary variant is introduced as an **exploratory extension** motivated by the validity/noise analysis. It is not yet presented as the final validated method.

---

## 3. Preservation and external-gold validity

For query `i`, let `G_i^-` denote externally identified contradictory paths and let `C_i` be the pre-pruning candidate set.

A query is recoverable iff:

```text
G_i^- ∩ C_i != empty
```

Only recoverable queries enter the primary pruning analysis. This prevents retrieval failures from being misclassified as pruning failures.

For selected set `P_i`:

```text
CPS_i = 1[G_i^- ∩ P_i != empty]
CIL_i = 1 - CPS_i
```

where CPS is Conflict-Path Survival and CIL is Conflict Information Loss.

### 3.1 Why survival alone is insufficient

A no-pruning policy trivially maximizes survival. Therefore we additionally define retained-set quality against MAGIC's externally paired conflict evidence.

Let retained candidate paths be `P` and benchmark-gold conflict paths be `G`:

```text
Precision_gold = |P ∩ G| / |P|
Recall_gold    = |P ∩ G| / |G|
F1_gold       = harmonic_mean(Precision_gold, Recall_gold)
NoiseRate     = 1 - Precision_gold
```

Search cost is represented by average active width and, in iterative experiments, the number of expanded candidates.

The real objective is therefore multi-dimensional:

```text
maximize conflict evidence preservation
maximize retained-set validity
minimize search cost
```

A crucial scope caveat is that MAGIC marks the paired injected conflict evidence, not every semantically useful alternative path. Thus `gold precision` is **task-specific preservation precision**, not universal truth/relevance precision.

---

## 4. Semantic scorer and non-circular evaluation

DeBERTa provides semantic evidence scores:

```text
D(p,q)=(S_p,C_p,U_p)
```

For conflict preservation, support and contradiction are both informative. We therefore use the side-agnostic score:

```text
r(p,q)=S_p+C_p=1-U_p
```

Gold conflict paths are defined independently by MAGIC `original_triplet ↔ perturb_triplet` provenance and attached after scoring. Therefore DeBERTa does not generate the labels used to evaluate its own pruning output.

---

## 5. Prior evidence that DeBERTa is a meaningful semantic verifier

Source run:

```text
Run      32730398659
Artifact 9521415589
Model    MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli
Rows     588
Queries  1,056
```

Compared with a weak lexical relation prior:

| Metric | Lexical | DeBERTa | Gain |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71pp** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68pp** |
| Structured exact LOC | 7.14% | **15.48%** | **+8.33pp** |

This result is retained as **scorer-validity evidence**: when a useful candidate path is available, DeBERTa distinguishes semantically relevant conflict structure better than the weak lexical prior. It does not establish end-to-end graph-search superiority.

---

## 6. Experiment A — WN18RR frozen relation-hypothesis diagnostic

A 50-example hard 2–4-hop WN18RR subset scored all 11 relation candidates with DeBERTa, after which only the retention policy changed.

| Policy | Gold survival | Avg width |
|---|---:|---:|
| Top-1 | 16% | 1.00 |
| Top-3 | 32% | 3.00 |
| Top-5 | 40% | 5.00 |
| Additive eps=.05 | 42% | 3.82 |
| Additive eps=.10 | **58%** | 5.08 |
| No prune | 100% | 11.00 |

This established a candidate-retention signal but was not iterative graph search.

---

## 7. Experiment B — iterative WN18RR: calibration matters

The pruning operator was then moved inside repeated 2–4 hop expansion. New edges were scored by DeBERTa, and path score was the mean edge support.

### 7.1 Naive additive result

| Policy | Search success | Pruning regret | Avg width |
|---|---:|---:|---:|
| Top-3 | **60%** | **40%** | 2.67 |
| Top-5 | **60%** | **40%** | 3.88 |
| Additive eps=.05 | 40% | 60% | 2.65 |
| Additive eps=.10 | 40% | 60% | 3.62 |

Thus raw `best - epsilon` does not automatically improve iterative search.

### 7.2 Relative-loss result

Executed run:

```text
Run      32813194834
Artifact 9550550657
Digest   sha256:8b52eecb980e610817c0a2e721765a7a6ca2e319feed40ff88e1a42c1804682a
n        10
```

| Policy | Search success | Pruning regret | Avg width | Avg expanded |
|---|---:|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 | 21.3 |
| Top-5 | 60% | 40% | 3.88 | 28.3 |
| Additive eps=.10 | 40% | 60% | 3.62 | 28.5 |
| Relative-loss eps=.25 | 50% | 50% | 4.09 | 31.4 |
| **Relative-loss eps=.50** | **70%** | **30%** | **5.97** | 31.4 |

The scale-aware variant recovers the failure at `eps=.50`, but it does so by keeping substantially more states. Because `n=10`, this is a pilot and supports only the statement that **calibration changes the preservation/cost trade-off**, not a final performance claim.

---

## 8. Experiment C — MAGIC external-gold preservation and validity

Latest executed ablation:

```text
Run      32817516186
Artifact 9551919328
Digest   sha256:3f83fbe18da5c43c94e8f12493c166fd685c873f232cfd6d233f97e9c37bb4c8
```

Data:

```text
588 rows
1,056 queries
618 queries with >=1 candidate path
420 queries with >=1 externally-gold conflict path before pruning
```

Thus primary evaluation is conducted on `n=420` recoverable queries with frozen candidate paths and DeBERTa scores.

### 8.1 Overall preservation-validity-cost result

| Policy | Survival ↑ | Gold precision ↑ | Gold recall ↑ | F1 ↑ | Avg width ↓ |
|---|---:|---:|---:|---:|---:|
| Top-1 | 80.71% | **80.71%** | 80.52% | **80.62%** | **1.00** |
| Top-3 | 94.76% | 59.38% | 94.77% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 98.10% | 70.54% | 1.79 |
| Additive eps=.05 | 94.76% | 54.00% | 94.54% | 68.74% | 1.75 |
| Additive eps=.10 | 97.14% | 50.18% | 97.15% | 66.18% | 1.94 |
| Relative-loss eps=.25 | 83.81% | 74.26% | 83.61% | 78.66% | 1.13 |
| **Boundary Top-3+.01** | **97.86%** | 55.30% | **97.86%** | 70.67% | **1.77** |
| Boundary Top-5+.01 | 98.81% | 52.93% | 98.81% | 68.93% | 1.87 |
| No pruning | 100% | 46.67% | 100% | 63.64% | 2.15 |

Three observations follow.

First, Top-1 has the highest benchmark-gold precision/F1 but loses 19.29% of recoverable conflict queries. It is clean but over-prunes.

Second, broad epsilon retention raises preservation but lowers precision because it carries more non-gold alternatives. For example, eps=.10 retains 97.14% of conflict paths but precision falls to 50.18%.

Third, boundary-aware Top-3 provides an encouraging intermediate point:

```text
Top-3               94.76% survival / 1.60 width
Boundary Top-3+.01  97.86% survival / 1.77 width
```

It rescues 13 queries lost by Top-3 while Top-3 rescues none lost by the boundary variant. The exact paired sign test gives `p=0.000244`, but this must be interpreted as exploratory because the boundary rule and epsilon were examined after earlier ablations.

### 8.2 High-branching regime

Candidate count is the clearest current risk factor.

Previously observed survival:

```text
Top-3: 94.76% overall → 72.84% (>=3) → 52.17% (>=4) → 37.50% (>=5)
Top-5: 98.10% overall → 90.12% (>=3) → 82.61% (>=4) → 75.00% (>=5)
```

For `paths >=5` (`n=32`), adding retained-set validity reveals the full trade-off:

| Policy | Survival ↑ | Gold precision ↑ | Gold F1 ↑ | Avg width ↓ |
|---|---:|---:|---:|---:|
| Top-3 | 37.50% | 12.50% | 18.75% | 3.00 |
| **Top-5** | 75.00% | **15.00%** | **25.00%** | 5.00 |
| Additive eps=.05 | 84.38% | 11.95% | 20.93% | 7.06 |
| Additive eps=.10 | **96.88%** | 11.52% | 20.60% | 8.41 |
| Boundary Top-5+.01 | 84.38% | 13.78% | 23.68% | 6.13 |
| No pruning | 100% | 10.26% | 18.60% | 9.75 |

This prevents an overclaim. Epsilon=.10 almost eliminates conflict-path loss, but at the cost of substantial noise and width. Top-5 retains fewer gold conflict queries but has the best gold-path F1 among these high-branching policies.

Paired query-level survival for eps=.10 vs Top-5:

```text
Rashomon-only wins: 8
Top-5-only wins:    1
Both:              23
Neither:            0
exact sign p = 0.0391
```

Again, this is exploratory (`n=32`, multiple policies examined).

---

## 9. Candidate branching vs score ambiguity

We also measure top-2 semantic relevance margin as an ambiguity proxy. Quartile cut points among branching recoverable queries are approximately:

```text
0.00197 / 0.01307 / 0.04769
```

Small margins occur disproportionately in queries with many candidate paths. Descriptive stratification suggests that near-tie preservation can help in these groups. However, current analysis does **not** establish score ambiguity as an independent causal factor once branching is considered.

Therefore:

```text
SUPPORTED:
high candidate branching → fixed-width pruning becomes brittle

NOT YET ESTABLISHED:
score ambiguity alone → pruning failure independent of branching
```

A larger controlled experiment should vary branching and score margin separately.

---

## 10. Updated hypotheses

### H1 — pruning-caused conflict loss

For recoverable conflict evidence:

```text
CIL_TopK > 0
```

This is directly supported in MAGIC.

### H2 — branching sensitivity

```text
CIL_TopK increases as candidate branching increases
```

This is the strongest current empirical pattern.

### H3 — preservation-validity trade-off

Policies that broaden retention improve conflict-path recall but can reduce retained-set precision and increase cost.

The target is therefore a useful Pareto point, not maximal survival alone.

### H4 — boundary-aware delayed pruning

When candidates near the K-th cutoff are nearly tied, retaining those boundary-near candidates can recover conflict evidence more efficiently than broad best-relative preservation.

This hypothesis is **exploratory** and requires a larger pre-specified iterative experiment.

### H5 — scorer independence

The branching/preservation result should be repeated with at least one structural/path scorer before claiming scorer independence.

---

## 11. What the paper can and cannot claim

### Supported

- Pruning can destroy externally recoverable conflicting evidence.
- The risk is small when candidate sets are small but rises sharply under high branching.
- DeBERTa provides useful semantic verification compared with a weak lexical prior.
- Broad preservation can recover conflict evidence, but it introduces noise and cost.
- Scale-aware scoring changes iterative pruning behavior.

### Not supported yet

- Rashomon-style pruning is universally better than Top-K.
- DeBERTa is a competitive general KG-completion model.
- Score ambiguity independently causes pruning failure.
- Boundary-aware pruning is a final validated algorithm.
- The current paper resolves which conflicting claim is true.
- Current pilots constitute a full ToG reproduction or head-to-head KGQA benchmark.

---

## 12. Next experiment

The next decisive experiment should validate **boundary-aware delayed pruning inside iterative multi-hop search**, rather than only on frozen candidate sets.

Pre-specify before evaluation:

```text
Policies:
- Top-3
- Top-5
- best-relative epsilon
- relative-loss epsilon
- boundary Top-3 + delta
- boundary Top-5 + delta
- no-prune upper bound

Metrics:
- viable/conflict path survival@hop
- pruning regret@hop
- external-gold precision / recall / F1
- average active width
- total expanded paths
- final search success
```

Evaluation requirements:

1. increase high-branching sample size;
2. fix epsilon/delta using development data, then freeze them for test;
3. stratify by branching level;
4. separately stratify score-margin ambiguity where sample size permits;
5. use paired statistical tests on pre-specified comparisons;
6. repeat with one stronger structural/path scorer;
7. only then pass preserved competing hypotheses to the subsequent semantic/logical resolution study.

The paper's working thesis is therefore:

> **The relevant question in multi-hop reasoning is not simply how aggressively to prune, but when a fixed rank boundary becomes epistemically unsafe. In high-branching competing-evidence regimes, delayed pruning can preserve otherwise lost conflict evidence, but the retained set must be evaluated for validity and cost as well as survival.**
