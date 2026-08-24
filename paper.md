# Rashomon-Tableau: Provenance-Aware Symbolic Truth Adjudication from Conflicting Sources

## 라쇼몽-태블로: 상충 출처로부터의 Provenance 기반 Symbolic Truth Adjudication

**Author:** [Author Name]  
**Affiliation:** [Affiliation]  
**Corresponding Author:** [Email]

---

## Abstract

Real-world information rarely comes from a single fully reliable source. Different documents, websites, agents, sensors, or witnesses may provide incomplete, partially overlapping, or mutually conflicting claims. Three questions must then be separated: **what follows logically from each claim, where the conflict originates, and which candidate truth is best supported**. Classical logic addresses the first two questions, while truth-discovery methods focus on the third. Recent conflict-resolution research further shows that graph structure, fact-level conflict modeling, and explicit reasoning traces can improve how large language models handle contradictory contexts.

We propose **Rashomon-Tableau**, a provenance-aware symbolic truth-adjudication framework that connects these lines of work without claiming that their individual components are new. The framework preserves the path `Source → Claim → Rule/Ontology → Derived Claim → Conflict`, distinguishes incomplete support from incompatible claims, estimates source reliability, and reuses localized conflict evidence to rank candidate truths. *Rashomon* is used here as a problem metaphor: conflicting accounts are retained until their relationships and evidence are understood, rather than prematurely collapsing them into one account. It does not refer to the machine-learning Rashomon set of near-optimal models.

We evaluate the framework component-wise. On the 28 FOLIO validation examples supported by the current Horn/explicit-negation grammar, semantic satisfiability reasoning obtains 96.43% accuracy and 96.33% Macro-F1; this is explicitly **not** a full-FOLIO result. On LogicNLI's official structured `test_logic` split, dual-direction proof checking obtains 98.40% accuracy and 97.92% F1 on paradox/self-contradiction cases, while a single-path rule obtains 0% paradox F1. For real-source truth adjudication, we use the DAFNA-EA Books gold subset containing 100 books, 1,999 source-object claims, and 227 sources. The proposed atomic resolver obtains **61.00% exact truth accuracy and 82.88% author-level F1**. Under the same subset and common evaluation, the official DAFNA-EA implementation yields 57.00% exact accuracy for TruthFinder and AccuSim, 54.00% for 2-Estimates, and 53.00% for 3-Estimates and Accu. Claim-level `exact/partial/conflict` localization reaches **74.58% Macro-F1**.

To test whether the method generalizes beyond legacy truth-discovery data, we additionally use the 2025 MAGIC inter-context conflict benchmark as a structured stress test. Pairwise conflict rules achieve 98.56–100% on MAGIC single-hop subsets but only 27–41% on multi-hop subsets, producing **63.15% overall detection on 1,080 examples**. This negative result is important: the current symbolic prototype handles direct conflicts well but lacks sufficient relation-composition semantics for graph-composed multi-hop conflicts. The paper therefore does not claim state-of-the-art modern conflict resolution.

The closest recent overlap is **Knowledge Conflict Reasoning (KCR, ACL 2026)**, which already disentangles conflicting long contexts into textual and graph-based reasoning traces and trains LLMs with RLVR to follow logically consistent paths. TCR (AAAI 2026), FaithfulRAG (ACL 2025), MAGIC (Findings EMNLP 2025), and DRAGged into CONFLICTS (2025) similarly narrow the novelty space. Consequently, our contribution is stated more narrowly as **source-provenance-preserving symbolic truth adjudication**: source identity and reliability remain attached to explicit and derived propositions, partial evidence is distinguished from incompatibility, and localized conflict provenance is reused for truth selection.

**Keywords:** Truth Discovery; Knowledge Conflict; Provenance; Symbolic Reasoning; Tableau; Conflict Localization; Source Reliability; Truth Adjudication

---

## 초록

현실의 정보는 하나의 완전히 신뢰할 수 있는 출처에서만 주어지지 않는다. 서로 다른 문서, 웹사이트, 에이전트, 센서, 증언자는 동일한 대상에 대해 불완전하거나 부분적으로 겹치거나 서로 상충하는 주장을 제공할 수 있다. 이때 다음 세 문제를 구분할 필요가 있다. **첫째, 각 주장으로부터 무엇이 논리적으로 도출되는가. 둘째, 충돌이 어느 source·claim·rule에서 발생하는가. 셋째, 상충된 후보 중 어떤 truth가 가장 잘 지지되는가.**

본 연구는 이 세 문제를 provenance를 중심으로 연결하는 **Rashomon-Tableau**를 제안한다. 제안 방법은 `Source → Claim → Rule/Ontology → Derived Claim → Conflict` 경로를 유지하고, 불완전하지만 참인 부분 주장을 거짓 주장과 구분하며, source reliability와 proposition support를 이용해 candidate truth를 평가한다. 본 연구에서 Rashomon은 여러 답을 모두 참으로 인정한다는 의미가 아니라, **상충된 관점을 성급하게 제거하지 않고 충돌의 구조와 근거를 추적한 뒤 truth를 판정한다**는 문제의식을 의미한다.

논리 추론은 FOLIO와 LogicNLI로, 실제 truth adjudication은 DAFNA-EA Books로 검증하였다. DAFNA-EA Books 100개 gold book, 1,999개 source-object claim, 227개 source에서 제안 방법은 **Exact Truth Accuracy 61.00%, Author F1 82.88%**를 기록하였다. 같은 subset에서 공식 DAFNA-EA 구현의 TruthFinder와 AccuSim은 Exact Accuracy 57.00%, 2-Estimates는 54.00%, 3-Estimates와 Accu는 53.00%를 기록하였다. Claim-level `exact/partial/conflict` 분류 Macro-F1은 **74.58%**였다.

최근 conflict-resolution 연구와의 비교를 위해 MAGIC(Findings EMNLP 2025)을 추가 stress test로 사용하였다. 구조화된 triplet 기준 pairwise reasoning은 single-hop에서 98.56–100%였으나 multi-hop에서는 27–41%로 크게 하락하였다. 전체 1,080개에서는 63.15%였다. 이는 현재 방법이 직접 충돌에는 강하지만 **relation composition과 graph-path reasoning이 필요한 간접 충돌에는 충분하지 않다**는 약점을 보여준다.

또한 ACL 2026의 KCR은 이미 text/KG reasoning trace를 이용해 explicit knowledge conflict를 adjudicate하므로, 본 연구는 reasoning-path conflict resolution 자체를 novelty로 주장하지 않는다. 본 연구의 차별점은 **source identity와 reliability를 symbolic derivation에 결합하고, partial support와 incompatibility를 분리하며, localized conflict provenance를 truth selection에 재사용하는 source-level symbolic adjudication 구조**에 있다.

---

# 1. Introduction

## 1.1 Problem

다중 출처 환경에서 다음 세 문장은 서로 다르다.

```text
Different information ≠ Contradiction
Contradiction existence ≠ Contradiction location
Contradiction location ≠ Truth selection
```

예를 들어 다음을 생각한다.

```text
Source A: Alice is Bob's father.
Source B: Alice is not Bob's parent.
Source C: Alice is Bob's parent.
```

공통 규칙이 다음과 같다면,

$$
Father(x,y) \rightarrow Parent(x,y)
$$

Source A는 명시적으로 `Parent`를 말하지 않았지만 다음을 지지한다.

$$
Parent(Alice,Bob)
$$

따라서 A와 B의 충돌은 문자열 비교만으로는 보이지 않지만 논리 추론 후에는 나타난다. 동시에 C는 A에서 파생된 proposition을 직접 지지한다.

```text
Source A
  ↓
Father(Alice,Bob)
  ↓ Father→Parent
Parent(Alice,Bob)
       X
NOT Parent(Alice,Bob)
  ↑
Source B

Source C → Parent(Alice,Bob)
```

우리의 목표는 여기서 단순히 `UNSAT=True`를 반환하는 것이 아니다. 어떤 source가 어떤 claim과 rule을 통해 conflict에 참여했는지 보존하고, 이후 source reliability 및 교차 지지를 이용하여 어떤 truth가 더 정당화되는지 판단하는 것이다.

## 1.2 Research Questions

**RQ1 — Logical Reasoning**  
명시적 fact lookup이나 한 방향의 forward reasoning이 놓치는 implicit entailment와 contradiction을 semantic satisfiability reasoning으로 복원할 수 있는가?

**RQ2 — Conflict Localization**  
source/claim provenance와 proposition structure를 유지하면 `exact`, `partial`, `conflict`를 구분하고 직접·간접 충돌의 위치를 더 잘 설명할 수 있는가?

**RQ3 — Truth Adjudication**  
상충된 source를 유지한 상태에서 source reliability와 atomic proposition support를 결합하면 whole-claim voting보다 gold truth recovery가 개선되는가?

## 1.3 Contributions

본 연구의 기여는 다음 세 가지로 제한한다.

1. **Source-provenance-preserving symbolic reasoning.**  
   explicit/derived proposition을 원래 source에서 분리하지 않고 derivation provenance로 유지한다.

2. **Partial-support-aware conflict localization.**  
   multi-valued claim을 atomic proposition으로 분해하여 `different`, `partial`, `conflict`를 구분한다.

3. **Provenance-aware truth adjudication.**  
   source reliability와 proposition-level support를 결합하고 localized conflict evidence를 candidate truth ranking에 재사용한다.

새로운 Tableau calculus, 최초의 truth discovery, 최초의 multi-perspective logic, 최초의 reasoning-trace conflict resolution은 주장하지 않는다.

---

# 2. Related Work and Novelty Boundary

## 2.1 Classical Truth Discovery

TruthFinder는 source trustworthiness와 fact confidence를 상호 강화하는 방식으로 conflicting value에서 truth를 찾는다. CATD는 long-tail source에서 reliability estimation uncertainty를 다룬다. DAFNA-EA는 TruthFinder, 2-Estimates, 3-Estimates, Accu/AccuSim, LTM 등 여러 classical truth-discovery algorithm을 비교하기 위한 공개 구현과 benchmark를 제공한다.

**차이점:** 전통적인 truth discovery는 주로 `source ↔ claimed value`를 모델링한다. 본 연구는 이 관계를 `source ↔ claim ↔ derivation ↔ conflict`로 확장하는 데 초점을 둔다. 다만 source reliability iteration 자체는 기존 연구의 기여이다.

## 2.2 Constrained and Ontology-Aware Truth Discovery

Constrained Truth Discovery는 first-order denial constraint를 truth discovery에 통합한다. 따라서 “논리를 truth discovery에 추가했다”는 주장은 novelty가 아니다. Ontology-aware truth-discovery 연구 역시 value 사이의 semantic relation과 partial ordering을 활용하여 서로 다른 표현이 동시에 참일 수 있는 경우를 다뤘다.

**차이점:** 본 연구는 constraint 또는 semantic relation의 존재 자체보다 **conflict를 만들어낸 source-to-derivation provenance를 output structure로 유지하고 truth adjudication에 다시 사용하는 것**을 강조한다.

## 2.3 Standpoint Logic, Multi-Context Systems, and Axiom Pinpointing

Standpoint Logic은 서로 다른 관점의 knowledge representation과 entailment를 정식화한다. Multi-Context Systems는 heterogeneous context와 bridge rule 사이의 inconsistency를 다룬다. Axiom Pinpointing은 entailment를 발생시키는 minimal axiom justification을 계산한다.

따라서 perspective-aware logic, inconsistency explanation, multiple justification은 본 연구가 최초가 아니다.

## 2.4 MAGIC — Findings EMNLP 2025

MAGIC은 KG subgraph를 perturb하여 **single-hop / multi-hop inter-context knowledge conflict**를 생성하고, conflict detection과 localization을 평가한다. 특히 multi-hop conflict는 2–3개의 logically connected triplet이 original triplet과 간접적으로 충돌하도록 만들어진다.

MAGIC은 본 연구의 RQ2와 직접적으로 관련된다. 동시에 현재 prototype의 약점을 명확히 드러낸다. 단순 same-subject/same-relation 또는 explicit-negation rule은 single-hop에는 충분하지만 multi-hop relation composition에는 부족하다.

**차이점:** MAGIC은 benchmark이며 source reliability 기반 truth adjudication이 목적은 아니다. 반대로 Rashomon-Tableau는 source-level truth 선택까지 포함하지만, MAGIC 수준의 multi-hop conflict reasoning은 아직 충분히 해결하지 못한다.

## 2.5 FaithfulRAG — ACL 2025

FaithfulRAG은 LLM의 self/parametric knowledge와 retrieved context 사이의 fact-level conflict를 모델링하고 context-faithful generation을 수행한다.

**차이점:** FaithfulRAG은 RAG answer generation과 parametric-vs-context conflict가 중심이다. 본 연구는 여러 external source의 identity와 reliability를 명시적으로 유지하고 source-level truth를 adjudicate하는 문제를 다룬다.

## 2.6 DRAGged into CONFLICTS — 2025

CONFLICTS는 실제 search result들을 기반으로 conflict type과 correct answer를 제공한다. 이는 향후 본 연구의 end-to-end RQ3 benchmark로 매우 적합하다.

현재 prototype은 normalized proposition을 입력으로 사용하므로 CONFLICTS에 직접 적용하려면 natural-language claim extraction과 entity/relation normalization을 고정해야 한다. Gold `conflict_type`이나 `correct_answer`를 extraction feature로 사용하면 leakage이므로 허용하지 않는다.

## 2.7 TCR — AAAI 2026

Transparent Conflict Resolution(TCR)은 semantic match, factual consistency, self-answerability를 분리하고 이를 generation에 주입하여 RAG conflict handling을 투명하게 만든다.

**차이점:** TCR은 neural signal과 soft-prompt 중심이며 주로 parametric-vs-retrieved conflict를 다룬다. 본 연구는 symbolic derivation provenance와 external source reliability를 중심으로 한다.

## 2.8 KCR — ACL 2026: Strongest Conceptual Overlap

Knowledge Conflict Reasoning(KCR)은 conflicting long context를 **textual and graph-based reasoning traces**로 분리하고, RLVR을 통해 logically consistent reasoning path를 선택하도록 모델을 학습한다. 이는 현재 연구와 가장 가까운 최신 선행연구다.

따라서 다음 주장은 사용할 수 없다.

> “Conflict를 reasoning path로 분해하고 logical consistency를 이용해 adjudicate하는 최초의 방법이다.”

KCR이 이미 해당 공간을 강하게 점유한다.

현재의 차이는 다음과 같이 좁혀야 한다.

| Dimension | KCR | Rashomon-Tableau |
|---|---|---|
| Core | LLM + RLVR | symbolic + statistical resolver |
| Representation | text / local KG reasoning traces | explicit source-claim-rule-derived-conflict provenance |
| Source reliability | central mechanism 아님 | explicit iterative variable |
| Partial support | central state 아님 | exact / partial / conflict |
| Logic | learned consistency | SAT/refutation + ontology rules |
| Training | task/model training | current prototype requires no task-specific training |
| Final target | answer under conflicting contexts | source-level truth + confidence |

따라서 논문의 가장 방어 가능한 novelty는 다음이다.

> **Source identity and reliability remain attached to symbolic derivations, partial support is separated from incompatibility, and localized conflict provenance is reused for truth adjudication.**

---

# 3. Formalization

Let the sources be:

$$
S = \{s_1, s_2, \ldots, s_m\}
$$

For object $o$, source $s_i$ provides a set of atomic claims:

$$
C_{i,o} = \{c_1, c_2, \ldots\}
$$

Let $T$ be a set of shared ontology or logical rules. The semantic closure is:

$$
Cl_T(C) = \{q \mid T \cup C \models q\}
$$

A direct or derived contradiction is present when:

$$
q \in Cl_T(C_i)
$$

and

$$
\neg q \in Cl_T(C_j)
$$

A derived proposition retains provenance:

$$
Prov(q)=\langle s_i,c,r_1,\ldots,r_k,q\rangle
$$

Given candidate truth set $G_o$, a source claim set is classified as:

- **Exact:** $C_{i,o}=G_o$
- **Partial:** $C_{i,o}\subset G_o$
- **Conflict:** $C_{i,o}$ asserts at least one atom incompatible with $G_o$

Each source has reliability:

$$
r_i \in [0,1]
$$

For an atomic proposition $a$:

$$
Support(a,o)=
\frac{\sum_{i:a\in C_{i,o}} r_i}
{\sum_i r_i}
$$

The current DAFNA implementation iterates between candidate truth construction and reliability re-estimation. A general future scoring form is:

$$
TruthScore(q)=
\alpha SourceSupport(q)
+\beta LogicalSupport(q)
+\gamma CrossSourceAgreement(q)
-\delta ConflictPenalty(q)
$$

The present DAFNA experiment instantiates mainly the source-support and proposition-compatibility terms because DAFNA does not provide rich ontology rules.

---

# 4. Method

## 4.1 Stage 1 — Semantic Reasoning

Entailment is checked through refutation:

$$
KB \models q
\iff
SAT(KB\cup\{\neg q\})=0
$$

The reasoner records derivation metadata instead of returning only a Boolean result.

## 4.2 Stage 2 — Provenance-Preserving Conflict Localization

A conflict is represented as a path rather than a single flag.

```text
Source A
  ↓
Claim A
  ↓ rule r1
Derived q
   X
Derived NOT q
  ↑ rule r2
Claim B
  ↑
Source B
```

For multi-valued data, proposition decomposition prevents partial truth from becoming false conflict.

```text
Truth = {A, B}

Source 1 = {A, B} → exact
Source 2 = {A}    → partial
Source 3 = {C}    → conflict
```

## 4.3 Stage 3 — Truth Adjudication

The resolver repeatedly:

1. estimates source reliability,
2. aggregates proposition-level support,
3. constructs a candidate truth,
4. re-evaluates source compatibility with the candidate.

The final output is a candidate truth with evidence and confidence, not an unordered set of equally valid views.

---

# 5. Experimental Design

No current public benchmark used here contains all of: source IDs, rich logical rules, source reliability, multi-hop conflicts, and independent gold truth. We therefore use **separate but complementary benchmarks**.

| RQ | Dataset | Purpose |
|---|---|---|
| RQ1 | FOLIO | semantic entailment / contradiction core |
| RQ1 | LogicNLI `test_logic` | dual-direction proof / paradox detection |
| RQ2 | DAFNA-EA Books | exact / partial / conflict claim relation |
| RQ2 stress | MAGIC | direct vs multi-hop inter-context conflict |
| RQ3 | DAFNA-EA Books | gold truth recovery from real source claims |

## 5.1 DAFNA Comparison Protocol

The evaluation uses the same 100-book `AuthorsNamesList` gold subset for all methods. The CI clones the official `qcri/DAFNA-EA` repository, builds the Java implementation, executes its voters, and evaluates the resulting `Confidences.csv` using the same benchmark-side author canonicalization.

The main metrics are:

- Exact-set Accuracy
- author-level Precision / Recall / F1
- claim-level `exact / partial / conflict` Macro-F1

`LTM` is stochastic in the official implementation and showed unstable single-run results. It is therefore excluded from headline comparison until repeated-run mean and standard deviation are reported.

## 5.2 MAGIC Protocol

The current MAGIC diagnostic uses released structured `original_triplet` and `perturb_triplet` fields. It tests whether deterministic conflict rules can recognize the benchmark's structured perturbations.

This is **not directly comparable to MAGIC's natural-language LLM ID/LOC results**. In particular, `pair_localization_coverage=1.0` in the diagnostic only means that a best pair can be selected from benchmark-provided structured fields; it is not 100% localization accuracy.

---

# 6. Results

## 6.1 FOLIO Supported Fragment

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Direct Fact | 42.86% | 26.71% |
| Forward Horn | 75.00% | 74.18% |
| **Semantic Clause Tableau** | **96.43%** | **96.33%** |

Only 28 of 204 validation examples are covered by the current grammar. This is component validation, not a full-FOLIO benchmark result.

## 6.2 LogicNLI Structured Logic

| Method | Accuracy | Macro-F1 | Paradox F1 |
|---|---:|---:|---:|
| Single-Path Forward | 74.00% | 65.78% | 0.00% |
| **Dual-Direction Proof Check** | **98.40%** | **98.40%** | **97.92%** |

The result supports checking both $q$ and $\neg q$ rather than terminating after one proof direction succeeds.

## 6.3 DAFNA-EA: Official Truth-Discovery Baselines

| Method | Implementation | Exact Truth Accuracy | Author F1 |
|---|---|---:|---:|
| **Rashomon-Tableau Atomic Resolution** | this work | **61.00%** | **82.88%** |
| TruthFinder | official DAFNA-EA | 57.00% | 66.85% |
| AccuSim | official DAFNA-EA | 57.00% | 66.18% |
| 2-Estimates | official DAFNA-EA | 54.00% | 65.28% |
| 3-Estimates | official DAFNA-EA | 53.00% | 65.45% |
| Accu | official DAFNA-EA | 53.00% | 65.45% |
| Reliability-Weighted Whole Claim | local baseline | 45.00% | 75.24% |
| Whole-Claim Majority | local baseline | 44.00% | 73.57% |

The proposed method is **+4.0 percentage points** above the strongest deterministic official baseline in Exact Truth Accuracy on this subset and substantially higher in author-level F1.

This should not be called global truth-discovery SOTA. The benchmark and several official algorithms are old, which is why modern conflict benchmarks are evaluated separately.

## 6.4 DAFNA Claim-Level Conflict Localization

Gold claim distribution:

| Relation | Count |
|---|---:|
| Exact | 903 |
| Partial | 585 |
| Conflict | 511 |

| Method | Claim Accuracy | Macro-F1 |
|---|---:|---:|
| Whole-Claim Majority | 60.68% | 49.04% |
| Reliability-Weighted Whole Claim | 62.08% | 50.37% |
| **Atomic Truth Resolution** | **76.69%** | **74.58%** |

The large Macro-F1 gain comes mainly from representing `partial` support explicitly rather than collapsing an incomplete but correct value into a competing false value.

## 6.5 MAGIC Modern Stress Test

| Subset | N | Structured Pairwise Detection |
|---|---:|---:|
| 1 single-hop | 208 | 98.56% |
| 2 single-hop | 154 | 98.70% |
| 3 single-hop | 80 | 100.00% |
| 4 single-hop | 50 | 100.00% |
| 1 multi-hop | 300 | 27.00% |
| 2 multi-hop | 158 | 41.14% |
| 3 multi-hop | 80 | 37.50% |
| 4 multi-hop | 50 | 38.00% |
| **Overall** | **1,080** | **63.15%** |

This is the most informative negative result in the current study. The method handles direct replacement/negation conflicts, but performance collapses when contradiction requires multiple semantically connected edges.

MAGIC explicitly constructs multi-hop conflicts from 2–3 connected triplets. Therefore a generic graph traversal alone is insufficient: the system needs **relation-composition semantics** that justify why a path entails or contradicts another relation.

---

# 7. Discussion

## 7.1 What the DAFNA Result Actually Shows

The DAFNA improvement should not be attributed to deep Tableau reasoning because the Books benchmark contains little ontology structure. The primary effect is atomic decomposition plus reliability-weighted partial support.

```text
S1: {A, B}
S2: {A}
S3: {C}
```

Whole-value voting treats all three sets as distinct candidates. Atomic resolution lets S1 and S2 jointly support `A`, while S2 remains incomplete rather than false.

## 7.2 What MAGIC Shows

The original prototype could have looked strong if evaluated only on direct conflicts. MAGIC demonstrates why that would be misleading. Multi-hop conflicts expose a gap between:

```text
Graph connectivity
```

and

```text
Logically valid relation composition
```

The next reasoner must only compose relations when a declared ontology/rule licenses the inference. Inventing composition simply because edges form a path would produce false contradictions.

## 7.3 Why KCR Changes the Novelty Claim

KCR already combines graph/text reasoning traces and logical consistency for conflict adjudication. Hence `reasoning trace + conflict resolution` is not sufficient novelty.

Rashomon-Tableau must therefore demonstrate value from variables KCR does not center on:

- explicit source identity,
- longitudinal source reliability,
- symbolic proof/derivation provenance,
- partial-support semantics,
- auditable truth confidence without task-specific RL training.

A future direct comparison should ideally use the same conflict dataset and hold the extraction layer fixed.

## 7.4 Rashomon as Truth Seeking, Not Pluralism

The method does not conclude that conflicting accounts are all equally true. Its sequence is:

```text
Preserve disagreement
        ↓
Explain the conflict
        ↓
Estimate source/evidence quality
        ↓
Adjudicate truth
```

An `Unresolved` output remains necessary when evidence is insufficient or multiple truths are genuinely valid.

---

# 8. Limitations

1. **No single end-to-end benchmark.** Logical reasoning and source-level truth resolution are still validated on different datasets.
2. **FOLIO coverage is only 28/204.** Full first-order grammar is not supported.
3. **LogicNLI uses structured input.** It does not test semantic parsing.
4. **DAFNA is a legacy benchmark.** It is useful for reproducible truth-discovery comparison but insufficient for a 2026 SOTA claim.
5. **MAGIC multi-hop performance is weak.** Current pairwise structured reasoning reaches only 27–41% on multi-hop subsets.
6. **MAGIC structured fields simplify extraction.** The current test does not reproduce natural-language ID/LOC.
7. **Source reliability and threshold parameters are heuristic.** Held-out tuning and calibration are needed.
8. **LTM is stochastic.** Repeated-run mean ± standard deviation is needed before reporting it as a stable baseline.
9. **KCR is a strong conceptual competitor.** The current work has not yet executed a direct KCR head-to-head evaluation.
10. **Objective truth may not be unique.** The system should support `Truth / False / Unresolved` and multi-truth cases when appropriate.

---

# 9. Next Experiments

The next stage is now more specific than “add more baselines.”

1. **Graph-path reasoner for MAGIC.**  
   Add a relation-rule registry supporting only semantically licensed inverse, symmetry, transitivity, hierarchy, and relation-composition rules. Re-run single-hop and multi-hop separately.

2. **Natural-language extraction freeze.**  
   Convert contexts into propositions without using benchmark gold conflict fields. Measure extraction errors separately from reasoning errors.

3. **CONFLICTS / DRAGged end-to-end evaluation.**  
   Use search results as sources, infer claims and provenance, and evaluate final answer against `correct_answer` without exposing gold conflict metadata.

4. **KCR / TCR / FaithfulRAG comparison where protocol-compatible.**  
   Do not mix their paper-reported metrics with DAFNA. Reproduce each on its own task, or create a common held-out conflict dataset with a fixed extraction layer.

5. **DAFNA robustness and statistics.**  
   Add bootstrap confidence intervals, repeated stochastic baselines, and source-noise injection experiments.

6. **Ablation of the actual novelty.**  
   Compare:
   - no source reliability,
   - no provenance,
   - no partial-support semantics,
   - no logical derivation,
   - full method.

The most important question is whether source-provenance-aware symbolic adjudication still improves truth accuracy **after** multi-hop reasoning and modern neural conflict baselines are included.

---

# 10. Conclusion

Rashomon-Tableau is reframed as a **source-provenance-aware symbolic truth-adjudication framework**, not as a new Tableau calculus and not as a generic claim of first conflict reasoning.

The current evidence supports three narrower conclusions. First, semantic satisfiability and dual-direction checking improve logical component behavior on supported symbolic fragments. Second, atomic decomposition and source reliability improve real-data truth recovery on DAFNA Books, reaching 61% exact accuracy versus 57% for the strongest deterministic official DAFNA baselines on the same subset. Third, MAGIC reveals that this success does not automatically extend to modern multi-hop conflict reasoning: direct conflicts are handled well while graph-composed conflicts remain difficult.

Recent work, especially KCR (ACL 2026), makes the novelty boundary clear. The defensible contribution is not merely “use reasoning traces for conflict resolution.” It is the combination of **explicit source provenance, symbolic derivation, partial-support-aware conflict localization, source reliability, and auditable truth adjudication**. Demonstrating that this combination remains beneficial on modern multi-hop and natural-language conflict benchmarks is the central next research challenge.

---

# References

1. Yin, X., Han, J., & Yu, P. S. (2008). **Truth Discovery with Multiple Conflicting Information Providers on the Web.** IEEE TKDE, 20(6), 796–808.
2. Li, Q., et al. (2014). **A Confidence-Aware Approach for Truth Discovery on Long-Tail Data.** PVLDB, 8(4), 425–436.
3. Waguih, D. A., & Berti-Équille, L. (2014). **Truth Discovery Algorithms: An Experimental Evaluation.** arXiv:1409.6428. DAFNA-EA.
4. Li, Y., et al. (2022). **Constrained Truth Discovery.** IEEE TKDE, 34(1), 205–218.
5. Beretta, V., Harispe, S., Ranwez, S., & Mougenot, I. (2016). **How Can Ontologies Give You Clue for Truth-Discovery? An Exploratory Study.**
6. Gómez Álvarez, L., Rudolph, S., & Strass, H. (2022). **How to Agree to Disagree: Managing Ontological Perspectives using Standpoint Logic.** ISWC 2022.
7. Eiter, T., Fink, M., Schüller, P., & Weinzierl, A. (2014). **Finding Explanations of Inconsistency in Multi-Context Systems.** Artificial Intelligence, 216, 233–274.
8. Baader, F., & Peñaloza, R. (2010). **Axiom Pinpointing in General Tableaux.** Journal of Logic and Computation, 20(1), 5–34.
9. Tian, J., et al. (2021). **Diagnosing the First-Order Logical Reasoning Ability Through LogicNLI.** EMNLP 2021.
10. Han, S., et al. (2024). **FOLIO: Natural Language Reasoning with First-Order Logic.** EMNLP 2024.
11. Lee, J., Kangmin, L., & Kim, T. (2025). **MAGIC: A Multi-Hop and Graph-Based Benchmark for Inter-Context Conflicts in Retrieval-Augmented Generation.** Findings of EMNLP 2025. https://aclanthology.org/2025.findings-emnlp.466/
12. FaithfulRAG authors. (2025). **FaithfulRAG: Fact-Level Conflict Modeling for Context-Faithful Retrieval-Augmented Generation.** ACL 2025. https://aclanthology.org/2025.acl-long.1062/
13. Cattan, A., et al. (2025). **DRAGged into CONFLICTS: Detecting and Addressing Conflicting Sources in Search-Augmented LLMs.** arXiv:2506.08500.
14. Ye, H., et al. (2026). **Seeing through the Conflict: Transparent Knowledge Conflict Handling in Retrieval-Augmented Generation.** AAAI 2026. DOI: 10.1609/aaai.v40i40.40740.
15. Wallat, J., Nejdl, W., & Sikdar, S. (2026). **When Facts Change: Temporal Knowledge Conflict Resolution in LLMs.** Findings ACL 2026. https://aclanthology.org/2026.findings-acl.103/
16. Zheng, X., Huang, Z., Chiang, M.-F., Liu, J., Fang, Y., Witbrock, M. J., & Zhao, K. (2026). **Disentangling Reasoning Logic to Resolve Explicit Knowledge Conflicts.** ACL 2026. https://aclanthology.org/2026.acl-long.1451/

---

## Reproducibility

Repository scripts:

```text
scripts/evaluate_folio_fragment.py
scripts/evaluate_logicnli.py
scripts/evaluate_truth_discovery_books.py
scripts/prepare_dafna_official_books.py
scripts/evaluate_dafna_official_outputs.py
scripts/merge_truth_discovery_comparison.py
scripts/evaluate_magic_structured.py
```

Measured outputs:

```text
results/folio_fragment_metrics.json
results/logicnli_metrics.json
results/truth_discovery_books_metrics.json
results/dafna_official_comparison.json
results/magic_structured_metrics.json
```

Modern baseline and novelty notes:

```text
MODERN_BASELINES.md
```
