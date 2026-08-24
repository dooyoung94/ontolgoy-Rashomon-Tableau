# Rashomon-Tableau: Provenance-Aware Logical Conflict Localization and Truth Resolution from Conflicting Sources

## 라쇼몽-태블로: 상충 출처에서의 출처 추적형 논리 충돌 위치 식별과 진실 추론

**Author:** [Author Name]  
**Affiliation:** [Affiliation]  
**Corresponding Author:** [Email]

---

## Abstract

Real-world information systems rarely observe a fact through a single reliable source. Different websites, witnesses, agents, sensors, documents, or database snapshots can provide mutually conflicting claims. Classical logical reasoning can determine whether a set of propositions is consistent, while truth-discovery methods estimate source reliability and select likely true claims. However, these two traditions answer different questions: logical reasoning explains whether and how a contradiction follows, whereas truth discovery estimates which competing value should be trusted. This paper studies whether the two can be connected through explicit provenance.

We propose **Rashomon-Tableau**, a three-stage framework for conflicting-source reasoning. First, a semantic reasoning layer derives implicit propositions and verifies logical support or contradiction. Second, a provenance-preserving conflict layer records the path `Source → Claim → Rule/Ontology → Derived Claim → Conflict` instead of reducing all evidence to a single inconsistent knowledge base. Third, a truth-resolution layer combines source reliability with atomic logical compatibility and cross-source support to rank candidate truths. The term *Rashomon* is used here in the sense of retaining mutually conflicting perspectives long enough to reason about the underlying event, rather than in the machine-learning sense of a Rashomon set of near-optimal predictive models.

The three components are evaluated separately because no single public benchmark used in this work provides natural-language logical rules, source provenance, conflicts, and external truth labels simultaneously. For logical reasoning, the semantic clause-tableau core reaches 96.43% accuracy and 96.33% Macro-F1 on the 28 examples of the FOLIO validation set that are strictly covered by the current Horn/explicit-negation grammar; this is not a full-FOLIO result. On LogicNLI's official structured `test_logic` split, dual-direction proof checking reaches 98.40% accuracy and 98.40% Macro-F1 and detects the paradox/self-contradiction class with 97.92% F1, compared with 0% paradox F1 for a single-path decision rule.

The main real-data evaluation uses the **DAFNA-EA Books** benchmark. It contains conflicting author claims from online sources and an independent gold truth. On 100 gold books, 1,999 source-object claims, and 227 sources, whole-claim majority voting obtains 44% exact truth accuracy, and an iterative source-reliability weighted whole-claim baseline obtains 45%. The proposed provenance-aware atomic resolution obtains **61% exact-set accuracy**, an improvement of **16 percentage points** over the reliability-weighted baseline. Mean author-level F1 improves from 75.24% to **82.88%**. At the claim level, distinguishing `exact`, `partial`, and `conflict` claims yields **74.58% Macro-F1**, compared with 50.37% for the reliability-weighted whole-claim baseline. The result suggests that a correct partial claim should not automatically be treated as a competing false value and that preserving claim structure and provenance can improve both conflict localization and truth recovery.

We explicitly position the contribution relative to prior work. Standpoint Logic and Multi-Context Systems already provide principled representations of multiple or conflicting perspectives; Axiom Pinpointing already computes minimal explanations for logical consequences; TruthFinder, CATD, and related methods already infer source reliability from conflicting claims; Constrained Truth Discovery already introduces first-order denial constraints; and ontology-aware truth-discovery work already exploits semantic relationships between candidate values. Accordingly, we do **not** claim the first perspective-aware logic, the first multiple-proof method, or the first logic-aware truth-discovery algorithm. The narrower contribution is an operational architecture in which **logical derivation paths remain attached to source provenance, conflicts are localized at the claim level, and that provenance-aware conflict evidence is reused for truth resolution**.

**Keywords:** Truth Discovery; Tableau Reasoning; Provenance; Conflict Localization; Multi-Source Reasoning; Source Reliability; Ontology Reasoning; Explainable AI

---

## 초록

실제 정보 시스템에서는 하나의 사실을 단일하고 완전히 신뢰할 수 있는 출처만으로 관찰하기 어렵다. 서로 다른 웹사이트, 증언자, 에이전트, 센서, 문서 또는 데이터 스냅샷은 동일 대상에 대해 상충하는 주장을 제공할 수 있다. 고전 논리 추론은 명제 집합의 일관성과 귀결 관계를 판정할 수 있고, Truth Discovery는 출처 신뢰도와 주장 신뢰도를 함께 추정하여 가능성이 높은 진실을 선택한다. 그러나 두 연구 흐름은 서로 다른 질문에 답한다. 논리 추론은 “어떤 논리 경로로 모순이 발생했는가”를 설명하는 데 강하고, Truth Discovery는 “서로 충돌하는 값 중 무엇을 믿을 것인가”에 강하다.

본 연구는 두 문제를 **provenance**를 중심으로 연결하는 **Rashomon-Tableau**를 제안한다. 제안 방법은 세 단계로 구성된다. 첫째, Semantic Reasoning 단계에서 명시되지 않은 관계를 추론하고 논리적 지지 또는 모순을 검증한다. 둘째, Conflict Localization 단계에서 모든 정보를 하나의 inconsistent knowledge base로 축약하지 않고 `Source → Claim → Rule/Ontology → Derived Claim → Conflict` 경로를 유지한다. 셋째, Truth Resolution 단계에서 source reliability, atomic claim support, logical compatibility, cross-source agreement를 함께 이용하여 candidate truth를 평가한다. 본 연구에서 Rashomon은 “비슷한 성능을 갖는 여러 예측 모델”이라는 Machine Learning의 Rashomon Set 의미가 아니라, **동일 사건에 대한 상충된 관점을 성급하게 제거하지 않고 함께 분석함으로써 실제 truth에 접근한다는 문제의식**을 의미한다.

세 구성요소는 하나의 공개 데이터셋에서 모두 검증하지 않고 역할에 맞는 벤치마크로 분리 평가하였다. Logical Reasoning은 FOLIO와 LogicNLI로 검증한다. FOLIO v0.0 validation 204개 중 현재 parser가 엄격하게 지원하는 Horn/explicit-negation fragment 28개에서 Semantic Clause Tableau는 Accuracy 96.43%, Macro-F1 96.33%를 기록하였다. 이는 full-FOLIO 성능이 아니다. LogicNLI structured `test_logic` 2,000개 statement에서는 명제와 부정 명제 양쪽을 모두 확인하는 dual-proof 판정이 Accuracy 98.40%, Macro-F1 98.40%, paradox/self-contradiction F1 97.92%를 기록하였다.

핵심 real-data 평가는 **DAFNA-EA Books** benchmark를 사용하였다. 100개의 gold book, 1,999개의 source-object claim, 227개의 source를 대상으로 whole-claim majority voting은 exact truth accuracy 44%, source-reliability weighted whole-claim baseline은 45%를 기록하였다. 제안한 provenance-aware atomic truth resolution은 **61%**로 reliability baseline 대비 **+16.0 percentage points** 향상되었다. Author-level mean F1은 75.24%에서 **82.88%**로 향상되었다. 또한 각 source claim을 `exact`, `partial`, `conflict`로 구분하는 conflict localization에서는 Macro-F1이 50.37%에서 **74.58%**로 향상되었다.

본 연구는 Standpoint Logic, Multi-Context Systems, Axiom Pinpointing, TruthFinder, CATD, Constrained Truth Discovery, ontology-aware truth discovery와 직접적으로 겹치는 부분이 있다. 따라서 최초의 multi-perspective logic, 최초의 multiple-proof reasoning, 최초의 logic-aware truth discovery를 주장하지 않는다. 본 연구의 차별점은 **논리적 derivation과 source provenance를 분리하지 않고 conflict path로 유지하며, 해당 conflict provenance를 다시 truth resolution의 evidence로 사용하는 전체 reasoning pipeline**에 있다.

**주요어:** Truth Discovery, Tableau, Provenance, Conflict Localization, Multi-Source Reasoning, Source Reliability, Ontology, Explainable Reasoning

---

# 1. Introduction

## 1.1 Motivation

서로 다른 출처의 정보가 다르다는 사실은 그 자체로 모순을 의미하지 않는다. 또한 모순이 발견되었다는 사실만으로 어떤 주장이 거짓인지 알 수 있는 것도 아니다. 다중 출처 환경에서는 다음 세 질문이 순차적으로 필요하다.

1. **Logical Reasoning:** 주장으로부터 무엇이 실제로 논리적으로 귀결되는가?
2. **Conflict Localization:** 어떤 source, claim, rule에서 충돌이 발생했는가?
3. **Truth Resolution:** 충돌하는 주장 중 무엇이 실제 truth에 더 잘 정당화되는가?

이 세 문제를 구분하지 않으면 서로 다른 종류의 정보 손실이 발생한다. 단순 문자열 비교는 implicit contradiction을 놓칠 수 있고, 모든 source를 하나의 ABox로 병합하면 contradiction provenance가 사라질 수 있으며, 단순 majority voting은 부분적으로 옳은 주장을 서로 다른 값으로 취급하거나 다수의 저품질 source에 의해 오염될 수 있다.

본 연구의 중심 가설은 다음과 같다.

> **상충된 관점을 즉시 하나로 병합하거나 하나를 제거하지 않고, 각 주장의 출처와 논리적 derivation을 보존하면 conflict를 더 정확하게 위치시킬 수 있으며, 그 conflict provenance를 source reliability와 결합하면 truth resolution을 개선할 수 있다.**

## 1.2 Running Example

다음 세 source를 생각한다.

```text
Source A: Alice is Bob's father.
Source B: Alice is not Bob's parent.
Source C: Alice is Bob's parent.
```

공통 ontology에 다음 규칙이 있다고 하자.

$$
Father(x,y) \rightarrow Parent(x,y)
$$

Source A의 명시적 claim은 `Father(Alice,Bob)`이지만 semantic reasoning을 적용하면 다음 명제가 파생된다.

$$
Parent(Alice,Bob)
$$

따라서 Source A와 Source B 사이에는 명시적 문자열이 동일하지 않아도 논리적 conflict가 존재한다.

```text
Source A
  └─ Father(Alice,Bob)
       └─ [Father -> Parent]
            └─ Parent(Alice,Bob)
                    X
Source B            └─ NOT Parent(Alice,Bob)

Source C
  └─ Parent(Alice,Bob)
       └─ supports the same candidate truth as A
```

여기서 단순한 `UNSAT` 결과만 반환하면 Source A가 어떤 rule을 통해 충돌에 참여했는지 보이지 않는다. 반대로 provenance path를 유지하면 `Source A → Father → Parent → conflict with Source B`와 `Source C → Parent → conflict with Source B`를 별도로 기록할 수 있다.

최종 단계는 누가 “이겼는가”를 단순히 세는 것이 아니다. Source A와 C의 reliability, 두 claim의 논리적 consistency, ontology-derived support, Source B가 과거에 제공한 claim의 정확성 등을 함께 고려하여 `Parent(Alice,Bob)`와 `NOT Parent(Alice,Bob)`의 confidence를 계산한다.

이 running example이 본 논문의 세 기여를 모두 보여준다.

## 1.3 Research Questions

**RQ1 — Logical Reasoning**  
Semantic satisfiability reasoning은 명시적 fact lookup 또는 한 방향의 forward reasoning이 놓치는 implicit entailment와 contradiction을 검출할 수 있는가?

**RQ2 — Conflict Localization**  
전체 conflict를 하나의 값으로 축약하지 않고 source-claim provenance와 proposition structure를 유지하면 실제 gold truth 기준으로 `exact`, `partial`, `conflict` claim을 더 정확하게 식별할 수 있는가?

**RQ3 — Rashomon Truth Resolution**  
상충된 source를 유지한 상태에서 source reliability와 atomic logical compatibility를 결합하면 majority 또는 whole-claim reliability voting보다 실제 truth recovery가 개선되는가?

## 1.4 Contributions

본 논문의 기여는 다음 세 가지로 제한한다.

**C1. Provenance-preserving semantic reasoning architecture.**  
논리적 귀결을 원래 source/claim에서 분리하지 않고 derivation path로 유지하는 reasoning architecture를 정의한다.

**C2. Claim-level conflict localization.**  
다중 값을 갖는 claim을 하나의 불가분한 문자열로 취급하지 않고 atomic proposition 집합으로 해석하여 `exact`, `partial`, `conflict`를 구분한다.

**C3. Provenance-aware truth resolution.**  
source reliability와 atomic proposition support를 반복적으로 함께 추정하고, conflict provenance를 유지하면서 candidate truth를 구성하는 lightweight resolution method를 제안한다.

본 연구는 새로운 Tableau calculus를 제안하지 않으며, TruthFinder나 CATD를 대체하는 일반적인 SOTA truth-discovery algorithm을 주장하지도 않는다.

---

# 2. Related Work

## 2.1 Truth Discovery

Truth Discovery는 동일 object에 대해 여러 source가 서로 다른 값을 제공할 때 source reliability와 value confidence를 함께 추정하는 연구 분야이다. TruthFinder는 “신뢰할 수 있는 source가 제공한 fact는 더 신뢰할 수 있고, 신뢰할 수 있는 fact를 많이 제공하는 source는 더 신뢰할 수 있다”는 상호 강화 구조를 사용한다. 이후 source dependence, value similarity, Bayesian inference, latent truth, long-tail source participation 등 여러 문제를 다루는 방법들이 제안되었다.

CATD는 source가 제공하는 claim 수가 매우 불균형한 long-tail 상황에서 적은 claim을 가진 source의 reliability estimation uncertainty를 고려한다. 이는 source reliability의 통계적 신뢰도를 다룬다는 점에서 본 연구보다 정교한 부분이다.

**차이점:** 전통적 Truth Discovery의 중심 대상은 `source ↔ claimed value` 관계이다. 본 연구는 claim이 규칙 또는 ontology를 통해 다른 명제로 파생되어 충돌할 수 있다는 경우에 대비하여 `source ↔ claim ↔ derivation ↔ conflict` provenance를 명시적으로 보존하는 것을 목표로 한다.

## 2.2 Constrained Truth Discovery

Constrained Truth Discovery는 denial constraint와 같은 first-order logical constraint를 truth discovery 최적화에 통합한다. 따라서 “logic을 truth discovery에 사용한다”는 주장 자체는 본 연구의 novelty가 될 수 없다.

**차이점:** constraint-based truth discovery는 논리 제약을 candidate truth의 feasible space 또는 optimization constraint로 사용한다. 본 연구가 강조하는 것은 constraint 존재 자체보다 **어떤 source claim이 어떤 derivation을 거쳐 어떤 다른 claim과 conflict했는지에 대한 proof provenance를 output과 truth score에 연결하는 것**이다.

이 차이는 향후 반드시 동일 데이터와 동일 constraint 조건에서 직접 비교되어야 하며, 현재 실험만으로 Constrained Truth Discovery보다 우수하다고 주장하지 않는다.

## 2.3 Ontology-Aware Truth Discovery

Beretta et al.은 claim value 사이의 semantic relation과 partial ordering을 활용하여 단일 값만을 truth로 가정하는 전통적 truth-finding의 한계를 완화했다. 예를 들어 `Málaga`와 `Spain`처럼 서로 다른 수준의 값이 동시에 참일 수 있는 경우를 다룬다.

이 연구는 본 논문의 DAFNA 실험과 특히 관련이 깊다. `Author A`와 `Author A; Author B`가 항상 상호 배타적인 값은 아니며, 전자는 후자의 부분 정보일 수 있기 때문이다.

**차이점:** ontology-aware truth discovery는 value 간 semantic relation을 truth estimation에 이용한다. 본 연구는 이를 더 일반적인 provenance architecture로 연결하고, semantic compatibility를 단순 truth score뿐 아니라 `partial` vs `conflict` localization에도 이용한다. 다만 ontology semantic relation 활용 자체는 기존 연구의 기여임을 명확히 인정한다.

## 2.4 Standpoint Logic

Standpoint Logic은 서로 다른, 심지어 충돌하는 관점을 하나의 논리 체계에서 표현하기 위한 formalism이다. Standpoint EL과 Standpoint EL+은 Description Logic 환경에서 tractable multi-perspective reasoning을 다루며, 기존 reasoner와 연결 가능한 번역 및 deduction 방법도 제시되어 있다.

**차이점:** Standpoint Logic의 핵심 문제는 perspective-aware knowledge representation과 entailment이다. 본 연구의 최종 문제는 여러 source의 truthfulness가 알려져 있지 않은 상황에서 **conflict provenance를 유지한 뒤 candidate truth를 선택하는 data fusion 문제**이다. 따라서 Standpoint Logic은 본 연구보다 perspective semantics 측면에서 더 강한 formalism이며, 본 연구는 source reliability와 truth resolution에 초점을 둔 operational pipeline이다.

## 2.5 Multi-Context Systems

Multi-Context Systems는 서로 다른 logic과 knowledge base가 bridge rule을 통해 연결되는 상황을 모델링한다. Eiter et al.은 bridge rule 조합을 중심으로 inconsistency explanation과 repair를 연구하였다.

**차이점:** MCS는 heterogeneous reasoning system의 consistency management를 다룬다. 본 연구는 동일 또는 정규화 가능한 proposition vocabulary를 전제로 하고, inconsistency repair보다 “어느 competing claim이 gold truth에 가까운가”를 평가하는 데 초점을 둔다.

## 2.6 Axiom Pinpointing

Axiom Pinpointing은 어떤 ontology axiom subset이 특정 consequence를 발생시키는지 계산한다. Tableau 기반 axiom pinpointing은 이미 오래전부터 multiple minimal justification을 다룬다.

**차이점:** 따라서 multiple proof를 찾는 것 자체는 본 연구의 novelty가 아니다. 본 연구에서는 justification/proof를 **truth resolution에 사용할 provenance evidence**로 해석한다. 즉 proof는 최종 산출물이 아니라 source reliability와 candidate truth를 평가하기 위한 중간 구조이다.

## 2.7 Positioning Summary

| Research line | Main question | Perspective / source | Logic / semantics | Source reliability | Explicit conflict provenance | Truth resolution |
|---|---|---:|---:|---:|---:|---:|
| Tableau / Hypertableau | Is the KB satisfiable? | No | Yes | No | proof-level | No |
| Axiom Pinpointing | Which axioms caused an entailment? | No | Yes | No | Yes | No |
| Standpoint Logic | What follows under different standpoints? | Yes | Yes | No | perspective semantics | No |
| Multi-Context Systems | How do contexts interact and become inconsistent? | Yes | Yes | No | bridge-rule explanation | repair-oriented |
| TruthFinder | Which conflicting value is likely true? | source | Limited | Yes | No derivation path | Yes |
| CATD | How reliable is truth discovery under long-tail participation? | source | Limited | Yes + confidence | No derivation path | Yes |
| Constrained Truth Discovery | How can logical constraints improve truth discovery? | source | **Yes** | Yes | constraint-oriented | Yes |
| Ontology-aware truth finding | How do semantic value relations affect truth? | source/value | **Yes** | Yes | value relation | Yes |
| **Rashomon-Tableau** | Which claim conflicts, through what path, and which truth is best supported? | **Yes** | **Yes** | **Yes** | **Source→Claim→Derivation→Conflict** | **Yes** |

The last row should be read as a **combination and operationalization claim**, not as a claim that every individual component is new.

---

# 3. Problem Formulation

## 3.1 Sources and Claims

Let the set of sources be:

$$
S = \{s_1, s_2, \ldots, s_m\}
$$

For object $o$, source $s_i$ provides a claim $c_{i,o}$. A claim can contain one or more atomic propositions.

For example:

```text
"Book X has authors Alice and Bob"
```

is represented as:

$$
C_{i,o} = \{AuthorOf(Alice,o), AuthorOf(Bob,o)\}
$$

This decomposition matters because a claim containing only Alice may be incomplete but still compatible with the richer truth `{Alice, Bob}`.

## 3.2 Semantic Closure

Let $T$ denote shared logical or ontological rules. The closure of claim set $C$ is:

$$
Cl_T(C) = \{q \mid T \cup C \models q\}
$$

In a general domain, a conflict exists when both a proposition and its negation are derivable:

$$
q \in Cl_T(C_i)
$$

and

$$
\neg q \in Cl_T(C_j)
$$

For DAFNA Books, the available benchmark does not provide rich ontology rules, so the real-data evaluation mainly uses conjunction/set semantics rather than a deep ontology closure. This limitation is discussed later.

## 3.3 Claim Relationship

Given a candidate truth set $G_o$, a source claim $C_{i,o}$ is classified as:

- **Exact:** $C_{i,o} = G_o$
- **Partial:** $C_{i,o} \subset G_o$
- **Conflict:** $C_{i,o}$ asserts at least one atom outside $G_o$

This three-way distinction is important because whole-value truth-discovery algorithms can treat `{Alice}` and `{Alice, Bob}` as two different candidate values even though the former may be a correct partial observation.

## 3.4 Source Reliability

Each source has reliability:

$$
r_i \in [0,1]
$$

The proposed implementation initializes all sources with the same prior and iteratively updates reliability according to compatibility between the source's claims and the current candidate truth.

For claim $C$ and candidate truth $G$, compatibility is based on overlap precision and recall:

$$
Compat(C,G) = 0.85 \cdot P(C,G) + 0.15 \cdot R(C,G)
$$

where:

$$
P(C,G) = \frac{|C \cap G|}{|C|}
$$

and

$$
R(C,G) = \frac{|C \cap G|}{|G|}
$$

The larger weight on precision means that asserting a false extra author is penalized more strongly than omitting a valid co-author.

## 3.5 Atomic Truth Support

For candidate atomic proposition $a$, support is the reliability-weighted sum of sources asserting it:

$$
Support(a,o) = \frac{\sum_{i:a\in C_{i,o}} r_i}{\sum_{i} r_i}
$$

Candidate atoms are ranked by support. The current prototype selects atoms whose support exceeds a relative threshold against the best-supported atom, with an evidence-based cardinality cap derived from observed claim size.

This is a lightweight prototype rather than a fully learned probabilistic model.

---

# 4. Proposed Framework

## 4.1 Stage 1: Semantic Logical Reasoning

The semantic reasoning layer answers whether a query follows from explicit claims and shared rules. Entailment can be checked through refutation:

$$
KB \models q
$$

iff

$$
SAT(KB \cup \{\neg q\}) = 0
$$

The role of this layer is not to perform truth discovery. It produces logically expanded claims and proof traces that later stages can use.

### Example

Given:

$$
P(a) \rightarrow Q(a)
$$

and

$$
\neg Q(a)
$$

querying $\neg P(a)$ can be resolved by adding $P(a)$ and deriving a clash between $Q(a)$ and $\neg Q(a)$.

## 4.2 Stage 2: Provenance-Aware Conflict Localization

Each derived proposition is stored with provenance:

```text
(source_id, original_claim, applied_rule, derived_claim)
```

A conflict can therefore be represented as a graph:

```text
Source A
   ↓
Claim A
   ↓ rule r1
Derived proposition q
   X
Derived proposition NOT q
   ↑ rule r2
Claim B
   ↑
Source B
```

The key property is that inconsistency does not erase the path by which it was produced.

For multi-valued claims, the current real-data prototype also uses proposition-level relationships:

```text
Gold / candidate truth = {A, B}

Source 1 = {A, B}  → exact
Source 2 = {A}     → partial
Source 3 = {C}     → conflict
```

This prevents an incomplete but correct source from being treated identically to a source asserting an incompatible value.

## 4.3 Stage 3: Rashomon Truth Resolution

The word Rashomon is used as a problem metaphor: conflicting accounts are kept rather than prematurely discarded. The algorithm does not assume that disagreement itself determines truth.

The resolution layer iterates between:

1. estimating source reliability,
2. accumulating atomic support,
3. constructing candidate truth,
4. re-evaluating each source against the candidate truth.

A general future form of the score is:

$$
TruthScore(q) =
\alpha SourceSupport(q)
+ \beta LogicalSupport(q)
+ \gamma CrossSourceAgreement(q)
- \delta ConflictPenalty(q)
$$

The current DAFNA implementation instantiates the source-support and proposition-compatibility terms; ontology-derived proof support is evaluated separately through the logical benchmarks because DAFNA does not provide rich rules.

---

# 5. Experimental Design

## 5.1 Why the Evaluation Is Split

No dataset used in this study simultaneously provides all of the following:

- multiple identifiable sources,
- natural-language or symbolic rules,
- ontology-mediated implicit contradiction,
- source-level provenance,
- competing truth candidates,
- independent gold truth.

Therefore the paper uses a **component-wise validation** rather than claiming a single end-to-end benchmark.

| Research question | Dataset | What is evaluated |
|---|---|---|
| RQ1 Logical Reasoning | FOLIO | semantic entailment / contradiction core |
| RQ1 + dual-direction contradiction | LogicNLI `test_logic` | support for both proposition and negation |
| RQ2 Conflict Localization | DAFNA-EA Books | exact / partial / conflict claim classification |
| RQ3 Truth Resolution | DAFNA-EA Books | recovery of gold author set |

## 5.2 FOLIO

FOLIO is a first-order logical reasoning benchmark with natural-language premises and FOL annotations. The current implementation does **not** support the full FOL grammar. It supports ground facts/conjunctions, universal Horn implications, explicit negation, and a single ground-literal query.

Only 28 of 204 validation examples satisfy this strict supported grammar, so the reported FOLIO result is a component validation rather than a competitive full-dataset score.

## 5.3 LogicNLI

LogicNLI defines four reasoning states: entailment, contradiction, neutral, and paradox/self-contradiction. The experiment uses the official structured `test_logic` representation rather than natural-language input.

The main comparison is between a single-path decision that can stop after finding support for one direction and a dual-direction procedure that checks whether both $q$ and $\neg q$ are derivable.

## 5.4 DAFNA-EA Books

The main real-data truth-resolution benchmark is DAFNA-EA Books. The claim file contains online-source claims for book authors, and the gold file provides independently validated author information for 100 books in the available gold subset used by the evaluator.

After filtering to gold objects and collapsing repeated claims from the same source-object pair, the experiment contains:

- **100** gold books,
- **1,999** source-object claims,
- **227** unique sources.

All compared methods use the same benchmark-side author canonicalization to reduce surface variations such as `Knuth, Donald E.` versus `Donald E. Knuth`. Therefore normalization does not give a unique advantage to the proposed method.

## 5.5 Baselines

### Whole-Claim Majority

The most frequent complete author set for an ISBN is selected.

### Reliability-Weighted Whole-Claim Vote

An iterative local baseline jointly updates source reliability and whole-value support. A source receives full agreement credit only when its complete author set equals the selected candidate.

**Important:** this implementation is **not** an exact reproduction of TruthFinder, CATD, DART, or another published method. It is used to isolate the effect of source-reliability weighting while keeping the experiment executable in the repository.

### Proposed Atomic Resolution

Author lists are decomposed into atomic `AuthorOf` propositions. Partial subsets are compatible evidence. Atomic support is weighted by source reliability, and source reliability is updated from proposition-level compatibility.

## 5.6 Metrics

### Exact-Set Accuracy

A prediction is correct only when the predicted author set equals the gold author set exactly.

$$
Accuracy_{set} = \frac{Correct\ exact\ sets}{All\ gold\ objects}
$$

### Author-Level F1

For each object, precision and recall are computed over predicted and gold authors, followed by F1.

$$
F1 = \frac{2PR}{P+R}
$$

### Conflict Localization Macro-F1

Each source claim is labelled `exact`, `partial`, or `conflict` relative to gold truth. Macro-F1 gives each relation class equal weight.

---

# 6. Results

## 6.1 RQ1: Logical Reasoning — FOLIO

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Direct Fact | 42.86% | 26.71% |
| Forward Horn | 75.00% | 74.18% |
| **Semantic Clause Tableau** | **96.43%** | **96.33%** |

On the 28-example supported fragment, semantic satisfiability reasoning improves Accuracy by 21.43 percentage points and Macro-F1 by 22.15 points over the forward-Horn baseline.

This result supports the use of a semantic reasoning core but **must not be interpreted as 96.43% accuracy on full FOLIO**. Grammar coverage is only 13.73% of the validation set.

## 6.2 RQ1: Opposing Proof Directions — LogicNLI

| Method | Accuracy | Macro-F1 | Paradox F1 |
|---|---:|---:|---:|
| Direct Fact Dual Check | 50.55% | 42.88% | 0.40% |
| Single-Path Forward | 74.00% | 65.78% | 0.00% |
| **Dual-Direction Proof Check** | **98.40%** | **98.40%** | **97.92%** |

The result shows why a reasoner should not stop after finding one supported conclusion. When both $q$ and $\neg q$ are derivable, a single-path procedure collapses the contradictory evidence into one class.

Again, the result is for LogicNLI's structured logical representation and is not an end-to-end NLP comparison with BERT, RoBERTa, or LLM systems.

## 6.3 RQ3: Real-Data Truth Resolution — DAFNA-EA Books

| Method | Exact Set Accuracy | Mean Author Precision | Mean Author Recall | Mean Author F1 |
|---|---:|---:|---:|---:|
| Whole-Claim Majority | 44.00% | 94.00% | 65.43% | 73.57% |
| Reliability-Weighted Whole Claim | 45.00% | **96.00%** | 66.93% | 75.24% |
| **Proposed Atomic Truth Resolution** | **61.00%** | 95.67% | **78.39%** | **82.88%** |

The proposed method improves exact-set accuracy by **16.0 percentage points** over the reliability-weighted baseline.

Mean author F1 improves by **7.64 percentage points**. The main change is recall: 66.93% to 78.39%, while precision remains similar (96.00% vs 95.67%).

This pattern is consistent with the design goal. Whole-claim voting can select a frequently repeated but incomplete author list. Atomic aggregation can recover additional co-authors supported across different partial observations without accepting every conflicting value.

## 6.4 RQ2: Real-Data Conflict Localization

The gold relation distribution over the 1,999 source claims is:

| Gold relation | Count |
|---|---:|
| Exact | 903 |
| Partial | 585 |
| Conflict | 511 |

The localization result is:

| Method | Claim-Level Accuracy | Macro-F1 |
|---|---:|---:|
| Whole-Claim Majority | 60.68% | 49.04% |
| Reliability-Weighted Whole Claim | 62.08% | 50.37% |
| **Proposed Atomic Truth Resolution** | **76.69%** | **74.58%** |

Compared with the reliability-weighted baseline, claim-level accuracy improves by **14.61 percentage points** and Macro-F1 by **24.21 percentage points**.

The particularly large Macro-F1 gain matters because whole-claim methods almost never represent the `partial` relation explicitly. They tend to collapse a correct incomplete claim into either the selected exact value or a competing value. Proposition decomposition provides a separate state for partial support.

## 6.5 Why the Old Synthetic 100% Result Is Not a Main Result

Earlier development versions included a controlled four-class benchmark on which perspective-indexed reasoning obtained 100% accuracy. That result is intentionally **not used as a headline empirical claim** in this paper.

A benchmark generated directly from the protocol's own definition is useful for unit/capability testing but weak evidence of real-world generalization. The main empirical claims now rely on DAFNA-EA's independent gold truth, while controlled cases remain repository tests only.

---

# 7. Analysis

## 7.1 What Actually Produced the DAFNA Improvement?

The real-data gain should not be attributed to Tableau alone. DAFNA Books does not provide rich logical rules. The main mechanism is **structural claim decomposition with provenance-preserving reliability weighting**.

Consider three author claims:

```text
S1: {A, B}
S2: {A}
S3: {C}
```

A whole-value model sees three competing values.

```text
{A,B} != {A} != {C}
```

The proposed representation sees:

```text
S1 supports A and B
S2 supports A
S3 supports C
```

If the truth is `{A,B}`, S2 is incomplete but not false. This distinction improves both truth recall and conflict localization.

## 7.2 Why Call It Provenance-Aware?

The resolver does not only return an author atom. It can retain the list of source IDs that support the atom and its support score. In a domain with ontology rules, the same structure can be extended to retain rule IDs and intermediate propositions.

```text
candidate truth atom
    ↑
weighted support
    ↑
source claims
    ↑
source reliability
```

or, with ontology inference:

```text
candidate proposition
    ↑
derived proposition
    ↑ rule
original claim
    ↑
source
```

This is the intended bridge between symbolic reasoning and truth discovery.

## 7.3 Rashomon as Conflict-Preserving Truth Seeking

The term Rashomon is not used here to mean that all conflicting accounts are equally true. Nor does the method adopt the ML Rashomon-set definition as its objective function.

Instead the term describes the methodological stance:

> **Do not eliminate one account before understanding how the accounts conflict. Preserve the disagreement, trace its logical support, and only then resolve the truth.**

This distinction is important. The output is ultimately a ranked candidate truth, not an unordered set of equally accepted answers.

## 7.4 Relation to TruthFinder

TruthFinder already models the feedback loop between source trustworthiness and fact confidence. Therefore source reliability iteration is not novel.

The proposed method differs in where evidence is attached. Instead of only associating reliability with complete candidate values, it can attach support to atomic propositions and, in the general architecture, to derived propositions with rule provenance.

The current experiment does **not** implement official TruthFinder and thus does not claim an empirical victory over TruthFinder. An exact DAFNA-EA TruthFinder/CATD comparison is future work and should be included before making a SOTA claim.

## 7.5 Relation to Constrained Truth Discovery

Constrained Truth Discovery is a particularly important baseline because it already introduces first-order logical constraints into truth discovery. The present work should therefore be understood as shifting emphasis from **constraint satisfaction** to **traceable conflict evidence**.

A future head-to-head comparison should answer:

- Do explicit proof paths improve truth accuracy beyond constraints alone?
- Do they improve conflict localization or explanation fidelity even when truth accuracy is similar?
- What is the computational overhead of maintaining provenance?

These questions are more defensible novelty claims than simply saying “we add logic to truth discovery.”

---

# 8. Threats to Validity and Limitations

## 8.1 No Single End-to-End Benchmark

The largest limitation is that the logical core and truth-resolution layer are validated on different datasets. FOLIO/LogicNLI contain logical structure but not source-reliability gold truth; DAFNA contains real conflicting sources and gold truth but little ontology structure.

Therefore the paper demonstrates **component validity**, not complete end-to-end superiority.

## 8.2 FOLIO Grammar Coverage

Only 28 of 204 FOLIO validation examples are supported. The current parser must be expanded to existential quantification, disjunction, biconditional, and richer first-order formulas before full benchmark comparison is meaningful.

## 8.3 Structured LogicNLI

The LogicNLI experiment bypasses natural-language semantic parsing. It measures symbolic reasoning quality, not end-to-end NLI performance.

## 8.4 DAFNA Name Canonicalization

Author identity normalization is heuristic. Surname + first initial can merge distinct people or fail on malformed author strings. The same normalization is applied to all methods, but absolute metric values remain sensitive to entity-resolution quality.

## 8.5 Baseline Scope

The current reliability-weighted baseline is deliberately simple and reproducible, but it is not an exact reproduction of TruthFinder, CATD, AccuSim, LTM, or Constrained Truth Discovery. Before publication at a strong venue, official or faithful implementations of major truth-discovery baselines should be added.

## 8.6 Current Truth Score Is Heuristic

The compatibility weights and support threshold are fixed heuristic parameters. They should be tuned only on a training/development split and evaluated on a held-out test split to avoid hidden benchmark fitting.

## 8.7 Objective Truth Is Not Always Unique

Some domains contain genuinely multiple truths, evolving truths, or unresolved evidence. A production system should support `Truth / False / Unresolved` or a calibrated probability rather than forcing every case into a single answer.

---

# 9. Future Work

The strongest next experiments are:

1. **Official DAFNA algorithm baselines:** run TruthFinder, 2-Estimates, 3-Estimates, Accu/AccuSim, SimpleLCA, and LTM on the same canonicalized objects where protocol compatibility allows.
2. **Constrained Truth Discovery baseline:** compare proof-provenance evidence with denial-constraint optimization under the same constraints.
3. **Ontology-rich multi-source benchmark:** construct or annotate a dataset with source IDs, ontology rules, implicit conflicts, and external truth labels in the same examples.
4. **Held-out parameter evaluation:** split DAFNA objects into development/test sets and tune threshold parameters only on development.
5. **Calibration:** evaluate Brier score or expected calibration error for truth confidence.
6. **Provenance ablation:** remove rule paths, source IDs, atomic decomposition, and reliability one at a time.
7. **Human explanation study:** test whether explicit `Source → Claim → Rule → Conflict → Truth` traces improve users' ability to audit a resolved fact.

---

# 10. Conclusion

This paper reframes Rashomon-Tableau around a narrower and more defensible problem: **finding the most defensible truth from conflicting sources without discarding the conflict structure that explains why the sources disagree**.

The framework separates three functions. Semantic reasoning determines what claims logically imply. Conflict localization retains source and derivation provenance so that disagreement can be attributed to concrete claims or rule paths. Truth resolution then combines source reliability with proposition-level compatibility and cross-source support.

The real-data DAFNA-EA Books evaluation provides the strongest current evidence. Exact gold-truth recovery increases from 45% for a reliability-weighted whole-claim baseline to 61% for atomic provenance-aware resolution, while author-level F1 increases from 75.24% to 82.88%. Claim-level conflict localization Macro-F1 increases from 50.37% to 74.58%. These are not synthetic 100% capability scores; they are measured against independent gold truth on conflicting real-source data.

At the same time, the work should not be presented as the first multi-perspective logic, the first use of logic in truth discovery, or the first multiple-proof method. Standpoint Logic, Multi-Context Systems, Axiom Pinpointing, TruthFinder, CATD, Constrained Truth Discovery, and ontology-aware truth finding already cover those individual ideas. The potential contribution lies in connecting them through **explicit source-to-proof provenance and using localized conflict evidence as an input to truth resolution**.

Whether this architecture remains beneficial against faithful state-of-the-art truth-discovery and constrained-reasoning baselines is the key question for the next stage of the research.

---

# References

[1] Yin, X., Han, J., & Yu, P. S. (2008). **Truth Discovery with Multiple Conflicting Information Providers on the Web.** IEEE Transactions on Knowledge and Data Engineering, 20(6), 796–808. DOI: 10.1109/TKDE.2007.190745.

[2] Li, Q., Li, Y., Gao, J., Su, L., Zhao, B., Demirbas, M., Fan, W., & Han, J. (2014). **A Confidence-Aware Approach for Truth Discovery on Long-Tail Data.** Proceedings of the VLDB Endowment, 8(4), 425–436. DOI: 10.14778/2735496.2735505.

[3] Waguih, D. A., & Berti-Équille, L. (2014). **Truth Discovery Algorithms: An Experimental Evaluation.** arXiv:1409.6428. DAFNA-EA implementation and datasets.

[4] Li, Y., et al. (2022). **Constrained Truth Discovery.** IEEE Transactions on Knowledge and Data Engineering, 34(1), 205–218. DOI: 10.1109/TKDE.2020.2982393.

[5] Beretta, V., Harispe, S., Ranwez, S., & Mougenot, I. (2016). **How Can Ontologies Give You Clue for Truth-Discovery? An Exploratory Study.** DOI: 10.1145/2912845.2912848.

[6] Gómez Álvarez, L., Rudolph, S., & Strass, H. (2022). **How to Agree to Disagree: Managing Ontological Perspectives using Standpoint Logic.** arXiv:2206.06793.

[7] Gómez Álvarez, L., Rudolph, S., & Strass, H. (2023). **Pushing the Boundaries of Tractable Multiperspective Reasoning: A Deduction Calculus for Standpoint EL+.** KR 2023.

[8] Eiter, T., Fink, M., Schüller, P., & Weinzierl, A. (2014). **Finding Explanations of Inconsistency in Multi-Context Systems.** Artificial Intelligence, 216, 233–274. DOI: 10.1016/j.artint.2014.07.008.

[9] Baader, F., & Peñaloza, R. (2010). **Axiom Pinpointing in General Tableaux.** Journal of Logic and Computation, 20(1), 5–34. DOI: 10.1093/logcom/exn058.

[10] Tian, J., Li, Y., Chen, W., Xiao, L., He, H., & Jin, Y. (2021). **Diagnosing the First-Order Logical Reasoning Ability Through LogicNLI.** EMNLP 2021.

[11] Han, S., et al. (2024). **FOLIO: Natural Language Reasoning with First-Order Logic.** EMNLP 2024.

[12] Motik, B., Shearer, R., & Horrocks, I. (2009). **Hypertableau Reasoning for Description Logics.** Journal of Artificial Intelligence Research, 36, 165–228.

---

## Reproducibility

Repository scripts used for the reported results:

```text
scripts/evaluate_folio_fragment.py
scripts/evaluate_logicnli.py
scripts/evaluate_truth_discovery_books.py
```

Measured real-data result:

```text
results/truth_discovery_books_metrics.json
```

GitHub Actions real-data validation run:

```text
Run ID: 32706842910
Artifact ID: 9512567772
```

The DAFNA evaluator downloads the public claim and gold files directly from the `qcri/DAFNA-EA` repository. The result file records the exact sample counts and metrics used in this manuscript.
