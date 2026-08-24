# Rashomon Worlds: Provenance-Aware Possible-World Reasoning for Multi-Hop Conflict and Truth Adjudication

## Abstract

Multi-source knowledge systems often contain mutually incompatible claims whose conflicts emerge only through multi-hop relations. A single-world reasoner faces two coupled problems: incomplete relation semantics can prevent formal closure, while early selection of one interpretation can discard a viable explanation. We propose **Rashomon Worlds**, a provenance-aware possible-world framework that keeps uncertain relation interpretations defeasible, constructs multiple internally consistent worlds, verifies them with Tableau reasoning, and adjudicates among them with explicit world scoring and provenance-aware reliability. The framework separates **world construction** from **world selection** rather than treating graph-path discovery, contradiction verification, and truth discovery as one metric. On 588 released MAGIC multi-hop conflict rows (1,056 query conflicts), static Tableau verifies 4.45% of query conflicts, while possible-world construction retains a paired gold conflicting explanation for 39.39% of queries and 29.42% of rows under strict structured exact localization. Weak lexical world weighting reduces final exact localization to 7.14%, exposing world ranking as the bottleneck. Replacing only that ranking layer with a DeBERTa-v3 NLI discriminator raises row conflict recall from 22.79% to **41.50%**, query conflict recall from 16.86% to **31.53%**, and structured exact localization from 7.14% to **15.48%**. On the DAFNA-EA Books AuthorsNamesList 100-book gold subset, candidate generation contains the gold truth world for 93% of books; posterior/marginal source reliability reaches **62% exact truth accuracy and 84.13% author F1**, compared with 61%/84.04% for early hard commitment and 57% exact for official TruthFinder and AccuSim under the shared evaluation. The results support a narrow conclusion: maintaining alternative worlds materially improves explanation retention, and final performance depends strongly on how those worlds are ranked and adjudicated.

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

### H3 — World selection / adjudication
Given the same candidate-world space, stronger evidence-aware world scoring or posterior reliability should improve final conflict localization and truth recovery over weak lexical weighting or early MAP commitment.

The paper is falsifiable: H1 fails if the gold explanation is not recovered more often; H2 fails if multiple worlds provide no retention benefit; H3 fails if replacing the ranking/adjudication mechanism does not improve same-protocol selection.

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

Trusted ontology axioms remain hard. Uncertain relation composition is represented separately as a defeasible hypothesis:

\[
r_1(x,y)\land r_2(y,z)\Rightarrow q(x,z)
\]

or

\[
r_1(x,y)\land r_2(y,z)\Rightarrow \neg q(x,z).
\]

An explicit unresolved alternative is also allowed. A relation interpretation is therefore a variable of a world rather than a benchmark-specific ontology axiom. For MAGIC, arbitrary multi-hop path hypotheses are endpoint- and direction-bound.

### 3.3 World scoring

World construction and world scoring are intentionally separate. The candidate world set can therefore be held fixed while the ranking layer is ablated.

The first MAGIC scorer is a weak frozen lexical relation prior. The second uses `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` as a discriminative NLI scorer:

\[
Score_{NLI}(W,q)=\{P(entail),P(contradict),P(neutral)\}.
\]

These map to support, contradiction, and unresolved world mass. DeBERTa does not generate claims, paths, or worlds; it only ranks the worlds already produced by the same Rashomon pipeline.

### 3.4 Truth worlds and posterior reliability

For truth-discovery data, a possible world corresponds to a candidate multi-valued truth. In DAFNA Books, candidate author worlds are generated from observed author sets and bounded combinations of source-supported atomic authors, with a maximum of 256 worlds per object. Gold truth is never used to generate or score candidate worlds.

Three DAFNA variants use the identical candidate world space:

- **Uniform:** all sources have equal reliability;
- **Hard Commit:** source reliability is updated against the current MAP world;
- **Marginal Reliability:** source reliability is updated from expected compatibility over all posterior worlds.

Conceptually:

\[
Rel(s)\leftarrow E_{W\sim P(W)}[Compat(c_s,W)].
\]

The key ablation is therefore delayed posterior commitment versus early MAP commitment, not a change in candidate generation.

---

## 4. Experimental Decomposition

### 4.1 MAGIC structured track — world construction and ranking

We evaluate all 588 released multi-hop conflict rows, corresponding to 1,056 query conflicts. Because these files contain conflict cases, conflict values are **recall**, not full official MAGIC ID accuracy.

A strict structured localization diagnostic requires every `original_triplet[i]` to be associated with a selected conflicting path covering its paired `perturb_triplet[i]`. This is not the published natural-language human-scored LOC metric.

The structured track answers two distinct questions:

1. **Construction:** is the gold-compatible conflicting world retained?
2. **Selection:** does the scorer select the correct conflicting world?

### 4.2 DAFNA-EA Books — truth-world adjudication

We use the 100-book `AuthorsNamesList` subset:

- 100 gold books;
- 1,999 collapsed source-object claims;
- 227 sources;
- shared surname + first-initial benchmark-side normalization.

The official DAFNA-EA Java implementations are cloned, built, executed, and re-evaluated under the same normalized comparison. Gold is evaluation-only.

### 4.3 MAGIC natural-language paired model-effect track

For direct comparison with MAGIC LLM peers, the next track consumes only the original natural-language `context1/context2`. Gold structured fields are unavailable to prediction.

For each base LLM we compare:

1. Direct;
2. Compute-Matched Direct;
3. Rashomon Worlds + the same LLM as world scorer;
4. Rashomon Worlds + DeBERTa-v3 as world scorer.

The primary method-effect comparison is within the same base model. Compute-Matched Direct controls for extra LLM inference budget. LOC predictions are exported for blinded human scoring consistent with MAGIC's manual localization protocol.

The current-model track is configured for GPT-5.5, GPT-5.4 mini, Claude Sonnet 5, Mistral Small 4, and Llama 3.3 70B Instruct. The historical MAGIC peer checkpoints remain a separate reproduction track.

---

## 5. Results

### 5.1 MAGIC — world construction and weak selection

Validated workflow: `32725453943`; artifact `9519356207`.

| Variant | Row conflict recall | Query conflict recall | Gold-world query recall | Structured row exact LOC |
|---|---:|---:|---:|---:|
| B1 Static Tableau | **5.44%** | 4.45% | — | — |
| B2 Early-commit single world | **29.93%** | 22.63% | — | — |
| B3 Possible-world retention | — | — | **39.39%** | **29.42%** |
| B4 Weak lexical weighting | **22.79%** | 16.86% | — | **7.14%** |

Average complexity is approximately 1.46 candidate paths/query and 4.10 retained worlds/query.

These results support H1 and the retention part of H2. B4 exposes a negative result: a weak relation-name prior does not reliably select among the retained worlds.

The valid row-level selection comparison is:

\[
29.42\%\;ExactGoldWorldRetention \rightarrow 7.14\%\;SelectedExactLocalization.
\]

The earlier query-level 39.39% value must not be subtracted directly from row-level 7.14% because they use different evaluation units.

### 5.2 MAGIC — DeBERTa-v3 world scorer

Validated workflow: `32730398659`; artifact `9521415589`.

The candidate-world generation mechanism is unchanged. Only the world scoring layer is replaced by DeBERTa-v3 NLI.

| World scorer | Row conflict recall | Query conflict recall | Structured row exact LOC |
|---|---:|---:|---:|
| Weak lexical prior | 22.79% | 16.86% | 7.14% |
| **DeBERTa-v3 NLI** | **41.50%** | **31.53%** | **15.48%** |
| **Absolute gain** | **+18.70 pp** | **+14.68 pp** | **+8.33 pp** |

DeBERTa selects the paired gold conflicting path for **22.06%** of query conflicts.

This result strengthens H3 on the MAGIC structured track: the world-ranking bottleneck is not merely conceptual. Holding candidate-world construction fixed while replacing a weak scorer with a discriminative semantic scorer materially improves both conflict selection and exact structured localization.

The remaining row-level gap becomes:

\[
29.42\%\;ExactGoldWorldRetention \rightarrow 15.48\%\;SelectedExactLocalization.
\]

Thus DeBERTa closes roughly part, but not all, of the selection gap. The next target is better calibrated relation/proof scoring, not simply increasing the number of generated worlds.

### 5.3 DAFNA-EA Books — truth-world adjudication

Validated workflow: `32726434311`; artifact `9519739380`.

Candidate world generation achieves **93.00% gold-world coverage**, with 27.94 candidate worlds/book on average.

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

Marginal reliability improves over hard commitment by **+1.00 pp exact**, over the prior Atomic method by **+1.00 pp exact / +1.25 pp F1**, and over official TruthFinder/AccuSim by **+5.00 pp exact** on this shared evaluated subset.

The DAFNA ranking gap remains:

\[
93\%\;GoldWorldCoverage \rightarrow 62\%\;ExactTruthSelection.
\]

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

These published values consume natural-language contexts. Structured DeBERTa results must not be presented as a head-to-head leaderboard against them. The repository now contains a same-input natural-language paired runner whose primary question is **method effect within each base model**, not cross-model ranking.

### Truth-discovery peers

The safe DAFNA claim is limited to the evaluated subset:

> On the DAFNA-EA Books AuthorsNamesList 100-book gold subset, Rashomon Worlds with marginal reliability achieves 62% exact truth accuracy, compared with 61% for the prior atomic method and 57% for official TruthFinder and AccuSim.

This is not a claim of global SOTA.

---

## 7. Relation to Prior Repository Work

The repository's earlier ontology-guided bidirectional Tableau is a historical baseline:

| Prior diagnostic | Result |
|---|---:|
| direct heuristic detection | 33.16% |
| bidirectional candidate-path coverage | 68.03% |
| strict ontology-verified contradiction | 5.44% |

The 68.03% value is path coverage, not accuracy. Its gap to formal contradiction motivated treating uncertain relation composition as a defeasible world variable rather than continuously hardcoding composition rules.

---

## 8. Why This Is Not a Technology Enumeration

Knowledge graphs, ontology, Tableau, possible worlds, LLMs, DeBERTa, and source reliability are not separate novelty claims. Their roles are subordinate to one experimentally testable mechanism:

1. generate alternative explanation/truth worlds;
2. reject internally inconsistent worlds;
3. preserve uncertainty rather than committing early;
4. score the same retained worlds with interchangeable ranking mechanisms;
5. marginalize provenance/reliability when applicable;
6. measure separately whether the correct world was generated and whether it was selected.

DeBERTa is therefore an ablated **world scorer**, not another technology added to the claimed novelty. Likewise, the LLM in the natural-language track is the perception/extraction and optionally scoring layer; the central representation remains Rashomon Worlds.
