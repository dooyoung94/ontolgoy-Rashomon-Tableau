# Rashomon Worlds: Provenance-Aware Possible-World Reasoning for Multi-Hop Conflict and Truth Adjudication

## Abstract

Multi-source knowledge systems often contain claims that are individually plausible yet mutually incompatible. The difficulty grows in multi-hop settings: a conflict may depend on several relations, relation-composition semantics may be incomplete, and prematurely selecting one interpretation can discard a valid explanation. We propose **Rashomon Worlds**, a provenance-aware possible-world framework that represents uncertain relation interpretations as defeasible hypotheses, constructs multiple internally consistent worlds, verifies each world with Tableau reasoning, and performs truth adjudication by marginalizing reliability over the surviving worlds. A world contains claims, source identities, relation interpretations, and derivation provenance. Hard ontology semantics remain separate from uncertain relation hypotheses, preventing benchmark-specific candidate rules from being silently promoted to universal axioms. The central hypothesis is that delayed commitment to multiple consistent worlds improves multi-hop conflict localization and final truth recovery compared with single-world reasoning. MAGIC is used to evaluate conflict identification/localization and world construction; DAFNA-EA Books is used to evaluate truth adjudication. Earlier bidirectional-Tableau results are retained only as prior baselines and diagnostics, not as results of the proposed possible-world method.

---

## 1. Problem

Suppose multiple sources provide evidence about a proposition `q`. A conventional pipeline tends to do one of three things early:

1. merge all claims into one knowledge base;
2. select one relation interpretation or proof path;
3. rank sources first and discard low-reliability claims.

All three are risky when the evidence is multi-hop and relation semantics are incomplete. A discovered path does not itself imply truth, contradiction, or causality. At the same time, requiring a complete hard ontology can leave many plausible paths unresolved.

The research problem is therefore not simply contradiction detection. It is:

> **How can a reasoning system preserve mutually incompatible but internally coherent explanations long enough to compare them using provenance and reliability, without treating uncertain relation semantics as hard truth?**

---

## 2. Central Thesis

The central claim of this paper is deliberately narrow:

> **For multi-hop conflict under incomplete relation semantics, preserving multiple internally consistent worlds and adjudicating them with provenance-aware reliability should outperform early single-world commitment in conflict localization and truth recovery.**

This is tested through three hypotheses.

### H1 — World construction
Defeasible relation interpretations should recover valid multi-hop explanations that a static ontology leaves unresolved.

### H2 — Delayed commitment
Maintaining multiple consistent worlds should reduce false early commitments relative to selecting one interpretation or proof path immediately.

### H3 — World-level adjudication
World-level reliability combining source, relation, evidence, and proof provenance should improve gold truth recovery over majority, source-only reliability, and single-proof scoring.

---

## 3. Method

### 3.1 World representation

A possible world is defined as:

\[
W = (C, S, R, D)
\]

where:

- `C` is the set of claims retained in the world;
- `S` is the set of provenance-bearing sources;
- `R` is the set of selected relation interpretations;
- `D` is the set of derivations/proofs induced by the claims and relation interpretations.

A candidate world is admissible only if:

\[
Tableau(W)=SAT
\]

Thus mutually incompatible explanations are not merged into one inconsistent state; they become separate worlds.

### 3.2 Hard semantics vs defeasible semantics

Hard ontology semantics include only externally justified or explicitly declared properties such as inverse, symmetry, hierarchy, or other domain axioms.

Uncertain relation composition is modeled separately as a `RelationHypothesis`:

\[
r_1(x,y) \land r_2(y,z) \Rightarrow r_3(x,z)
\]

with confidence `c` and provenance describing how the hypothesis was obtained. A hypothesis is not promoted to a hard ontology axiom merely because it improves a benchmark example.

This distinction is essential for avoiding answer-template leakage.

### 3.3 World branching

For one uncertain semantic slot, the system may retain several alternatives:

\[
H_1: r_1 \circ r_2 \Rightarrow q
\]

\[
H_2: r_1 \circ r_2 \Rightarrow \neg q
\]

\[
H_3: unresolved
\]

Each choice yields a candidate world. Tableau removes worlds containing an explicit logical clash under the selected assumptions.

### 3.4 World reliability

The initial implementation uses an intentionally simple baseline:

\[
Weight(W) \propto RelationSupport(W) \times SourceSupport(W)
\]

The scoring function is not claimed as theoretically final. It is an ablation target. The planned full model evaluates:

\[
Score(W)=f(S(W),R(W),E(W),P(W))
\]

where:

- `S(W)` = source reliability;
- `R(W)` = relation-interpretation reliability;
- `E(W)` = independent evidence support;
- `P(W)` = proof/provenance consistency.

### 3.5 Truth marginalization

Instead of choosing one world first, support for a query is marginalized across worlds:

\[
P(q)=\sum_{W_i \models q} P(W_i)
\]

\[
P(\neg q)=\sum_{W_i \models \neg q} P(W_i)
\]

The implementation also preserves `BOTH` and `UNRESOLVED` mass rather than forcing a binary decision.

---

## 4. Why This Is Not a Technology List

The method does not claim novelty for Knowledge Graphs, ontology, Tableau, possible-world semantics, rule mining, or source reliability individually.

Their roles are deliberately subordinated to one algorithmic question:

- KG/path retrieval proposes candidate evidence;
- hard ontology provides trusted semantics;
- relation hypotheses represent uncertain semantics;
- Tableau validates each candidate world;
- provenance-aware weighting adjudicates worlds;
- truth marginalization produces the final decision.

External rule miners, embeddings, or LLMs may propose relation hypotheses, but they are interchangeable candidate generators rather than core contributions.

The intended contribution is therefore:

> **a unified world-level representation for source-provenanced conflicting multi-hop claims in which uncertain relation semantics remain defeasible, worlds are logically validated, and final truth is determined by reliability-weighted marginalization.**

---

## 5. Relation to Prior Repository Work

The repository previously implemented ontology-guided bidirectional Tableau reasoning. That work remains useful as a baseline and as diagnostic evidence for the research problem.

On the released structured MAGIC multi-hop data, the prior approach produced:

| Prior component | Multi-hop result |
|---|---:|
| direct heuristic detection | 33.16% |
| bidirectional candidate-path coverage | 68.03% |
| strict ontology-verified contradiction | 5.44% |

These three values measure different things and are not interchangeable accuracy scores.

The diagnostic lesson is that path discovery was substantially easier than closing the path as a formal contradiction using only a static explicit ontology. This motivates the new treatment of relation interpretation as a defeasible world variable.

The 68.03% value is not MAGIC ID or LOC, and the 5.44% value is not claimed as a peer-comparable natural-language benchmark score.

---

## 6. Experimental Design

### 6.1 MAGIC — world construction and conflict localization

MAGIC is the primary dataset for evaluating multi-hop conflict reasoning.

The new method should be evaluated on the same official protocol wherever possible using:

- conflict Identification (ID);
- exact Localization (LOC);
- world coverage;
- gold-world recall;
- relation-interpretation accuracy;
- proof/provenance localization accuracy.

Published multi-hop peer references, weighted from the official N=1..4 subset sizes, are:

| Peer | Weighted ID | Weighted LOC |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | **78.40%** | **47.28%** |
| 5-model mean | **54.34%** | **29.25%** |

These are natural-language model results. A structured-triplet version of Rashomon Worlds must be reported as a separate track unless the natural-language input protocol is reproduced.

### 6.2 DAFNA-EA Books — truth adjudication

DAFNA-EA Books is used to answer a different question:

> Given competing claims/worlds, can the system recover gold truth?

Existing same-protocol prior repository measurements are:

| Prior method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| previous Rashomon atomic resolution | **61.00%** | **82.88%** |
| TruthFinder | 57.00% | 66.85% |
| AccuSim | 57.00% | 66.18% |
| 2-Estimates | 54.00% | 65.28% |
| 3-Estimates | 53.00% | 65.45% |
| Accu | 53.00% | 65.45% |

These numbers establish a prior baseline only. The new Possible-World evaluator must be run before attributing any DAFNA result to Rashomon Worlds.

### 6.3 LogicNLI and FOLIO

LogicNLI and FOLIO remain sanity checks for logical machinery. They are not headline datasets for the central possible-world claim.

---

## 7. Required Ablation

A publishable result should show a coherent progression rather than a list of technologies.

| Variant | Relation semantics | World model | Reliability |
|---|---|---|---|
| B0 Direct | direct evidence only | single | none |
| B1 Static Tableau | hard ontology | single | none |
| B2 Adaptive Relation | hard + defeasible candidates | single selected interpretation | relation only |
| B3 Possible Worlds | hard + defeasible candidates | multiple | uniform |
| B4 Rashomon Worlds | hard + defeasible candidates | multiple | source + relation + proof/evidence |

The paper's principal empirical claim should depend on whether B4 improves over B1–B3 under the same protocol.

Expected table structure:

| Method | MAGIC ID | MAGIC LOC | Gold-world Recall | DAFNA Truth Acc. |
|---|---:|---:|---:|---:|
| B0 | measured | measured | — | measured |
| B1 | measured | measured | measured | measured |
| B2 | measured | measured | measured | measured |
| B3 | measured | measured | measured | measured |
| **B4** | **measured** | **measured** | **measured** | **measured** |

No placeholder improvement should be presented as an experimental result.

---

## 8. Peer-Group Positioning

The closest peer groups are not one homogeneous leaderboard.

### Conflict detection / localization
MAGIC-style LLM systems test whether models can detect and localize conflicts in natural-language contexts.

### Inconsistent knowledge reasoning
Possible-world, maximal-consistent-subset, paraconsistent, and multi-context approaches provide formal machinery for preserving alternatives rather than collapsing them.

### Truth discovery
TruthFinder, Accu-family methods, and related source-reliability models estimate truth from conflicting sources.

Rashomon Worlds sits at the intersection, but its claim is not that any one component is new. The research question is whether **world-level integration** of multi-hop relation uncertainty, logical consistency, provenance, and reliability improves adjudication.

---

## 9. Implementation Status

Implemented:

- `RelationHypothesis` for defeasible two-hop relation semantics;
- explicit unresolved alternatives;
- `PossibleWorld` representation;
- enumeration of mutually exclusive semantic choices;
- Tableau-based pruning of inconsistent worlds;
- source/relation weighted world normalization;
- truth marginalization over `SUPPORTED / CONTRADICTED / BOTH / UNRESOLVED`;
- unit tests for world branching, marginalization, and inconsistent-world pruning.

Not yet claimed as measured:

- official MAGIC ID/LOC for the new world model;
- gold-world recall on MAGIC;
- DAFNA truth accuracy for the new world model;
- learned/adaptive relation-hypothesis generator;
- calibrated proof/evidence reliability model.

---

## 10. Falsifiability

The proposal should be rejected or substantially revised if any of the following occurs under fair evaluation:

1. multiple worlds do not improve ID/LOC or gold-world recall over a single best interpretation;
2. world-level reliability does not improve truth recovery over source-only baselines;
3. gains disappear when relation rules are frozen before test evaluation;
4. improvements depend on benchmark-specific hand-written relation rules;
5. world enumeration becomes impractical without preserving accuracy under pruning.

This falsifiability criterion is important: the paper should demonstrate that the world representation itself provides value, not merely that more components were added.

---

## 11. Summary

The revised research is not "Ontology + Tableau + KG + Rule Mining + Reliability" as a technology stack.

It is one claim:

> **Do not collapse conflicting multi-hop evidence into one interpretation too early. Represent uncertain claims and relation semantics as multiple logically consistent, provenance-bearing worlds, then adjudicate truth across those worlds using reliability.**

Everything else in the repository exists to test that claim.
