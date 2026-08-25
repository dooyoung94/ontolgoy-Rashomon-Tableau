# When Not to Prune: Preserving Conflicting Multi-Hop Evidence under Search Uncertainty

## Abstract

Multi-hop knowledge-graph reasoning systems control combinatorial search by repeatedly pruning candidate paths. This is necessary for efficiency, but pruning can irreversibly remove evidence that a later semantic or logical verifier would need. The problem is especially important when multiple plausible branches compete or when one branch carries evidence that contradicts the current claim.

This paper separates **preservation** from **resolution**. Rather than deciding which conflicting claim is ultimately true, we ask a prior question: **when is it unsafe to prune a reasoning path?** We compare fixed-width Top-K retention with Rashomon-inspired near-optimal score-band retention under frozen scorers and candidate spaces. We define conflict-path survival and conflict information loss using external benchmark provenance, so the semantic scorer does not define its own gold labels.

The empirical study uses two complementary settings. A WN18RR relation-level diagnostic initially shows that near-optimal retention can preserve more gold hypotheses than fixed Top-K at similar average width. However, a 10-query iterative WN18RR experiment provides an important negative result: naive additive epsilon pruning reaches only 40% search success versus 60% for Top-3 and Top-5, demonstrating that score-band retention is not automatically superior and depends on scorer calibration. We then evaluate conflict-evidence preservation on MAGIC multi-hop conflict cases using frozen DeBERTa scores. Of 1,056 queries, 420 contain an externally-gold contradictory path recoverable before pruning. On this full recoverable set, Top-5 is already strong at 98.10% survival, while epsilon=.10 reaches 97.14%. The key effect appears in high-branching regimes: with at least five candidate paths, Top-3 preserves 37.50% and Top-5 75.00% of gold conflict paths, whereas epsilon=.10 preserves 96.88%, at increased search width. These results support a regime-dependent claim: fixed-width pruning becomes brittle as candidate competition grows, and adaptive hypothesis preservation can substantially reduce irreversible conflict-evidence loss when ambiguity/branching is high.

---

## 1. Research problem

Suppose a query or claim `q` induces multiple multi-hop paths:

```text
q
├── p1 : evidence compatible with q
├── p2 : another plausible explanation
├── p3 : evidence contradicting q
└── p4 : unresolved / weak evidence
```

A pruning algorithm must choose which paths survive to the next search step. Once `p3` is removed, downstream conflict detection cannot recover it even if `p3` would have provided the decisive contradiction.

The paper therefore asks:

> **Can a multi-hop reasoner control search cost without prematurely deleting competing or contradictory evidence that remains plausible under the current scorer?**

This is intentionally different from final truth resolution.

```text
Current paper:  Preserve competing evidence
Follow-up:      Resolve competing evidence
```

---

## 2. Relationship to ToG-style search

ToG-style reasoning repeatedly searches and prunes candidate relations/entities. It already retains multiple candidates, so the contribution cannot be framed as `Top-1 versus multiple paths`.

Let `P_k` denote active partial paths at depth `k` and let

```text
C_(k+1) = Expand(P_k, G)
```

be the candidate set after expansion. A scorer assigns

```text
s_theta(p,q)
```

to each candidate.

A fixed beam retains:

```text
P_(k+1)^TopK = TopK(C_(k+1), s_theta, K)
```

The cardinality boundary is independent of whether the score distribution is clear or ambiguous.

The alternative considered here is near-optimal retention:

```text
s* = max_p s_theta(p,q)
R_epsilon = {p in C | s_theta(p,q) >= s* - epsilon}
```

with an optional computational cap.

The conceptual difference is:

```text
Fixed Top-K:
    survive because rank <= K

Near-optimal retention:
    survive because current evidence does not separate the path
    sufficiently from the best candidate
```

The paper does not assume the second policy is always better. Instead, it tests **which search regimes make fixed-width pruning risky**.

---

## 3. Preservation before resolution

For a benchmark query `i`, let `G_i^-` be the externally identified family of paths that contain the contradictory evidence.

Let `C_i` be the candidate set before pruning and `P_i` the selected set after pruning.

A query is **recoverable** if:

```text
G_i^- intersects C_i != empty
```

Primary evaluation is conditioned on recoverability. This is necessary because otherwise retrieval failure would be incorrectly counted as pruning failure.

Conflict-path survival is:

```text
CPS_i = 1[G_i^- intersects P_i != empty]
```

Conflict Information Loss is:

```text
CIL_i = 1 - CPS_i
```

Dataset-level values are the means over recoverable queries.

This gives a direct causal interpretation under frozen candidates and scores:

```text
gold evidence exists before prune
             +
only selection policy changes
             +
gold evidence absent after prune
             ↓
information loss caused by pruning
```

---

## 4. Semantic scorer

The pruning framework is scorer-agnostic:

```text
s_theta = semantic NLI model
s_theta = KGE / structural scorer
s_theta = path model
s_theta = LLM relevance scorer
```

The current experiments retain DeBERTa because prior MAGIC runs show that it is useful as a **semantic verifier**, even though it is weak as a generic WN18RR relation predictor.

### 4.1 DeBERTa output

For path `p` and claim `q`:

```text
D(p,q) = (S_p, C_p, U_p)
```

where:

- `S_p`: support probability,
- `C_p`: contradiction probability,
- `U_p`: unresolved probability.

For the MAGIC preservation experiment we require a side-agnostic path relevance score. Therefore:

```text
r(p,q) = S_p + C_p = 1 - U_p
```

This deliberately treats strong support and strong contradiction as equally worth preserving.

Gold path labels are **not** derived from DeBERTa.

---

## 5. Existing DeBERTa semantic-verifier evidence

Executed source run:

```text
Run      32730398659
Artifact 9521415589
Model    MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli
Rows     588
Queries  1,056
```

Compared with the prior weak lexical scoring condition:

| Metric | Weak lexical | DeBERTa | Gain |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71pp** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68pp** |
| Structured row exact LOC | 7.14% | **15.48%** | **+8.33pp** |

This is retained in the paper for one reason only:

> **when candidate paths are available, DeBERTa provides meaningfully better semantic path discrimination than the weak lexical prior.**

It does not establish end-to-end pruning superiority.

---

## 6. Experiment A — WN18RR relation-hypothesis diagnostic

### 6.1 Protocol

A previously executed 50-example hard 2–4-hop WN18RR subset scored all 11 relation candidates with DeBERTa. The gold relation was evaluation-only. We froze those scores and changed only the retention policy.

### 6.2 Result

| Policy | Gold survival | Pruning regret | Avg active hypotheses |
|---|---:|---:|---:|
| Top-1 | 16% | 84% | 1.00 |
| Top-3 | 32% | 68% | 3.00 |
| Top-5 | 40% | 60% | 5.00 |
| Rashomon eps=.05 | **42%** | **58%** | 3.82 |
| Rashomon eps=.10 | **58%** | **42%** | 5.08 |
| No pruning | 100% | 0% | 11.00 |

The strongest preliminary comparison was:

```text
Top-5            40% survival / width 5.00
Rashomon eps=.10 58% survival / width 5.08
```

This motivated the pruning study, but it was only a **relation-hypothesis diagnostic**, not repeated path search.

---

## 7. Experiment B — iterative WN18RR negative result

We next placed the selection policy inside repeated multi-hop expansion.

The incremental scorer evaluated new edges with DeBERTa and used mean edge support as the path score.

10-query pilot:

| Policy | Search success | Query pruning regret | Avg width | Avg expanded |
|---|---:|---:|---:|---:|
| Top-1 | 20% | 80% | 1.00 | 10.9 |
| **Top-3** | **60%** | **40%** | 2.67 | 21.3 |
| **Top-5** | **60%** | **40%** | 3.88 | 28.1 |
| Additive Rashomon .05 | 40% | 60% | 2.65 | 23.7 |
| Additive Rashomon .10 | 40% | 60% | 3.59 | 28.5 |

### 7.1 Why this matters

The result falsifies the naive claim:

```text
near-optimal retention is always better than fixed Top-K
```

Inspection showed cases in which the best support score itself was low. A fixed additive tolerance then became too narrow relative to score scale and removed viable paths.

Therefore:

> **a preservation rule is only as good as its scoring/calibration assumptions.**

This negative result is retained explicitly in the paper.

---

## 8. Experiment C — MAGIC external-gold conflict preservation

### 8.1 Why MAGIC

WN18RR is useful for path/relation reasoning but weak as an explicit contradiction benchmark. MAGIC provides structured multi-hop conflict cases with paired:

```text
original_triplet
perturb_triplet
```

The original triple defines the claim side; the perturb chain identifies contradictory evidence independently from DeBERTa.

This enables a non-circular preservation evaluation.

### 8.2 Protocol

Executed ablation:

```text
Run      32815760029
Artifact 9551317704
Digest   sha256:f94720659fe26f1634288ad8c572fdd73ce311b9a791d9ba248aef78c281b85a
```

Source:

```text
588 rows
1,056 queries
618 queries with >=1 candidate path
420 queries with >=1 externally-gold conflict path before pruning
```

Thus the primary evaluation set is `n=420` recoverable queries.

All candidate paths and DeBERTa scores are frozen. Only the selection policy changes.

Path-selection score:

```text
r(p) = S_p + C_p = 1 - U_p
```

Gold:

```text
MAGIC perturb_triplet provenance
```

Gold is attached only after scoring/selection.

### 8.3 Overall recoverable result

| Policy | Conflict-path survival ↑ | Information loss ↓ | Avg selected paths |
|---|---:|---:|---:|
| Top-1 | 80.71% | 19.29% | 1.00 |
| **Top-3** | **94.76%** | 5.24% | 1.60 |
| **Top-5** | **98.10%** | **1.90%** | 1.79 |
| Rashomon .03 | 93.10% | 6.90% | 1.60 |
| Rashomon .05 | 94.76% | 5.24% | 1.75 |
| Rashomon .10 | 97.14% | 2.86% | 1.94 |
| No pruning | 100% | 0% | 2.15 |

The aggregate result is deliberately not described as a Rashomon win. Most MAGIC queries in this recoverable set contain only a small number of paths; therefore Top-5 is close to no pruning.

### 8.4 Candidate branching changes the result

When candidate competition is larger, fixed cardinality becomes much more brittle.

| Recoverable subset | n | Top-3 | Top-5 | Rashomon .03 | Rashomon .05 | Rashomon .10 |
|---|---:|---:|---:|---:|---:|---:|
| paths >=3 | 81 | 72.84% | 90.12% | 76.54% | 83.95% | **91.36%** |
| paths >=4 | 46 | 52.17% | 82.61% | 82.61% | 84.78% | **93.48%** |
| paths >=5 | 32 | 37.50% | 75.00% | 81.25% | 84.38% | **96.88%** |

The Top-3 degradation is especially clear:

```text
overall recoverable: 94.76%
paths >=3:           72.84%
paths >=4:           52.17%
paths >=5:           37.50%
```

Top-5 also degrades:

```text
98.10% → 90.12% → 82.61% → 75.00%
```

In contrast, epsilon=.10 remains:

```text
97.14% → 91.36% → 93.48% → 96.88%
```

This does not mean epsilon=.10 is free. On `paths >=5` it retains 8.41 paths on average, versus 5.0 for Top-5. The correct interpretation is:

> **adaptive preservation trades additional search for substantially lower conflict-information loss in high-branching regimes.**

### 8.5 Row-level preservation

Among 176 rows for which every constituent query had a recoverable gold conflict path:

| Policy | Exact row preservation |
|---|---:|
| Top-1 | 79.55% |
| Top-3 | 94.32% |
| Top-5 | **99.43%** |
| Rashomon .03 | 93.18% |
| Rashomon .05 | 95.45% |
| Rashomon .10 | 96.59% |
| No pruning | 100% |

Again, full-set Top-5 is already near the recoverability ceiling. The paper therefore focuses on **where pruning becomes unsafe**, not on global average dominance.

---

## 9. Secondary dual-side diagnostic

A secondary analysis labels a candidate path as support-dominant or contradiction-dominant using the DeBERTa S/C/U outputs themselves. Among 114 queries where both DeBERTa-defined sides existed before pruning:

```text
Top-3 dual-side retention       68.42%
Rashomon eps=.10 retention      86.84%
```

This is useful as a mechanism diagnostic but **not primary evidence**, because DeBERTa defines both the side labels and the score. The primary result remains the MAGIC-provenance conflict-path survival evaluation.

---

## 10. Empirical claim supported so far

The executed results support the following claim:

> **Fixed-width pruning causes irreversible loss of recoverable conflicting evidence, and the risk grows sharply when many candidate paths compete. Near-optimal score-band retention can preserve substantially more conflict evidence in these high-branching regimes, but it incurs additional search cost and is not uniformly superior when the candidate set is small or the scorer is poorly calibrated.**

This is intentionally narrower than:

```text
Rashomon always beats Top-K
```

and narrower than:

```text
we resolve conflicting claims
```

---

## 11. Hypotheses

### H1 — Pruning-caused information loss

For recoverable conflict evidence:

```text
CIL(Top-K) > 0
```

This is directly observed in MAGIC.

### H2 — Branching-risk hypothesis

```text
CIL(Top-K | high branching)
>
CIL(Top-K | low branching)
```

The executed MAGIC results strongly support this descriptive relationship.

### H3 — Adaptive-preservation hypothesis

In high-branching regimes:

```text
CPS(near-optimal retention)
>
CPS(fixed Top-K)
```

for a corresponding increase in retained paths/search cost.

### H4 — Cost trade-off

Preservation must be evaluated jointly with:

```text
active width
expansion count
model calls / token cost
```

### H5 — Scorer dependence

A pruning policy can fail when its scores are poorly calibrated. The iterative WN18RR negative result establishes this as a required control rather than a theoretical footnote.

---

## 12. What remains to prove

The current evidence is strong enough for a research direction, but a final paper still needs:

1. larger iterative multi-hop runs rather than the current 10-query iterative pilot;
2. an explicit score-ambiguity stratification, not only candidate-count stratification;
3. at least one stronger structural/path scorer to test scorer independence;
4. matched-cost comparisons or a Pareto frontier between preservation and search cost;
5. statistical uncertainty / paired significance tests over the final evaluation set;
6. ideally a closer ToG implementation using the same expansion/scoring interface.

These are validation requirements, not changes to the core research question.

---

## 13. Follow-up paper: resolution

The current paper deliberately outputs a preserved reasoning state:

```text
H(q) = {supporting / contradictory / unresolved candidate paths}
```

A follow-up can then study:

```text
H(q)
  ↓
Semantic verification
  ↓
Possible worlds
  ↓
Ontology constraints
  ↓
Tableau SAT / UNSAT
  ↓
Conflict resolution
```

Thus the earlier Tableau idea is not discarded. It moves to the logically subsequent question:

> **Once competing hypotheses survive search, how should they be resolved?**

The current paper establishes the prerequisite:

> **A resolver cannot reason over evidence that pruning has already deleted.**

---

## 14. Reproducibility

Key files:

```text
scripts/evaluate_pruning_policies.py
scripts/evaluate_iterative_pruning_search_incremental.py
scripts/evaluate_iterative_pruning_relative_loss.py
scripts/evaluate_magic_deberta_worlds.py
scripts/evaluate_magic_conflict_preservation.py

results/wn18rr_pruning_policy_ablation_50.json
results/magic_deberta_worlds_summary.json
results/magic_conflict_preservation_summary.json

.github/workflows/wn18rr-pruning-policy-ablation.yml
.github/workflows/magic-conflict-preservation-ablation.yml
```

Current core principle:

```text
Preserve first.
Resolve later.
```
