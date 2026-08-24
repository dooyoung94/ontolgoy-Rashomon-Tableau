# Rashomon-Tableau: Ontology-Guided Bidirectional Tableau for Provenance-Aware Multi-Hop Truth Adjudication

## 라쇼몽-태블로: Provenance 기반 Multi-Hop Truth Adjudication을 위한 Ontology-Guided Bidirectional Tableau

---

## Abstract

Conflicting information from multiple sources raises three distinct questions: what can be logically derived from each account, where the disagreement is produced, and which candidate truth is best supported. Classical truth-discovery methods emphasize source reliability and value confidence, while recent knowledge-conflict research emphasizes graph structure, multi-hop reasoning, and conflict-aware answer generation. We study whether these two lines can be connected through explicit symbolic provenance.

We propose **Rashomon-Tableau**, an ontology-guided bidirectional reasoning framework. The method preserves the chain `Source → Claim → Ontology Rule → Derived Claim → Conflict`, retrieves candidate paths in both forward and reverse graph directions, and verifies a queried proposition `q` together with its opposing evidence rather than stopping after the first proof. Each query is assigned one of four states: `SUPPORTED`, `CONTRADICTED`, `BOTH`, or `UNRESOLVED`. Crucially, graph connectivity alone is not treated as truth: inverse, symmetric, transitive, hierarchy, and relation-composition steps are accepted only when explicitly licensed by the ontology. The localized proof evidence is then designed to be combined with source reliability and proposition-level support for truth adjudication.

The evaluation is component-wise. On LogicNLI's official structured `test_logic` split, dual-direction proof checking reaches 98.40% accuracy and 98.40% Macro-F1, while recovering the paradox/self-contradiction class with 97.92% F1. On the currently supported 28-example FOLIO validation fragment, semantic Tableau reasoning reaches 96.43% accuracy; this is not a full-FOLIO result. For real-source truth discovery, the DAFNA-EA Books AuthorsNamesList gold subset contains 100 books, 1,999 source-object claims, and 227 sources. Rashomon-Tableau's atomic resolver obtains 61.00% exact truth accuracy and 82.88% author F1, compared with 57.00% exact accuracy for the official TruthFinder and AccuSim implementations under the same evaluation protocol.

To test modern graph conflict behavior, we use MAGIC (Findings of EMNLP 2025). The previous direct pair heuristic performs well on single-hop subsets but drops sharply on multi-hop cases. We therefore extend the system with bounded forward/reverse path retrieval and ontology-licensed multi-hop derivation. The new evaluation deliberately separates **candidate path coverage** from **verified contradiction**: a path can be retrieved without being accepted as a logical conflict. This distinction is central to both knowledge-conflict reasoning and root-cause analysis, where an observed dependency path is only a hypothesis until evidence and rules validate it.

The contribution is intentionally narrow. We do not claim the first graph-based conflict reasoner, the first logic-aware truth-discovery system, or the first reasoning-trace conflict method. Recent KCR, TCR, FaithfulRAG, MAGIC, and DRAGged into CONFLICTS already cover important parts of this space. The target contribution is the integration of **source identity and reliability, ontology-governed bidirectional symbolic reasoning, partial-vs-incompatible claim semantics, and explicit conflict provenance into a truth-adjudication pipeline**.

**Keywords:** Tableau; Truth Discovery; Knowledge Conflict; Ontology Reasoning; Multi-Hop Reasoning; Provenance; Source Reliability; Conflict Localization; Root Cause Analysis

---

# 1. Introduction

Real systems rarely receive one perfectly reliable description of an event. Different websites, documents, users, sensors, agents, database snapshots, or observability signals may be incomplete, mutually inconsistent, or only partially overlapping. A useful reasoning system must therefore answer three questions separately.

1. **Logical reasoning:** what follows from each explicit claim and the shared ontology?
2. **Conflict localization:** which source, claim, relation, or derivation step produces the disagreement?
3. **Truth adjudication:** which candidate proposition is best supported after considering source reliability and logical evidence?

Collapsing these questions causes information loss. A truth-discovery method may rank values without exposing why they are incompatible. A satisfiability checker may report a contradiction without identifying which source or rule caused it. A graph traversal may return a path that is topologically connected but semantically invalid.

The central hypothesis of this work is:

> **Preserving source provenance while reasoning in both directions over ontology-licensed multi-hop paths can improve conflict localization and provide better evidence for source-level truth adjudication than direct relation matching or whole-value voting alone.**

The term *Rashomon* is used as a methodological metaphor. Competing accounts are retained long enough to understand how and why they disagree; they are not treated as equally true, and the term does not refer to the machine-learning Rashomon set.

---

# 2. Research Questions

## RQ1 — Ontology-Guided Bidirectional Reasoning

Can ontology-guided bidirectional Tableau reasoning recover and validate implicit multi-hop support and contradiction paths missed by direct relation matching?

## RQ2 — Provenance-Aware Conflict Localization

Can the system identify which source, claim, relation, and hop participates in a conflict while distinguishing exact support, partial support, contradiction, and unresolved evidence?

## RQ3 — Truth Adjudication

Does combining proposition-level support and source reliability with localized logical conflict evidence improve recovery of independently verified truth?

---

# 3. Related Work and Novelty Boundary

## 3.1 Classical Truth Discovery

TruthFinder, 2-Estimates, 3-Estimates, Accu/AccuSim, LTM, CATD, and related work estimate source reliability and candidate-value confidence from conflicting providers. This research already establishes that source reliability can be learned from claim agreement patterns. Therefore **source reliability iteration is not a novelty claim** of Rashomon-Tableau.

## 3.2 Logic- and Ontology-Aware Truth Discovery

Constrained Truth Discovery integrates first-order constraints into truth estimation. Ontology-aware truth-discovery work uses semantic relations among values and shows that different-looking values are not always mutually exclusive. Consequently, **adding logic or ontology to truth discovery is not itself novel**.

## 3.3 Perspective and Inconsistency Reasoning

Standpoint Logic formalizes reasoning across conflicting perspectives. Multi-Context Systems study inconsistency across interacting contexts. Axiom Pinpointing finds axioms responsible for consequences or inconsistencies. These works already cover perspective-aware logic and proof localization.

## 3.4 Recent Knowledge-Conflict Reasoning

MAGIC (Findings EMNLP 2025) evaluates inter-context conflict detection and localization with graph-derived single-hop and multi-hop conflicts. FaithfulRAG (ACL 2025) models fact-level conflict between retrieved context and model knowledge. TCR (AAAI 2026) separates transparent conflict signals. KCR (ACL 2026) disentangles conflicting contexts into textual and graph reasoning traces and uses RLVR for conflict adjudication. DRAGged into CONFLICTS provides realistic conflicting search results and correct answers.

These works make a generic claim such as “we are the first to represent conflict as a reasoning path” untenable.

## 3.5 Defensible Contribution

The contribution explored here is narrower:

> **Source identity and reliability remain attached to symbolic ontology derivations; forward and reverse graph candidates are verified with q/¬q Tableau reasoning; partial support is separated from incompatibility; and localized conflict provenance is reused as truth-adjudication evidence.**

---

# 4. Method

## 4.1 Source Claims

Let `S={s1,...,sm}` be a set of sources. Each source provides one or more atomic claims represented as literals:

`r(subject, object)` or `¬r(subject, object)`.

A multi-valued claim is decomposed into atomic propositions instead of being treated as one indivisible string.

## 4.2 Ontology

The ontology can explicitly declare:

- `symmetric(r)`
- `inverse(r1,r2)`
- `subrelation(r1,r2)` / hierarchy
- `transitive(r)`
- `composition(r1,r2→r3)`
- incompatible relation pairs
- exclusive/function-like relations when the domain guarantees them

No reverse or composition rule is invented merely because two graph edges connect.

## 4.3 Candidate Path Retrieval

For a query `q = r(a,b)`, the graph layer retrieves bounded paths in two directions:

```text
Forward: a -> ... -> b
Reverse: b -> ... -> a
```

This stage is deliberately permissive. It produces **hypotheses**, not truth decisions.

The same separation is useful in Root Cause Analysis:

```text
Observed symptom
   <- reverse candidate search - possible upstream causes
   -> forward candidate search - possible downstream impact
```

A path is not accepted as causal simply because it exists.

## 4.4 Ontology Closure

The reasoner derives only ontology-licensed facts. For example:

`partOf(A,B) ∧ partOf(B,C) → partOf(A,C)`

is valid only if `partOf` is declared transitive.

Likewise:

`instanceOf(A,B) ∧ subclassOf(B,C) → instanceOf(A,C)`

requires an explicit composition rule.

## 4.5 Bidirectional Tableau Verification

For query `q`, the reasoner checks both support and opposing evidence.

| q derivable | opposing evidence derivable | State |
|---|---|---|
| Yes | No | SUPPORTED |
| No | Yes | CONTRADICTED |
| Yes | Yes | BOTH |
| No | No | UNRESOLVED |

Opposing evidence is accepted only through:

1. explicit `¬q`,
2. an ontology-declared incompatible relation on the same pair,
3. a competing object for a relation explicitly declared exclusive.

The system does **not** use a closed-world assumption. Failure to prove `q` does not imply `¬q`.

## 4.6 Provenance

Every derived literal stores its parent literals and applied rule. A conflict can therefore be represented as:

```text
Source A
  -> Claim
  -> Rule 1
  -> Derived Claim q
                 X
Source B         -> not-q / incompatible claim
```

For multi-hop derivations, the path contains every supporting hop.

## 4.7 Truth Adjudication

The final layer combines:

- source reliability,
- proposition-level support,
- logical support,
- conflict penalty,
- provenance evidence.

The current DAFNA implementation instantiates the source-reliability and atomic-support terms. The ontology-derived proof terms are being validated on the logical/MAGIC track because DAFNA Books does not contain rich logical rules.

---

# 5. Experimental Design

No single public dataset used here simultaneously provides rich ontology rules, identifiable source histories, multi-hop conflicts, and independent truth labels. Therefore the paper uses split validation rather than pretending that one benchmark validates the whole architecture.

| Component | Dataset | Purpose |
|---|---|---|
| semantic / dual-direction reasoning | FOLIO, LogicNLI | RQ1 |
| multi-hop graph conflict reasoning | MAGIC | RQ1 + RQ2 |
| source-level conflict localization | DAFNA-EA Books | RQ2 |
| truth adjudication | DAFNA-EA Books | RQ3 |

Exact reproducibility and peer-comparison rules are fixed in `BENCHMARK_PROTOCOL.md`.

---

# 6. Current Results

## 6.1 LogicNLI

Official structured `test_logic`, 2,000 statements:

| Method | Accuracy | Macro-F1 | Paradox F1 |
|---|---:|---:|---:|
| Single-path forward | 74.00% | 65.78% | 0.00% |
| **Dual-direction proof check** | **98.40%** | **98.40%** | **97.92%** |

This supports the design choice of checking `q` and its opposite instead of terminating after the first supported path. It is a symbolic reasoning-layer evaluation, not an end-to-end NLP score.

## 6.2 FOLIO

Current grammar coverage is 28/204 validation examples.

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Forward Horn | 75.00% | 74.18% |
| Semantic Clause Tableau | **96.43%** | **96.33%** |

The 96.43% result must not be described as full-FOLIO accuracy.

## 6.3 DAFNA-EA Books

Same 100-book AuthorsNamesList gold subset:

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon-Tableau Atomic Resolution** | **61.00%** | **82.88%** |
| TruthFinder — official DAFNA-EA | 57.00% | 66.85% |
| AccuSim — official DAFNA-EA | 57.00% | 66.18% |
| 2-Estimates — official DAFNA-EA | 54.00% | 65.28% |
| 3-Estimates — official DAFNA-EA | 53.00% | 65.45% |
| Accu — official DAFNA-EA | 53.00% | 65.45% |

The correct claim is limited to this dataset and shared protocol: Rashomon-Tableau is +4.0 percentage points above the strongest stable official baselines in exact truth accuracy. This is not a universal SOTA claim.

Claim-level `exact / partial / conflict` localization reaches 74.58% Macro-F1 versus 50.37% for the local reliability-weighted whole-claim baseline.

## 6.4 MAGIC — Existing Direct Diagnostic

The previous structured direct-pair diagnostic over 1,080 conflict examples obtains nearly complete single-hop detection but only 27–41% on the multi-hop subsets. This demonstrates that direct pair matching cannot reconstruct graph-composed conflicts.

## 6.5 MAGIC — New Bidirectional Tableau Evaluation

The new evaluator `scripts/evaluate_magic_bidirectional.py` separates three quantities:

1. legacy direct conflict detection,
2. bidirectional candidate path coverage,
3. ontology-verified contradiction.

The distinction is intentional. Candidate path coverage is **not** reported as truth accuracy.

The evaluator uses released `subgraph`, `original_triplet`, and `perturb_triplet` fields and a conservative ontology in `config/magic_ontology_rules.yaml`. Missing ontology semantics yield `UNRESOLVED` rather than a guessed contradiction.

The resulting metrics are generated by CI into:

`results/magic_bidirectional_tableau_metrics.json`

and must be interpreted separately from MAGIC's published natural-language LLM ID/LOC scores because the input protocol differs.

---

# 7. RCA Interpretation

The same reasoning architecture can be applied to Root Cause Analysis, but the paper treats RCA as an application interpretation rather than empirical evidence unless a separate RCA benchmark is added.

Example:

```text
DB wait -> SQL latency -> API latency -> Web latency
```

A graph system may retrieve this as a candidate cause path. Tableau then asks whether domain rules and observed evidence support or refute the hypothesis. Reverse search proposes possible causes from the symptom; forward search checks expected impact. Competing evidence can produce `BOTH`, while insufficient evidence produces `UNRESOLVED`.

Thus Tableau's role in RCA is **hypothesis verification and conflict localization**, not automatic conversion of correlation into causation.

---

# 8. Threats to Validity

1. **Split validation:** logic and source-truth labels are not available together in one benchmark.
2. **FOLIO coverage:** only 28/204 validation examples are supported by the current parser.
3. **MAGIC input mismatch:** our current evaluator consumes released structured triplets, while published peers consume natural-language contexts.
4. **Ontology incompleteness:** conservative rules reduce false semantic assumptions but may leave many true conflicts unresolved.
5. **DAFNA age:** DAFNA Books is useful for direct classical truth-discovery comparison but is not a modern RAG conflict benchmark.
6. **LTM instability:** the legacy official LTM implementation is stochastic; single-run values are excluded from headline comparison.
7. **No causal guarantee:** graph direction alone is insufficient for RCA causality.

---

# 9. Next Experiments

1. Execute the new MAGIC bidirectional evaluator in CI and preserve measured outputs.
2. Run ablations for inverse/symmetric, transitive, composition, and bidirectional q/¬q verification.
3. Add exact provenance-path scoring where MAGIC gold localization permits fair mapping.
4. Freeze a non-leaking claim extraction layer for DRAGged into CONFLICTS and evaluate end-to-end truth selection.
5. Add a held-out ontology-rule or domain split to test whether rules generalize instead of encoding benchmark-specific answers.
6. Add a real RCA benchmark only as a separate application track.

---

# 10. Conclusion

Rashomon-Tableau is best understood not as a new Tableau calculus and not as a generic claim of better conflict resolution. Its research target is a specific bridge between two traditions: **truth discovery from unreliable sources** and **symbolic multi-hop conflict reasoning**.

The architecture first retrieves possible forward and reverse paths, then uses an explicit ontology to decide which transformations are logically licensed, then verifies both `q` and its opposing evidence, preserves the source-to-proof provenance, and finally supplies that evidence to truth adjudication. This design makes an important distinction that is shared by knowledge-conflict reasoning and RCA: **a connected path is a candidate explanation, not a verified truth or cause**.

The current evidence is mixed but informative. DAFNA Books shows a measurable advantage over stable official classical truth-discovery baselines on a multi-valued author task. LogicNLI supports dual-direction proof checking. MAGIC exposes the main remaining weakness: multi-hop conflicts require richer, explicit relation semantics. The next stage therefore focuses on measured ontology-guided multi-hop reasoning rather than adding unverified claims of performance.

---

# References

- Yin, X., Han, J., & Yu, P. S. Truth Discovery with Multiple Conflicting Information Providers on the Web. IEEE TKDE, 2008.
- Waguih, D. A., & Berti-Équille, L. Truth Discovery Algorithms: An Experimental Evaluation / DAFNA-EA, 2014.
- Li et al. Constrained Truth Discovery. IEEE TKDE, 2022.
- Gómez Álvarez, Rudolph, & Strass. How to Agree to Disagree: Managing Ontological Perspectives using Standpoint Logic, 2022.
- Baader & Peñaloza. Axiom Pinpointing in General Tableaux, 2010.
- Tian et al. LogicNLI, EMNLP 2021.
- FOLIO, EMNLP 2024.
- MAGIC: A Multi-Hop and Graph-Based Benchmark for Inter-Context Conflicts in Retrieval-Augmented Generation. Findings EMNLP 2025.
- FaithfulRAG: Fact-Level Conflict Modeling for Context-Faithful Retrieval-Augmented Generation. ACL 2025.
- KCR: Disentangling Reasoning Logic to Resolve Explicit Knowledge Conflicts. ACL 2026.
- TCR, AAAI 2026.
- DRAGged into CONFLICTS, 2025.
