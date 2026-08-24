# Rashomon-Tableau: Ontology-Guided Bidirectional Tableau for Provenance-Aware Multi-Hop Truth Adjudication

## 라쇼몽-태블로: Provenance 기반 Multi-Hop Truth Adjudication을 위한 Ontology-Guided Bidirectional Tableau

---

## Abstract

Conflicting information from multiple sources raises three different problems: what follows logically from each account, where the disagreement is produced, and which candidate truth is best supported. Classical truth discovery emphasizes source reliability and value confidence, whereas recent knowledge-conflict research emphasizes graph structure, multi-hop reasoning, and conflict-aware generation. We study a symbolic bridge between these lines through explicit provenance.

We propose **Rashomon-Tableau**, an ontology-guided bidirectional reasoning framework. The method preserves `Source → Claim → Ontology Rule → Derived Claim → Conflict`, retrieves candidate paths in both forward and reverse directions, and verifies a proposition `q` together with opposing evidence. Each query is classified as `SUPPORTED`, `CONTRADICTED`, `BOTH`, or `UNRESOLVED`. Graph connectivity alone is never treated as truth: inverse, symmetric, hierarchy, transitive, and relation-composition steps are accepted only when explicitly licensed by the ontology. The resulting proof provenance is designed to be combined with source reliability and proposition-level support for truth adjudication.

Evaluation is component-wise. On LogicNLI structured `test_logic`, dual-direction proof checking reaches **98.40% Accuracy / 98.40% Macro-F1 / 97.92% paradox F1**. On the currently supported 28/204 FOLIO validation fragment, semantic Tableau reasoning reaches **96.43% Accuracy / 96.33% Macro-F1**; this is not a full-FOLIO result. On the DAFNA-EA Books AuthorsNamesList gold subset of 100 books, 1,999 source-object claims, and 227 sources, the atomic resolver reaches **61.00% exact truth accuracy and 82.88% author F1**, compared with **57.00% exact accuracy** for the official TruthFinder and AccuSim implementations under the same evaluation protocol.

For modern multi-hop conflict stress testing, we use MAGIC (Findings of EMNLP 2025). The legacy direct structured heuristic detects **33.16%** of multi-hop rows but relies on permissive relation-replacement assumptions rather than strict logical proof. The new bidirectional layer retrieves a subject-to-object or object-to-subject candidate path for **68.03%** of multi-hop rows. However, with a conservative ontology, only **5.44%** of multi-hop rows are formally closed as contradiction. This is a central negative result rather than a performance claim: bidirectional search substantially reduces candidate-path omission, while the remaining bottleneck is **domain relation semantics**, not graph traversal alone.

The contribution is deliberately narrow. KCR, TCR, FaithfulRAG, MAGIC, DRAGged into CONFLICTS, Standpoint Logic, Axiom Pinpointing, and logic-aware truth-discovery work already cover important parts of the problem. The research target is the integration of **source identity and reliability, ontology-governed bidirectional symbolic reasoning, partial-vs-incompatible claim semantics, and explicit source-to-proof provenance into a truth-adjudication pipeline**.

**Keywords:** Tableau; Truth Discovery; Knowledge Conflict; Ontology Reasoning; Multi-Hop Reasoning; Provenance; Source Reliability; Conflict Localization; Root Cause Analysis

---

# 1. Introduction

Real information systems rarely observe one event through a single perfectly reliable source. Documents, websites, agents, sensors, users, and database snapshots may be incomplete, partially overlapping, or contradictory. Three questions should therefore be separated:

1. **Logical reasoning:** what follows from each claim and shared ontology?
2. **Conflict localization:** which source, claim, relation, rule, or hop creates disagreement?
3. **Truth adjudication:** which candidate proposition is best supported after considering source reliability and logical evidence?

A truth-discovery method may rank values without exposing why they conflict. A satisfiability checker may find inconsistency without retaining source identity. A graph traversal may return a connected path that is semantically invalid. Rashomon-Tableau addresses the intersection of these limitations.

The term *Rashomon* is used as a methodological metaphor: competing accounts are retained until their relationships and evidence are understood. It does not mean that all accounts are equally true and does not refer to the machine-learning Rashomon set.

### Central hypothesis

> **Preserving source provenance while reasoning in both directions over ontology-licensed multi-hop paths can improve conflict localization and provide auditable evidence for source-level truth adjudication.**

---

# 2. Research Questions

**RQ1 — Ontology-Guided Bidirectional Reasoning**  
Can ontology-guided bidirectional Tableau reasoning recover and validate implicit multi-hop support and contradiction paths missed by direct relation matching?

**RQ2 — Provenance-Aware Conflict Localization**  
Can the system identify which source, claim, relation, and hop participates in a conflict while distinguishing support, contradiction, both, and unresolved evidence?

**RQ3 — Truth Adjudication**  
Does proposition-level support and source reliability, combined with localized logical evidence, improve recovery of independently verified truth?

---

# 3. Related Work and Novelty Boundary

## 3.1 Truth Discovery

TruthFinder and subsequent methods such as 2-/3-Estimates, Accu/AccuSim, LTM, CATD, and DART estimate source reliability and candidate-value confidence. Therefore **source-reliability iteration is not novel** here.

## 3.2 Logic- and Ontology-Aware Truth Discovery

Constrained Truth Discovery integrates logical constraints into truth estimation, while ontology-aware truth discovery exploits semantic relationships among candidate values. Therefore **adding logic or ontology to truth discovery is not itself a contribution**.

## 3.3 Perspective and Explanation Reasoning

Standpoint Logic formalizes multiple perspectives; Multi-Context Systems study inconsistency among connected contexts; Axiom Pinpointing identifies axioms responsible for logical consequences. These works already cover important aspects of perspective-aware reasoning and explanation provenance.

## 3.4 Modern Knowledge-Conflict Research

MAGIC evaluates graph-based single-hop and multi-hop inter-context conflicts. FaithfulRAG models fact-level conflict in RAG. TCR separates transparent conflict signals. KCR (ACL 2026) constructs textual/KG reasoning traces and uses RLVR for explicit knowledge-conflict adjudication. DRAGged into CONFLICTS supplies realistic conflicting search evidence and a correct answer.

Consequently, a generic statement such as “the first reasoning-path conflict resolver” is not defensible.

### Defensible contribution

> **Source identity and reliability remain attached to symbolic ontology derivations; forward and reverse graph candidates are verified with q/opposing-evidence Tableau reasoning; partial support is separated from incompatibility; and localized source-to-proof provenance is reused as truth-adjudication evidence.**

---

# 4. Method

## 4.1 Atomic source claims

Each source supplies one or more literals:

`r(subject, object)` or `¬r(subject, object)`.

Multi-valued claims are decomposed into atomic propositions so an incomplete but correct subset can be distinguished from an incompatible value.

## 4.2 Ontology

The ontology may explicitly declare:

- symmetric relations;
- inverse relation pairs;
- relation hierarchy;
- transitive relations;
- relation composition `r1(x,y) ∧ r2(y,z) → r3(x,z)`;
- incompatible relations;
- exclusive/function-like relations where justified.

No rule is inferred merely because two edges are connected.

## 4.3 Bidirectional candidate retrieval

For query `q = r(a,b)` the graph layer retrieves bounded paths:

```text
Forward: a → ... → b
Reverse: b → ... → a
```

These are **candidate explanations only**.

## 4.4 Ontology closure

Only declared relation semantics can produce derived literals. Examples:

```text
partOf(A,B) ∧ partOf(B,C) → partOf(A,C)
instanceOf(A,B) ∧ subclassOf(B,C) → instanceOf(A,C)
equivalent(A,B) ∧ distinct(B,C) → distinct(A,C)
```

The third rule is a substitution-style semantic rule and is explicitly declared rather than inferred from connectivity.

## 4.5 Bidirectional Tableau verification

For query `q`, the reasoner evaluates both supporting and opposing evidence.

| q supported | opposing evidence | State |
|---|---|---|
| Yes | No | `SUPPORTED` |
| No | Yes | `CONTRADICTED` |
| Yes | Yes | `BOTH` |
| No | No | `UNRESOLVED` |

Opposition is accepted through explicit negation, ontology-declared incompatible relations, or a competing value of an explicitly exclusive relation. The system does **not** use a closed-world assumption.

## 4.6 Provenance

Each derivation stores parent literals and the applied rule. A verified conflict therefore retains a path such as:

```text
Source A → Claim A → Rule 1 → Derived q
                                  ×
Source B → Claim B → Rule 2 → Derived not-q
```

## 4.7 Truth adjudication

The general target score combines source reliability, atomic support, logical support, cross-source agreement, and conflict evidence. In the current DAFNA implementation, source reliability and atomic support are instantiated directly; ontology-proof terms are evaluated separately because DAFNA Books lacks rich logical rules.

---

# 5. Experimental Design

No current public dataset used here simultaneously provides identifiable source histories, rich ontology rules, multi-hop conflict structure, and independent truth labels. We therefore use split validation.

| Research component | Dataset | Role |
|---|---|---|
| semantic / dual-direction reasoning | LogicNLI, FOLIO | RQ1 |
| multi-hop graph candidate + logical verification | MAGIC | RQ1, RQ2 |
| source-level exact/partial/conflict localization | DAFNA-EA Books | RQ2 |
| independent truth recovery | DAFNA-EA Books | RQ3 |

The exact evaluation policy is fixed in `BENCHMARK_PROTOCOL.md`.

---

# 6. Results

## 6.1 LogicNLI

Official structured `test_logic`, 2,000 statements:

| Method | Accuracy | Macro-F1 | Paradox F1 |
|---|---:|---:|---:|
| Single-path forward | 74.00% | 65.78% | 0.00% |
| **Dual-direction proof check** | **98.40%** | **98.40%** | **97.92%** |

This supports checking both proof directions rather than terminating after the first supported conclusion. It is a symbolic reasoning-layer evaluation, not end-to-end NLP.

## 6.2 FOLIO

Current supported grammar: 28/204 validation examples.

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Forward Horn | 75.00% | 74.18% |
| Semantic Clause Tableau | **96.43%** | **96.33%** |

This must not be reported as full-FOLIO performance.

## 6.3 DAFNA-EA Books — Same-Protocol Truth Discovery

100 gold books, 1,999 source-object claims, 227 sources:

| Method | Exact Truth Accuracy | Author F1 | Protocol |
|---|---:|---:|---|
| **Rashomon-Tableau Atomic Resolution** | **61.00%** | **82.88%** | measured |
| TruthFinder | 57.00% | 66.85% | official DAFNA-EA, measured |
| AccuSim | 57.00% | 66.18% | official DAFNA-EA, measured |
| 2-Estimates | 54.00% | 65.28% | official DAFNA-EA, measured |
| 3-Estimates | 53.00% | 65.45% | official DAFNA-EA, measured |
| Accu | 53.00% | 65.45% | official DAFNA-EA, measured |

The supported claim is narrow: on this multi-valued author benchmark under the shared evaluator, Rashomon-Tableau is **+4.0 percentage points** above the strongest stable official baselines in exact-set accuracy. It is not a universal SOTA claim.

Claim-level `exact / partial / conflict` localization reaches **74.58% Macro-F1**, compared with 50.37% for the local reliability-weighted whole-claim baseline.

## 6.4 MAGIC — Legacy Direct Structured Heuristic

The previous evaluator treats relation replacement and competing objects permissively as conflict cues. Its weighted multi-hop row detection is **33.16%**. Because those assumptions are not always logically valid, this value is retained only as a legacy heuristic baseline.

## 6.5 MAGIC — Ontology-Guided Bidirectional Tableau

Validated GitHub Actions run: `32720349460`  
Artifact: `9517514860`

| Track | Single-hop | Multi-hop | Meaning |
|---|---:|---:|---|
| Legacy direct heuristic | 97.56% | 33.16% | permissive structured conflict cue |
| **Bidirectional candidate-path coverage** | **61.38%** | **68.03%** | at least one forward/reverse path found; **not accuracy** |
| **Ontology-verified contradiction** | **42.68%** | **5.44%** | contradiction closed by declared semantics |

Multi-hop detail:

| MAGIC subset | N | Direct heuristic | Candidate path coverage | Verified contradiction |
|---|---:|---:|---:|---:|
| 1-conflict multi-hop | 300 | 27.00% | 57.33% | 1.33% |
| 2-conflict multi-hop | 158 | 41.14% | 73.42% | 10.76% |
| 3-conflict multi-hop | 80 | 37.50% | 82.50% | 7.50% |
| 4-conflict multi-hop | 50 | 38.00% | 92.00% | 10.00% |
| **Weighted** | **588** | **33.16%** | **68.03%** | **5.44%** |

### Interpretation

This result separates two problems that were previously conflated.

1. **Path omission is substantially reduced.** A relevant endpoint-to-endpoint path is available in 68.03% of multi-hop rows, compared with only 33.16% detection by the old local heuristic.
2. **Path availability does not imply logical contradiction.** Only 5.44% can currently be closed under the conservative ontology.
3. Therefore the remaining bottleneck is **relation semantics / ontology coverage**, not merely bidirectional search.

Examples in MAGIC include chains such as `equivalent to → distinct from`, `connects with ↔ does not connect with`, and `territory overlaps ↔ territory disjoint with`. General opposing semantics for these relation types improve closure, but many other benchmark conflicts require domain-specific or commonsense relation constraints not yet represented.

### Peer comparison policy

MAGIC's published peers read **natural-language contexts** and report ID/LOC. This implementation reads the released **structured triplets**. Therefore the following published values are context only, not head-to-head scores.

Using the official multi-hop subset counts `[300,158,80,50]`, weighted values derived from the paper's Tables 9/10 are:

| Published peer | Weighted ID* | Weighted LOC* |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | 78.40% | 47.28% |
| **5-model mean** | **54.34%** | **29.25%** |

`*` These weighted values are our arithmetic summary of published N-specific values, not metrics printed directly by the MAGIC paper.

**We do not compare 68.03% candidate coverage or 5.44% formal contradiction directly against peer ID/LOC.** The inputs and targets differ.

---

# 7. RCA Interpretation

The architecture maps naturally to Root Cause Analysis, but RCA remains an application interpretation until evaluated on a dedicated RCA dataset.

```text
Observed symptom
      ↓ reverse graph search
Candidate upstream causes
      ↓ Tableau + ontology + evidence
SUPPORTED / CONTRADICTED / BOTH / UNRESOLVED
      ↓ forward graph search
Expected downstream impact
```

For example, a path `DB wait → SQL latency → API latency → Web latency` is only a candidate causal explanation. Tableau verifies whether domain rules and observed evidence support the hypothesis. This avoids converting correlation or topology into causality by assumption.

---

# 8. Threats to Validity

1. **Split validation:** logical rules and source-level truth labels are not jointly available in one benchmark.
2. **FOLIO coverage:** only 28/204 validation cases are parsed by the current grammar.
3. **MAGIC protocol mismatch:** published peers use natural language; our current modern evaluator uses structured released triplets.
4. **Ontology coverage:** conservative semantics reduce false inferences but leave many conflicts unresolved.
5. **DAFNA age:** DAFNA is appropriate for classical truth-discovery comparison but is not a modern RAG conflict benchmark.
6. **LTM instability:** the legacy official implementation is stochastic, so single-run LTM is excluded from headline comparison.
7. **No causal guarantee:** graph direction and dependency do not prove RCA causality.

---

# 9. Next Experiments

1. Build a reproducible ontology-coverage ablation: inverse/symmetric → transitive → composition → opposition semantics → full bidirectional verification.
2. Obtain relation constraints from external schema/ontology sources rather than benchmark-specific sample rules.
3. Implement a fair MAGIC localization mapping and report proof-path precision/recall where gold permits it.
4. Freeze a non-leaking natural-language claim extraction layer and evaluate DRAGged into CONFLICTS end to end.
5. Add a held-out relation/domain split so ontology rules cannot overfit a fixed benchmark relation inventory.
6. Evaluate RCA only on a separate real incident benchmark.

---

# 10. Conclusion

Rashomon-Tableau is best understood as a bridge between **truth discovery from unreliable sources** and **symbolic multi-hop conflict reasoning**. It retrieves possible paths in both directions, restricts inference to explicit ontology semantics, verifies both a query and opposing evidence, retains source-to-proof provenance, and provides this evidence to truth adjudication.

The current results are mixed and therefore useful. DAFNA Books shows a measurable same-protocol advantage over stable official classical truth-discovery baselines. LogicNLI supports dual-direction proof checking. MAGIC shows that bidirectional search can recover candidate connectivity for 68.03% of multi-hop rows, but only 5.44% can currently be formally verified as contradiction under conservative semantics. This demonstrates that the next research problem is not simply “more graph hops,” but **how to represent and validate the semantics that make a multi-hop path evidentially meaningful**.

That distinction is also central to RCA: a graph path is a hypothesis; a verified, provenance-preserving logical path is evidence.

---

# References

- Yin, Han, & Yu. Truth Discovery with Multiple Conflicting Information Providers on the Web. IEEE TKDE, 2008.
- Waguih & Berti-Équille. Truth Discovery Algorithms: An Experimental Evaluation / DAFNA-EA, 2014.
- Li et al. Constrained Truth Discovery. IEEE TKDE, 2022.
- Gómez Álvarez, Rudolph, & Strass. How to Agree to Disagree: Managing Ontological Perspectives using Standpoint Logic, 2022.
- Baader & Peñaloza. Axiom Pinpointing in General Tableaux, 2010.
- Tian et al. LogicNLI. EMNLP 2021.
- FOLIO. EMNLP 2024.
- MAGIC: A Multi-Hop and Graph-Based Benchmark for Inter-Context Conflicts in Retrieval-Augmented Generation. Findings EMNLP 2025.
- FaithfulRAG: Fact-Level Conflict Modeling for Context-Faithful Retrieval-Augmented Generation. ACL 2025.
- KCR: Disentangling Reasoning Logic to Resolve Explicit Knowledge Conflicts. ACL 2026.
- TCR. AAAI 2026.
- DRAGged into CONFLICTS. 2025.
