# Rashomon Worlds: Provenance-Aware Possible-World Reasoning for Multi-Hop Conflict and Truth Adjudication

## Abstract

Multi-source knowledge systems often contain mutually incompatible claims whose conflicts emerge only through multi-hop relations. A single-world reasoner faces two coupled problems: incomplete relation semantics can prevent formal closure, while early selection of one interpretation can discard a viable explanation. We propose **Rashomon Worlds**, a provenance-aware possible-world framework that keeps uncertain relation interpretations defeasible, constructs multiple internally consistent worlds, verifies them with Tableau reasoning, and adjudicates truth using source-aware posterior weighting. The framework separates **world construction** from **world selection** rather than treating graph-path discovery, contradiction verification, and truth discovery as one metric. On 588 released MAGIC multi-hop conflict rows (1,056 query conflicts), static Tableau verifies 4.45% of query conflicts, while possible-world construction retains a paired gold conflicting explanation for 39.39%; strict row-level structured localization is 29.42%. However, weak lexical/equal-source weighting selects the correct explanation poorly, exposing world ranking as the bottleneck. On the DAFNA-EA Books AuthorsNamesList 100-book gold subset, candidate generation contains the gold truth world for 93% of books. Posterior/marginal source reliability reaches **62% exact truth accuracy and 84.13% author F1**, compared with 61%/84.04% for early hard commitment, 61%/82.88% for the prior atomic method, and 57% exact for official TruthFinder and AccuSim under the shared evaluation. The results support a narrow conclusion: maintaining alternative worlds materially improves explanation retention, while delayed world-level reliability yields a modest truth-adjudication gain; selecting the correct world remains the dominant challenge.

---

## 1. Research Problem

The target problem is not merely contradiction detection. With multi-hop evidence, three uncertainties interact:

1. the relevant evidence path may be indirect;
2. the composition of relations on that path may be uncertain;
3. multiple sources may support mutually incompatible interpretations with different reliability.

A conventional pipeline often commits early by merging all claims, selecting one path/relation interpretation, or ranking sources before preserving alternative explanations. Under incomplete semantics, this can destroy a correct but lower-ranked explanation before it can be evaluated.

We therefore study:

> **Can a system preserve alternative, internally consistent explanations long enough to compare them using logical consistency and provenance-aware reliability, and does this improve conflict explanation retention and final truth recovery?**

---

## 2. Central Hypotheses

### H1 — World construction
Defeasible relation interpretations should retain valid multi-hop conflict explanations that a static hard ontology leaves unresolved.

### H2 — Delayed commitment
Keeping multiple consistent worlds should preserve viable explanations that would be lost by choosing a single interpretation early.

### H3 — World-level adjudication
Updating source reliability over the posterior distribution of competing worlds should improve final truth recovery relative to equal-source scoring, early MAP commitment, and prior atomic resolution.

The paper is falsifiable: H1 fails if the gold explanation is not recovered more often; H2 fails if multiple worlds provide no retention benefit; H3 fails if marginal reliability does not improve same-protocol truth recovery.

---

## 3. Method

### 3.1 Possible-world representation

A world is defined as:

\[
W=(C,S,R,D)
\]

where `C` is a set of claims, `S` their source provenance, `R` selected relation interpretations, and `D` their derivations/proofs.

A candidate world is retained only when:

\[
Tableau(W)=SAT.
\]

Logical inconsistency therefore separates worlds instead of forcing all evidence into one inconsistent knowledge base.

### 3.2 Hard and defeasible relation semantics

Trusted ontology axioms remain hard. Uncertain relation composition is represented separately as a defeasible hypothesis, for example:

\[
r_1(x,y)\land r_2(y,z)\Rightarrow q(x,z)
\]

or

\[
r_1(x,y)\land r_2(y,z)\Rightarrow \neg q(x,z).
\]

An explicit unresolved alternative is also allowed. A relation interpretation is therefore a variable of a world rather than a benchmark-specific ontology axiom.

For MAGIC, arbitrary multi-hop path hypotheses are endpoint- and direction-bound, preventing a relation sequence observed elsewhere in the graph from creating unrelated claims.

### 3.3 Truth worlds

For truth-discovery data, a possible world corresponds to a candidate multi-valued truth. In DAFNA Books, candidate author worlds are generated from:

- all observed author sets;
- bounded combinations of the 12 most source-supported atomic authors;
- cardinality capped by the largest observed claim;
- maximum 256 candidate worlds per object.

Gold truth is never used to generate candidate worlds.

### 3.4 World evidence

For a source claim `c` and candidate world `W`, compatibility rewards overlap while treating omitted co-authors as weaker evidence rather than direct contradiction. The current DAFNA scoring model uses:

\[
Evidence(W)=0.8\cdot Compatibility(W)+0.2\cdot ExactSupport(W).
\]

A softmax over evidence scores produces a world posterior.

### 3.5 Reliability updates: early vs delayed commitment

Three variants use the same candidate world space:

- **Uniform:** all sources have equal reliability;
- **Hard Commit:** source reliability is updated against the current MAP world;
- **Marginal Reliability:** source reliability is updated from expected compatibility over all posterior worlds.

The proposed delayed-commitment update is conceptually:

\[
Rel(s)\leftarrow E_{W\sim P(W)}[Compat(c_s,W)].
\]

Truth is the MAP world after the reliability/posterior iterations. The key ablation is therefore not “more technologies,” but **hard early commitment versus posterior-aware delayed commitment on the same candidate set**.

---

## 4. Experimental Decomposition

The research separates two questions that prior work in the repository had mixed together.

### 4.1 MAGIC: can the right explanation world be constructed and localized?

The structured MAGIC multi-hop release contains conflict examples. We evaluate all 588 rows, corresponding to 1,056 original query conflicts.

Because these files contain conflict cases, reported conflict values are **recall**, not full official MAGIC ID accuracy. We also define a strict structured localization diagnostic: for each `original_triplet[i]`, a retained conflicting path must cover its paired `perturb_triplet[i]`; a row is exact only when all paired conflicts are localized. This is not the published natural-language LOC metric.

### 4.2 DAFNA-EA Books: can competing truth worlds be ranked correctly?

We use the same 100-book `AuthorsNamesList` gold subset used by the repository's prior direct comparison:

- 100 gold books;
- 1,999 collapsed source-object claims;
- 227 sources;
- shared surname + first-initial benchmark-side person normalization.

The official DAFNA-EA Java implementations are cloned, built, executed, and re-evaluated under the same normalized gold comparison.

Gold is used only for final evaluation and candidate-world coverage, never for generation, world scoring, or source-reliability updates.

---

## 5. Results

### 5.1 MAGIC — world construction and localization

Validated workflow: `32725453943`; artifact `9519356207`.

| Variant | Row conflict recall | Query conflict recall | Gold-world query recall | Structured row exact LOC |
|---|---:|---:|---:|---:|
| B1 Static Tableau | **5.44%** | 4.45% | — | — |
| B2 Early-commit single world | **29.93%** | 22.63% | — | — |
| B3 Possible-world retention | — | — | **39.39%** | **29.42%** |
| B4 Weakly weighted worlds | **22.79%** | 16.86% | — | **7.14%** |

Average complexity is 1.46 candidate paths/query, 4.10 retained worlds/query, and 7.36 worlds/row.

These results support H1 and the retention part of H2: the correct conflicting explanation survives in the candidate world set much more frequently than static Tableau can close it formally. However, B4 exposes an important negative result. A weak relation-name prior with equal source reliability does not reliably rank those worlds and performs below the early-commit B2 row recall. The result is retained rather than tuned away.

The main MAGIC gap is therefore:

\[
39.39\%\;GoldWorldRecall \rightarrow 7.14\%\;SelectedExactLocalization.
\]

World ranking, not merely path enumeration, becomes the primary bottleneck.

### 5.2 DAFNA-EA Books — truth-world adjudication

Validated workflow: `32726434311`; artifact `9519739380`.

Candidate world generation achieves:

- **93.00% gold-world coverage**;
- 27.94 candidate worlds/book on average;
- maximum 256 worlds for an object.

Same-protocol truth results:

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds — Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds — Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds — Uniform | 58.00% | 80.38% |
| TruthFinder, official DAFNA-EA | 57.00% | 66.85% |
| AccuSim, official DAFNA-EA | 57.00% | 66.18% |
| 2-Estimates, official DAFNA-EA | 54.00% | 65.28% |
| 3-Estimates, official DAFNA-EA | 53.00% | 65.45% |
| Accu, official DAFNA-EA | 53.00% | 65.45% |

Marginal reliability improves over:

- prior Atomic: **+1.00 pp exact**, **+1.25 pp F1**;
- hard early commitment: **+1.00 pp exact**, **+0.08 pp F1**;
- official TruthFinder: **+5.00 pp exact**;
- official AccuSim: **+5.00 pp exact**.

This gives modest positive evidence for H3. The effect is not large, but it directly isolates delayed commitment: the hard and marginal variants use the same world-generation procedure, while only the reliability update differs.

The larger diagnostic gap remains:

\[
93\%\;GoldWorldCoverage \rightarrow 62\%\;ExactTruthSelection.
\]

Thus candidate generation is already high-coverage, while ranking/calibration remains the central performance problem.

---

## 6. Peer Positioning

### MAGIC natural-language peers

Published weighted multi-hop references are:

| Peer | ID | LOC |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | 78.40% | 47.28% |

These peers consume natural-language contexts, while our current MAGIC experiment consumes released structured triplets. The two tracks must not be presented as a head-to-head leaderboard. A future natural-language Rashomon Worlds track is required for official ID/LOC comparison.

### Truth-discovery peers

DAFNA is a direct same-protocol comparison after common benchmark-side normalization. The safe empirical claim is limited to this evaluated subset:

> On the DAFNA-EA Books AuthorsNamesList 100-book gold subset, Rashomon Worlds with marginal reliability achieves 62% exact truth accuracy, compared with 61% for the prior atomic method and 57% for official TruthFinder and AccuSim.

This is not a claim of global SOTA.

---

## 7. Relation to Prior Repository Work

The repository's earlier ontology-guided bidirectional Tableau is treated as prior baseline. On MAGIC multi-hop structured data it produced:

| Prior diagnostic | Result |
|---|---:|
| direct heuristic detection | 33.16% |
| bidirectional candidate-path coverage | 68.03% |
| strict ontology-verified contradiction | 5.44% |

The 68.03% value is path coverage, not accuracy. Its gap to 5.44% formal contradiction motivated the present change: uncertain relation composition is no longer solved by continuously adding hard ontology rules; it becomes a defeasible interpretation preserved across possible worlds.

---

## 8. Why This Is Not a Technology Enumeration

Knowledge graphs, ontology, Tableau, possible worlds, and source reliability are not independent contributions here. Their roles are subordinate to one experimentally testable mechanism:

1. generate alternative explanation/truth worlds;
2. reject internally inconsistent worlds;
3. retain provenance and uncertainty rather than committing early;
4. rank/marginalize those worlds using reliability;
5. measure separately whether the correct world was generated and whether it was selected.

Rule miners, embeddings, or LLMs may later provide candidate relation interpretations, but they are replaceable generators unless independently evaluated.

The contribution under test is therefore:

> **a provenance-aware possible-world framework that keeps multi-hop relation interpretations defeasible, separates explanation generation from truth selection, and uses posterior-aware reliability to adjudicate between consistent worlds.**

---

## 9. Limitations and Next Experiments

1. **MAGIC protocol mismatch:** current structured diagnostics are not official natural-language ID/LOC.
2. **Weak relation ranking:** MAGIC B4 uses only a fixed broad lexical prior; it is intentionally not optimized against test labels.
3. **Candidate explosion:** DAFNA can reach 256 worlds/object; scalable pruning must preserve gold coverage.
4. **Small DAFNA gain:** marginal reliability improves exact accuracy by only 1 pp over hard commitment. Repeated datasets are required to establish generality.
5. **93% coverage ceiling:** 7% of DAFNA gold truths are absent from the candidate world space, setting an oracle upper bound below 100% for the current generator.

The next core experiment should improve world ranking without test leakage: freeze external relation semantics or train-only induced rules before MAGIC evaluation, calibrate world probabilities, and run relation/domain-held-out tests. A natural-language MAGIC evaluator should then measure official ID and LOC.

---

## 10. Conclusion

The experiments refine the original hypothesis rather than simply adding components. Possible worlds are useful because they **preserve** conflict explanations that hard single-world reasoning would discard; reliability matters because the retained worlds still require adjudication. MAGIC shows a large improvement in gold explanation retention but weak final ranking. DAFNA shows that posterior-aware reliability provides a small, measurable improvement over early commitment. The evidence therefore supports a narrower research claim: **delayed commitment is useful, but the quality of world ranking determines whether that preserved uncertainty becomes better truth decisions.**
