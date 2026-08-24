# Rashomon-Tableau: Perspective-Indexed Tableau Reasoning for Contradiction Localization and Multi-Proof Preservation

## 라쇼몽-태블로: 모순 위치 식별과 복수 증명 보존을 위한 관점 인덱스 기반 Tableau 추론

---

## 초록

Tableau 기반 논리 추론은 주어진 지식베이스가 만족가능한지(SAT) 또는 모순되는지(UNSAT)를 엄밀하게 판정하는 데 사용되어 왔다. 그러나 서로 다른 화자, 문서, 시점, 센서 또는 에이전트가 제공한 사실을 하나의 지식베이스로 병합하면 두 종류의 정보가 손실될 수 있다. 첫째, 모순이 특정 context 내부에 이미 존재했는지, 아니면 각각은 일관적인 두 context를 결합했을 때 새롭게 발생했는지를 구분하기 어렵다. 둘째, 동일한 모순을 설명하는 여러 독립적인 최소 증명이 존재하더라도 하나의 proof만 반환하면 설명의 다양성이 사라진다.

본 연구는 이 문제를 해결하기 위해 **Rashomon-Tableau**를 제안한다. 제안 방법은 새로운 Tableau calculus를 제안하는 것이 아니라 기존 satisfiability reasoning을 세 계층으로 확장한다. 첫째, **Semantic Tableau**가 논리적 entailment와 contradiction을 판정한다. 둘째, **Perspective Index**가 각 context의 ABox를 분리하여 `SAT(T∪A_i)`, `SAT(T∪A_j)`, `SAT(T∪A_i∪A_j)`를 각각 검사함으로써 `Consistent`, `Divergence`, `Intra-Contradiction`, `Inter-Contradiction`을 구분한다. 셋째, UNSAT 사례에 대해 Minimal Unsatisfiable Subset(MUS)을 복수로 추출하고, 단일 최적 proof 대신 거의 동등하게 타당한 proof들을 **Rashomon Explanation Set**으로 보존한다.

각 기여를 서로 다른 실험으로 분리하여 검증하였다. 공식 **FOLIO v0.0 validation** 204개 중 현재 reasoner가 완전하게 지원하는 Horn/explicit-negation fragment 28개에서 Semantic Clause Tableau는 Accuracy **96.43%**, Macro-F1 **96.33%**를 기록하여 Forward-Horn baseline보다 각각 **+21.43 pp**, **+22.15 pp** 향상되었다. 공식 **LogicNLI `test_logic`** 2,000개 statement에서는 하나의 지지 경로를 찾은 뒤 판정을 종료하는 single-path 방식이 Accuracy **74.00%**, Macro-F1 **65.78%**, `self_contradiction(Paradox)` F1 **0%**를 기록한 반면, 명제와 부정 명제의 두 증명 방향을 모두 검사하는 dual-proof 방식은 Accuracy **98.40%**, Macro-F1 **98.40%**, Paradox F1 **97.92%**를 기록하여 각각 **+24.40 pp**, **+32.63 pp**, **+97.92 pp** 향상되었다. 80개의 multi-context controlled benchmark에서는 merged-ABox Tableau의 Accuracy 75.00%, Macro-F1 66.67%가 Perspective-Indexed Tableau에서 모두 100%로 향상되어 **+25.00 pp**, **+33.33 pp**의 개선을 보였다. 마지막으로 두 개의 독립적 MUS를 갖는 20개 사례에서 single-proof explanation coverage 50%에 비해 Rashomon proof set은 100%를 보존하여 **+50.00 pp** 향상되었다.

이 결과는 Rashomon-Tableau가 모든 데이터셋에서 하나의 동일한 이유로 Accuracy를 높인다는 주장이 아니다. **Semantic Tableau는 논리 추론 정확성, Perspective Index는 모순의 발생 위치, Rashomon layer는 복수 proof 보존**을 각각 담당한다. CONAN 탐정 서사는 이러한 multi-perspective reasoning을 보여주는 응용 데이터셋일 뿐이며, 제안 방법은 다중 출처 뉴스, 법률 진술, 시스템 로그, 데이터 스냅샷, 멀티에이전트 가설 등 context provenance가 중요한 문제로 일반화될 수 있다.

**주요어:** Tableau Algorithm, Rashomon Effect, Satisfiability, Contradiction Localization, Perspective-Aware Reasoning, Minimal Unsatisfiable Subset, Multi-Proof Reasoning, Neuro-Symbolic AI

---

# 1. 서론

## 1.1 연구 배경

논리 추론에서 Tableau가 답하는 기본 질문은 단순하다.

> **주어진 명제들이 동시에 참일 수 있는가?**

Tableau 계열 알고리즘은 논리식을 규칙에 따라 확장하면서 가능한 branch를 구성하고, branch 안에 `φ`와 `¬φ`가 동시에 존재하는 clash가 발생하면 해당 branch를 닫는다. 모든 branch가 닫히면 지식베이스는 UNSAT, 하나 이상의 open branch가 남으면 SAT이다. Description Logic과 Ontology Reasoning에서는 이러한 tableau-like reasoning이 concept satisfiability, consistency, subsumption 등을 판정하는 핵심 기법으로 사용되어 왔다.

그러나 실제 지식은 보통 하나의 homogeneous source에서만 오지 않는다.

```text
Witness A
Witness B
News Source A
News Source B
Sensor A
Sensor B
Database snapshot t1
Database snapshot t2
Agent hypothesis A
Agent hypothesis B
```

이러한 정보를 출처 구분 없이 하나의 지식베이스로 병합하면 Tableau는 전체가 UNSAT이라는 사실은 발견할 수 있지만 **모순의 위치(scope)**를 잃을 수 있다.

예를 들어 다음 두 경우는 논리적으로 다른 문제다.

```text
Case A — Intra contradiction
Perspective 1: P(a), NOT P(a)
Perspective 2: Q(b)

Case B — Inter contradiction
Perspective 1: P(a)
Perspective 2: NOT P(a)
```

Merged Tableau는 두 경우 모두 다음 결과만 낸다.

```text
SAT(T ∪ A1 ∪ A2) = 0
```

그러나 Case A는 첫 번째 source 자체의 consistency 문제이고, Case B는 두 source 사이의 conflict이다. 실제 시스템에서는 대응 방법도 다르다.

두 번째 문제는 **설명의 단일화**이다. 하나의 UNSAT 결과가 여러 독립적인 최소 충돌로 설명될 수 있는데 reasoner가 첫 번째 proof만 반환하면 사용자는 다른 동등하게 타당한 원인을 볼 수 없다.

본 연구는 이 두 문제를 하나의 일관된 질문으로 묶는다.

> **모순이 존재하는가뿐 아니라, 어디에서 발생했고, 그 모순을 설명하는 타당한 proof가 몇 개인가를 함께 보존할 수 있는가?**

## 1.2 핵심 주장

본 논문의 핵심 주장은 다음 하나이다.

> **기존 Tableau satisfiability reasoning을 context별로 인덱싱하면 논리적 엄밀성을 유지하면서 contradiction scope를 식별할 수 있으며, 그 과정에서 발견되는 여러 최소 contradiction proof를 Rashomon set으로 보존하면 single-proof selection에 의한 설명 손실을 줄일 수 있다.**

이를 세 계층으로 구분한다.

```text
[Layer 1] Semantic Tableau
           ↓
    논리적으로 참/거짓/불확실한가?

[Layer 2] Perspective Index
           ↓
    모순이 한 context 내부인가?
    두 context 사이에서 생기는가?

[Layer 3] Proof Rashomon Set
           ↓
    동일 결론에 타당한 설명이 여러 개인가?
```

세 계층은 서로 다른 성능 개선을 담당한다. 따라서 본 논문은 하나의 Accuracy 숫자로 모든 기여를 주장하지 않는다.

## 1.3 연구 질문

**RQ1 — Logical Reasoning**  
Semantic Tableau는 단순 fact lookup 또는 forward-only reasoning보다 외부 논리 benchmark에서 더 정확한 추론을 수행하는가?

**RQ2 — Contradiction Multiplicity**  
명제 `s`와 `¬s`의 양쪽 증명 가능성을 모두 검사하면 single-path 방식이 놓치는 paradox/self-contradiction을 더 잘 식별할 수 있는가?

**RQ3 — Contradiction Scope**  
Perspective별 SAT를 별도로 검사하면 merged-ABox Tableau가 구분하지 못하는 Intra/Inter contradiction을 식별할 수 있는가?

**RQ4 — Explanation Diversity**  
Rashomon proof set은 single-proof 방식보다 검증 가능한 대안 설명을 더 많이 보존하는가?

## 1.4 연구 기여

본 연구의 기여는 다음 네 가지이다.

1. **Perspective-Indexed Tableau protocol**  
   Tableau calculus 자체를 바꾸지 않고 context별 SAT를 분리하여 contradiction scope를 판정한다.

2. **Divergence ≠ Contradiction**  
   두 context가 다른 정보를 제공하더라도 union이 SAT이면 contradiction이 아닌 divergence로 구분한다.

3. **Dual-proof contradiction analysis**  
   `KB ⊢ s`와 `KB ⊢ ¬s`를 모두 검사하여 한 방향의 proof만 확인할 때 사라지는 paradox를 보존한다.

4. **Proof-space Rashomon Set**  
   Rashomon의 near-equivalent alternatives 개념을 predictive-model 공간이 아니라 contradiction-proof 공간으로 확장한다.

---

# 2. 이론적 배경과 선행연구

## 2.1 기존 연구에서 Tableau는 무엇을 하는가

Tableau는 일반적인 machine-learning classifier가 아니라 **논리적 만족가능성과 entailment를 판정하는 증명 절차**이다. Description Logic 분야에서 Baader와 Sattler는 주요 reasoning problem을 tableau-like algorithm으로 결정하는 방법을 체계화했다. 이후 OWL/DL reasoner 연구에서는 blocking, role restriction, cardinality와 같은 더 복잡한 표현을 처리하도록 calculus가 발전했고, HermiT은 classical Tableau를 발전시킨 hypertableau calculus를 사용한다.

전형적인 구조는 다음과 같다.

```text
Logical KB
   ↓
Expansion / branching
   ↓
Possible interpretations
   ↓
φ AND NOT φ ?
   ↓
Clash
   ↓
SAT / UNSAT
```

Entailment도 satisfiability로 변환할 수 있다.

```text
KB |= q
iff
SAT(KB ∪ {NOT q}) = 0
```

즉 Tableau의 강점은 확률 점수가 아니라 **명시적인 논리 consistency test**이다.

### 본 연구와의 차이

기존 연구의 주요 발전 방향은 대체로 다음과 같았다.

```text
더 표현력 있는 논리를
더 sound / complete / efficient하게 결정
```

본 연구는 새로운 DL constructor나 새로운 calculus를 제안하지 않는다. 대신 **동일한 SAT oracle을 provenance-aware하게 호출하는 protocol**을 제안한다.

```text
기존 merged reasoning:
SAT(T ∪ A1 ∪ A2)

제안:
SAT(T ∪ A1)
SAT(T ∪ A2)
SAT(T ∪ A1 ∪ A2)
```

따라서 본 연구의 novelty는 theorem proving 그 자체보다 **context-preserving contradiction semantics**에 있다.

## 2.2 Neuro-Symbolic Logical Reasoning

Logic-LM, LINC, SymbCoT 등 최근 연구는 LLM이 자연어 문제를 직접 끝까지 추론하게 하는 대신 자연어를 symbolic representation으로 변환하고 외부 solver 또는 구조화된 reasoning module을 사용한다.

Logic-LM은 `Natural Language → Symbolic Formulation → Deterministic Solver → Self-refinement` 구조를 사용하며, 다섯 개 logical reasoning benchmark에서 standard prompting과 CoT보다 평균 성능 향상을 보고하였다. 이는 language model이 추론과 formalization을 모두 내부적으로 처리하는 것보다 **symbolic inference를 분리하는 방식의 가능성**을 보여준다.

본 연구 역시 이 흐름과 호환된다. 다만 관심은 다음 단계에 있다.

```text
Natural Language
      ↓
Formalization
      ↓
[여기까지 기존 neuro-symbolic 연구]
      ↓
어느 source/context의 명제인가?
      ↓
Perspective-indexed satisfiability
      ↓
Multiple proof preservation
```

즉 LLM formalizer는 교체 가능한 front-end이며 본 연구의 주된 novelty가 아니다.

## 2.3 기존 Rashomon 연구는 무엇을 하는가

Rashomon Effect는 하나의 데이터에 대해 **거의 동일하게 좋은 성능을 갖는 여러 모델이 존재할 수 있다**는 문제를 다룬다. Breiman의 논의 이후 Fisher, Rudin, Dominici는 하나의 모델만 해석하면 다른 잘 맞는 모델에서 feature importance가 달라질 수 있음을 지적하고 전체 well-performing model class를 분석하는 Model Class Reliance를 제안했다. 이후 sparse decision tree 연구는 near-optimal tree의 Rashomon set 자체를 열거하여 여러 대안 모델을 동시에 분석했다.

일반적인 모델 Rashomon set은 다음과 같이 표현할 수 있다.

```text
R_ε
= { f : Loss(f) ≤ Loss(f*) + ε }
```

여기서 중요한 철학은 다음이다.

```text
Best model 하나만 의미 있다   X
여러 near-optimal model도 의미 있다 O
```

## 2.4 본 연구에서 Rashomon은 어떻게 쓰이는가

본 연구는 위 개념을 그대로 재사용한다고 주장하지 않는다. **Model space에서 proof space로의 방법론적 전이**를 제안한다.

```text
기존 Rashomon
Near-optimal predictive models

            ↓ conceptual transfer

Rashomon-Tableau
Near-equivalent valid contradiction proofs
```

모순 `c`에 대한 가능한 proof 집합을 `Π(c)`라 하고 각 proof의 간결성, provenance diversity, faithfulness를 score로 두면:

```text
R^proof_ε(c)
= { π ∈ Π(c) : Score(π) ≥ Score(π*) - ε }
```

이다.

현재 PoC의 score는 간결성과 perspective diversity를 단순 조합한다.

```text
Score(π)
= 1 / |π|
  + 0.05 × NumPerspectives(π)
```

즉 Rashomon은 **분류 정확도를 올리는 모듈이 아니라 설명 다양성을 보존하는 모듈**이다.

## 2.5 LogicNLI와 multiple proof

LogicNLI는 논리적 관계를 다음 네 상태로 정의한다.

```text
Entailment:
P ⊢ s, P ⊬ NOT s

Contradiction:
P ⊬ s, P ⊢ NOT s

Neutral:
P ⊬ s, P ⊬ NOT s

Paradox / self_contradiction:
P ⊢ s, P ⊢ NOT s
```

Paradox는 한 방향의 proof만 찾고 멈추면 식별할 수 없다. 따라서 LogicNLI는 본 연구의 **dual-proof preservation**을 CONAN과 무관하게 검증할 수 있는 적합한 외부 데이터셋이다.

## 2.6 P-FOLIO와 multiple reasoning chains

P-FOLIO는 human-written reasoning chain을 제공하고 생성 reasoning chain이 human chain과 다른 유효 경로를 가질 수 있다는 점을 고려하여 multiple sampling과 `pass@k`를 평가한다. 이는 같은 결론에 여러 reasoning path가 존재한다는 점에서 proof Rashomon 아이디어와 관련된다.

차이는 본 연구가 자연어 chain의 다양성보다 **symbolically verified MUS/proof set**을 직접 다룬다는 점이다.

## 2.7 연구 공백

| 연구 축 | 기존 강점 | 남는 문제 |
|---|---|---|
| Classical/DL Tableau | 엄밀한 SAT/UNSAT | source/context의 모순 위치를 별도 semantics로 다루지 않음 |
| Logic-LM/LINC | NL → Logic → Solver | provenance/perspective 분리가 주 목적이 아님 |
| LogicNLI | entail/contradiction/paradox 진단 | 여러 독립 source 사이의 scope 문제를 직접 다루지 않음 |
| Rashomon ML | 여러 near-optimal model 분석 | symbolic proof set을 대상으로 하지 않음 |
| P-FOLIO | multiple reasoning chain 평가 | contradiction scope localization이 목적이 아님 |

본 연구는 이 교차점을 다룬다.

```text
Satisfiability
      +
Context provenance
      +
Multiple valid proofs
```

---

# 3. 제안 방법

## 3.1 Perspective-Indexed Knowledge Base

관점 또는 context 집합을 다음과 같이 정의한다.

```text
P = {P1, P2, ..., Pm}
```

각 context의 사실 집합은:

```text
A_i = {φ_i1, φ_i2, ..., φ_in}
```

공통 규칙 또는 Ontology를 `T`라 하면:

```text
K_i = T ∪ A_i
```

이다.

여기서 Perspective는 사람으로 제한되지 않는다.

```text
person
news source
document
sensor
log source
timestamp
database snapshot
AI agent
competing hypothesis
```

## 3.2 Semantic Tableau Logical Core

현재 외부 benchmark에는 ground-clause semantic Tableau backend를 사용한다.

예를 들어:

```text
P(x) AND Q(x) -> R(x)
```

를 ground substitution 후:

```text
NOT P(a) OR NOT Q(a) OR R(a)
```

로 변환할 수 있다.

Query `R(a)`의 entailment는:

```text
SAT(KB ∪ {NOT R(a)})
```

가 UNSAT인지 검사한다.

## 3.3 Contradiction Scope

두 context `A_i`, `A_j`에 대해:

```text
s_i  = SAT(T ∪ A_i)
s_j  = SAT(T ∪ A_j)
s_ij = SAT(T ∪ A_i ∪ A_j)
```

를 계산한다.

판정 규칙:

```text
if s_i = 0 or s_j = 0:
    Intra-Contradiction

elif s_ij = 0:
    Inter-Contradiction

elif A_i != A_j:
    Divergence

else:
    Consistent
```

### 핵심 차이

Merged Tableau는 `s_ij`만 보므로:

```text
Intra → UNSAT
Inter → UNSAT
```

가 동일하게 보인다.

Perspective Index는 세 SAT 상태를 보존하므로 두 경우를 분리한다.

## 3.4 Dual-Proof Decision

하나의 statement `s`에 대해 두 방향을 모두 검사한다.

```text
proof_positive = KB ⊢ s
proof_negative = KB ⊢ NOT s
```

그 결과:

```text
positive only  → Entailment
negative only  → Contradiction
neither        → Neutral
both           → Paradox / Self-Contradiction
```

Single-path 방식은 positive proof를 찾은 순간 종료하면 `both` 상태를 잃는다.

## 3.5 MUS

UNSAT이 발생했을 때 실제 모순에 필요한 최소 사실 집합을 찾는다.

```text
MUS
= min_subset {M ⊆ A : SAT(T ∪ M)=0}
```

여러 개의 MUS가 존재하면 각각 독립적인 contradiction explanation 후보가 된다.

## 3.6 Rashomon Proof Set

모든 MUS/증명 후보에서 score가 최고 proof와 `ε` 이내인 것을 보존한다.

```text
R^proof_ε(c)
= {π : π proves c,
       Score(π) ≥ Score(π*) - ε}
```

이 layer의 출력은 하나의 label이 아니라:

```text
Proof 1
Proof 2
...
Proof k
```

이다.

---

# 4. 평가 지표

## 4.1 Accuracy

```text
Accuracy = Correct Predictions / Total Predictions
```

전체적인 정답 비율을 보여준다.

## 4.2 Precision과 Recall

특정 클래스 `c`에 대해:

```text
Precision_c = TP_c / (TP_c + FP_c)
Recall_c    = TP_c / (TP_c + FN_c)
```

Precision은 “이 클래스라고 예측한 것 중 실제로 맞은 비율”, Recall은 “실제 이 클래스인 것 중 찾아낸 비율”이다.

## 4.3 F1은 이 논문에서 무엇을 의미하는가

```text
F1_c
= 2 × Precision_c × Recall_c
  / (Precision_c + Recall_c)
```

F1은 Precision과 Recall의 **조화평균**이다. 둘 중 하나가 낮으면 F1도 크게 낮아진다.

예를 들어 80개 4-class benchmark에서 Vanilla merged Tableau가 60개를 맞히면:

```text
Accuracy = 60 / 80 = 75%
```

만 보면 꽤 높은 것처럼 보인다.

그러나 20개의 Intra-Contradiction을 전부 Inter로 분류하면:

```text
Intra Precision = 0
Intra Recall    = 0
Intra F1        = 0
```

이다.

즉 **F1은 특정 중요한 클래스를 완전히 놓치고 있는지를 보여준다.**

## 4.4 Macro-F1

모든 class F1을 동일하게 평균한다.

```text
Macro-F1
= (F1_1 + F1_2 + ... + F1_C) / C
```

본 연구에서는 `Consistent`, `Divergence`, `Intra`, `Inter`가 모두 의미적으로 중요하므로 class 수가 균등하지 않더라도 각 클래스를 동일 비중으로 평가하는 Macro-F1을 주요 지표로 사용한다.

## 4.5 Explanation Coverage

Gold minimal explanation 집합을 `G`, 시스템이 반환한 valid explanation 집합을 `E`라 하면:

```text
Explanation Coverage
= |E ∩ G| / |G|
```

이다.

## 4.6 Grammar Coverage

외부 FOL 데이터에서 현재 구현이 완전하게 지원하는 문법 범위도 함께 보고한다.

```text
Grammar Coverage
= Supported Examples / Total Examples
```

이를 숨기면 작은 쉬운 subset의 높은 Accuracy를 전체 성능처럼 오해할 수 있기 때문이다.

---

# 5. 실험 설계

본 연구는 하나의 데이터셋으로 모든 가설을 검증하지 않는다. 각 데이터셋이 서로 다른 질문을 담당한다.

| Experiment | Dataset | 검증 대상 |
|---|---|---|
| E1 | FOLIO | Semantic Tableau logical core |
| E2 | LogicNLI | single proof vs dual proof / paradox |
| E3 | Controlled multi-context | merged vs perspective-indexed contradiction scope |
| E4 | Controlled multi-MUS | single explanation vs Rashomon proof set |
| Application | CONAN | 실제 multi-perspective narrative 적용 가능성 |

이 분리가 논문의 핵심이다.

## 5.1 E1 — FOLIO

공식 `FOLIO v0.0 validation` 204개를 사용하였다.

현재 구현은 full FOL solver가 아니므로 다음 strict fragment만 평가한다.

지원:

- ground fact
- conjunction
- universal Horn implication
- explicit negation
- single ground-literal query

미지원:

- existential quantifier
- disjunction branching
- XOR
- biconditional
- nested quantified formula

Strict supported subset은 **28/204 = 13.73%**이다.

비교:

1. Direct Fact
2. Forward Horn
3. Semantic Clause Tableau
4. Rashomon-Tableau logical core

단일 context에서는 3과 4의 class prediction은 동일해야 한다.

## 5.2 E2 — LogicNLI

공식 `LogicNLI_sim/test_logic.json`을 사용하였다.

- Context: 100
- Statement: 2,000
- Entailment: 500
- Contradiction: 500
- Neutral: 500
- Self-Contradiction/Paradox: 500

LogicNLI의 structured logic representation을 직접 읽어 rule closure를 생성한다.

비교:

1. **Direct Fact + dual check**
2. **Single-Path Forward Reasoner** — `s`가 유도되면 즉시 Entailment로 종료
3. **Dual-Proof Reasoner** — `s`와 `¬s`를 모두 검사하여 둘 다 참이면 Paradox

세 번째 방식이 Rashomon-Tableau의 “여러 상충 proof를 동시에 버리지 않는다”는 핵심과 직접 연결된다.

## 5.3 E3 — Contradiction Scope

80개 controlled case:

```text
Consistent             20
Divergence             20
Intra-Contradiction    20
Inter-Contradiction    20
```

비교:

```text
Merged Tableau
vs
Perspective-Indexed Tableau
```

## 5.4 E4 — Multiple MUS

20개 UNSAT case에 각각 두 개의 독립적인 MUS를 구성한다.

```text
20 cases × 2 MUS = 40 gold explanations
```

비교:

```text
Single Proof
vs
Rashomon Proof Set
```

## 5.5 CONAN의 위치

CONAN은 제안 방법의 정체성이 아니다.

```text
CONAN = multi-perspective application dataset
```

각 인물별로 knowledge scope가 다르기 때문에 Perspective Index를 자연어 서사에 적용하기 좋은 사례다.

본 연구의 일반적인 적용 범위는 더 넓다.

```text
법률 진술
뉴스 출처 비교
로그/모니터링 source conflict
멀티에이전트 가설
과학 문헌의 conflicting evidence
버전/시점별 정책 충돌
Knowledge Graph merge conflict
```

---

# 6. 실험 결과

## 6.1 E1 — FOLIO: Logical Core

GitHub Actions에서 Yale-LILY/FOLIO 공식 validation을 직접 다운로드해 실행하였다.

### Table 1. FOLIO strict supported fragment — 직접 재현 결과

| Method | Accuracy | Macro-F1 | Accuracy Δ vs Forward | Macro-F1 Δ vs Forward |
|---|---:|---:|---:|---:|
| Direct Fact | 42.86% | 26.71% | -32.14 pp | -47.47 pp |
| Forward Horn | 75.00% | 74.18% | - | - |
| **Semantic Clause Tableau** | **96.43%** | **96.33%** | **+21.43 pp** | **+22.15 pp** |
| **Rashomon-Tableau logical core** | **96.43%** | **96.33%** | **+21.43 pp** | **+22.15 pp** |

Class F1:

| Class | Tableau F1 |
|---|---:|
| True | 100.00% |
| False | 93.33% |
| Unknown | 95.65% |

### 해석

Semantic satisfiability를 사용하는 logical core가 같은 supported fragment에서 단순 forward rule firing보다 높은 성능을 보였다.

```text
Accuracy
75.00 → 96.43
+21.43 pp

Macro-F1
74.18 → 96.33
+22.15 pp
```

하지만 Perspective와 Rashomon은 단일-context FOLIO의 class label을 바꾸지 않는다.

```text
Tableau = 96.43
Rashomon-Tableau = 96.43
```

즉 Rashomon layer가 붙었다고 모든 데이터셋에서 Accuracy가 증가하는 것은 아니다.

### Full FOLIO 한계

지원하지 않는 176개를 `Unknown` abstention으로 처리한 보수적 full-validation 결과:

```text
Accuracy = 41.67%
Macro-F1 = 31.97%
```

따라서 96.43%를 full-FOLIO 성능이라고 주장하지 않는다.

## 6.2 E2 — LogicNLI: Multiple Contradictory Proof

공식 structured `test_logic` 2,000 statement를 실제 실행하였다.

### Table 2. LogicNLI official structured test — 직접 재현 결과

| Method | Accuracy | Macro-F1 | Paradox F1 |
|---|---:|---:|---:|
| Direct Fact + dual check | 50.55% | 42.88% | 0.40% |
| Single-Path Forward | 74.00% | 65.78% | **0.00%** |
| **Dual-Proof / Rashomon-style** | **98.40%** | **98.40%** | **97.92%** |

Dual-proof의 개선폭:

```text
Accuracy
74.00 → 98.40
= +24.40 pp

Macro-F1
65.78 → 98.40
= +32.63 pp

Paradox F1
0.00 → 97.92
= +97.92 pp
```

### 왜 이런 차이가 생기는가

LogicNLI의 Paradox는:

```text
KB ⊢ s
AND
KB ⊢ NOT s
```

이다.

Single-path 방식은:

```text
if KB proves s:
    return Entailment
```

처럼 첫 proof에서 멈추므로 500개 Paradox의 존재 자체를 표현할 수 없다.

Dual-proof는:

```text
positive = KB proves s
negative = KB proves NOT s

if positive and negative:
    Paradox
```

로 판정한다.

따라서 이 결과는 단순한 “더 많은 rule을 썼다”는 효과보다 **상충하는 proof를 하나로 덮어쓰지 않고 동시에 보존하는 것의 효과**를 보여준다.

### LogicNLI 원 논문과의 참고 비교

LogicNLI 논문은 자연어 입력을 사용한 Test-A에서 다음 Accuracy를 보고했다.

| Model | Published Test-A Accuracy |
|---|---:|
| BERT | 55.9% |
| XLNet | 65.4% |
| RoBERTa | 68.3% |
| Human | 77.5% |

본 연구의 98.4%는 **structured `test_logic`을 직접 사용하는 symbolic evaluation**이므로 이 표와 같은 조건의 SOTA 경쟁 수치가 아니다. 오히려 차이가 보여주는 것은:

```text
Natural-language formalization 문제
          +
Logical inference 문제
```

를 분리해서 평가해야 한다는 점이다.

즉 end-to-end 모델의 성능은 대략 다음 두 요소의 영향을 받는다.

```text
NL → Logic 품질
      ×
Reasoner 품질
```

본 논문의 핵심 실험은 두 번째를 분석한다.

## 6.3 E3 — Perspective Index: 기존 Tableau 대비

### Table 3. 4-way contradiction scope — 직접 실행 결과

| Method | Accuracy | Macro-F1 | Intra F1 | Inter F1 |
|---|---:|---:|---:|---:|
| Merged-ABox Tableau | 75.00% | 66.67% | **0.00%** | 66.67% |
| **Perspective-Indexed Tableau** | **100.00%** | **100.00%** | **100.00%** | **100.00%** |
| Rashomon-Tableau | **100.00%** | **100.00%** | **100.00%** | **100.00%** |

향상:

```text
Accuracy +25.00 pp
Macro-F1 +33.33 pp
```

### 해석

이것이 “기존 Tableau 대비 성능 향상”이라고 가장 직접적으로 말할 수 있는 부분이다.

그러나 정확한 표현은:

```text
Tableau SAT solver 자체가 25pp 좋아졌다 X

Perspective indexing으로
contradiction scope classification이
25pp 좋아졌다 O
```

이다.

Merged 방식은 모든 UNSAT union을 하나의 `Inter`로 보게 되므로 Intra F1이 0이다. Perspective 방식은 개별 context의 SAT를 먼저 확인하여 이 정보를 복원한다.

## 6.4 E4 — Rashomon Explanation Set

### Table 4. Multiple-MUS explanation coverage — 직접 실행 결과

| Method | Gold MUS | Returned valid MUS | Explanation Coverage |
|---|---:|---:|---:|
| Single-Proof | 40 | 20 | 50.00% |
| **Rashomon Proof Set** | 40 | 40 | **100.00%** |

향상:

```text
Explanation Coverage
50.00 → 100.00
= +50.00 pp
```

이 결과 역시 Classification Accuracy와 섞어 해석하면 안 된다.

```text
Perspective Index
→ classification/scope 개선

Rashomon Set
→ explanation coverage 개선
```

---

# 7. 기존 모델 및 선행연구와의 위치

## 7.1 FOLIO 계열 공개 결과

아래는 선행연구가 full benchmark에서 보고한 결과이며 본 연구의 28-example FOLIO fragment와 **직접 동일 조건 비교가 아니다.** 연구 방향의 위치를 보여주는 참고치로만 사용한다.

| Method | Reported FOLIO Accuracy |
|---|---:|
| GPT-4 Standard | 69.11% |
| GPT-4 CoT | 70.58% |
| LINC | 72.50% |
| Logic-LM | 78.92% |
| SymbCoT | 83.33% |
| LTRAG (GPT-4o) | 80.77% |

이 계열 연구가 보여주는 공통 경향은 **pure language reasoning보다 symbolic structure/solver를 결합했을 때 논리 task에서 성능이 개선될 수 있다**는 것이다.

Rashomon-Tableau는 여기에 다른 질문을 추가한다.

```text
기존 neuro-symbolic:
"논리 문제를 더 정확히 풀 수 있는가?"

본 연구:
"논리 문제를 풀면서
 source/context와 alternative proofs도
 잃지 않을 수 있는가?"
```

## 7.2 전체 실험을 하나의 표로 요약

### Table 5. 제안 구조의 구성요소별 실제 개선

| 구성요소 | Dataset | Baseline | Before | After | Improvement |
|---|---|---|---:|---:|---:|
| Semantic Tableau | FOLIO fragment | Forward Accuracy | 75.00% | 96.43% | **+21.43 pp** |
| Semantic Tableau | FOLIO fragment | Forward Macro-F1 | 74.18% | 96.33% | **+22.15 pp** |
| Dual-Proof preservation | LogicNLI | Single-path Accuracy | 74.00% | 98.40% | **+24.40 pp** |
| Dual-Proof preservation | LogicNLI | Single-path Macro-F1 | 65.78% | 98.40% | **+32.63 pp** |
| Dual-Proof preservation | LogicNLI | Paradox F1 | 0.00% | 97.92% | **+97.92 pp** |
| Perspective Index | Scope benchmark | Merged Tableau Accuracy | 75.00% | 100.00% | **+25.00 pp** |
| Perspective Index | Scope benchmark | Merged Tableau Macro-F1 | 66.67% | 100.00% | **+33.33 pp** |
| Rashomon Set | Multi-MUS benchmark | Single-proof Coverage | 50.00% | 100.00% | **+50.00 pp** |

이 표가 본 논문의 주장을 가장 정확히 압축한다.

```text
Semantic Tableau
→ 논리적 추론 품질

Dual-Proof
→ 상충하는 두 proof의 동시 보존

Perspective Index
→ 모순 위치 식별

Rashomon Set
→ 대안 proof의 설명 coverage
```

---

# 8. 논의

## 8.1 무엇을 새로 제안하는가

본 연구가 새롭다고 주장하지 않는 것:

- SAT/UNSAT
- Tableau calculus
- MUS
- Rashomon Effect
- LLM + symbolic solver

본 연구가 제안하는 것:

```text
Perspective-indexed SAT protocol
+
4-way contradiction scope semantics
+
Dual-proof preservation
+
MUS-based Rashomon proof set
```

즉 새로운 단일 알고리즘이라기보다 **provenance-aware logical reasoning architecture**이다.

## 8.2 왜 LogicNLI 결과가 중요한가

CONAN만 사용하면 reviewer가 “탐정 서사에 맞춘 규칙 아니냐”고 질문할 수 있다.

LogicNLI는 탐정 서사와 무관한 synthetic FOL diagnostic benchmark인데도 `Paradox = s와 ¬s가 모두 증명됨`이라는 구조가 존재한다. 실제 2,000개 test에서 dual-proof 방식이 single-path보다 큰 폭으로 향상된 것은 **multiple proof를 동시에 확인하는 설계가 특정 서사 데이터에만 의존하지 않음**을 보여준다.

## 8.3 왜 FOLIO 결과가 중요한가

FOLIO는 human-authored natural-language/FOL benchmark다. 현재 coverage가 13.73%로 작다는 한계는 있지만 supported fragment에서는 semantic satisfiability reasoning이 단순 forward baseline보다 +21.43 pp 높았다.

따라서 현재 결과는 다음 두 사실을 동시에 보여준다.

```text
Logical core는 효과가 있다.
BUT
Full-FOL coverage는 아직 부족하다.
```

이처럼 coverage를 Accuracy와 함께 보고하는 것이 중요하다.

## 8.4 Rashomon을 쓰는 이유

기존 explanation 시스템은 흔히 가장 높은 score의 explanation 하나를 반환한다.

```text
argmax Score(π)
```

그러나 실제 모순에 두 개의 독립적인 근거가 존재한다면 하나만 보여주는 것은 정보 손실이다.

Rashomon 관점에서는 질문을 바꾼다.

```text
"Best explanation은 무엇인가?"
             ↓
"Best와 거의 동등하게 타당한 explanation은
 몇 개이며 서로 무엇이 다른가?"
```

이 변화는 특히 RCA, 법률 증거, scientific evidence, multi-agent reasoning처럼 **여러 원인이나 가설을 동시에 검토해야 하는 분야**에서 유용하다.

## 8.5 Tableau와 Rashomon의 결합 가능성

두 개념은 원래 서로 다른 문제를 해결한다.

```text
Tableau
→ validity / satisfiability

Rashomon
→ multiplicity among similarly good alternatives
```

본 연구에서 이 둘은 다음처럼 결합된다.

```text
Tableau가 proof validity를 보장
         ↓
MUS가 proof를 최소화
         ↓
Rashomon이 여러 valid proof를 유지
```

즉 Rashomon이 논리 validity를 대신하는 것이 아니다. **Tableau가 validity filter이고 Rashomon이 alternative-preservation layer**이다.

## 8.6 적용 가능성

### Multi-source News

```text
Source A KB
Source B KB
Source C KB
→ 어떤 source pair가 충돌하는가?
```

### Legal Testimony

```text
Witness A 내부 모순
vs
Witness A ↔ Witness B 충돌
```

### Observability / RCA

```text
APM says DB normal
DB monitor says DB abnormal
→ inter-source contradiction

APM itself says normal + abnormal
→ intra-source inconsistency
```

### Multi-Agent AI

```text
Agent A hypothesis
Agent B hypothesis
Agent C hypothesis
→ individually SAT?
→ jointly SAT?
→ alternative contradiction proofs?
```

### Knowledge Graph Merge

여러 graph/source의 provenance를 유지한 상태에서 merge conflict를 탐색할 수 있다.

---

# 9. 한계 및 향후 연구

## 9.1 Full FOL Coverage

현재 FOLIO strict coverage는:

```text
28 / 204 = 13.73%
```

이다.

Full FOL 지원을 위해:

- existential branching
- disjunction
- biconditional
- nested quantifier
- equality
- richer role semantics

가 필요하다.

향후 Prover9, Z3, OWLReady2, HermiT 등의 backend adapter와 비교해야 한다.

## 9.2 LogicNLI Structured Input

98.4%는 `test_language`가 아니라 공식 structured `test_logic`을 사용한다.

따라서:

```text
98.4% = logical reasoning layer 성능
≠ end-to-end natural-language 성능
```

이다.

향후 `test_language → LLM formalizer → Rashomon-Tableau`의 end-to-end 실험이 필요하다.

## 9.3 Controlled Scope Benchmark

Perspective Index의 +25 pp는 구조적 capability를 검증하기 위해 설계한 controlled benchmark 결과다.

자연 발생 multi-source corpus에서도 동일한 향상폭이 유지되는지는 human annotation을 통해 검증해야 한다.

## 9.4 Controlled Explanation Benchmark

Rashomon coverage +50 pp는 두 개의 MUS가 존재하도록 설계한 benchmark 결과다.

향후 P-FOLIO human reasoning chains 또는 실제 multi-evidence dataset에서:

- proof precision
- proof recall
- pass@k
- human preference
- explanation faithfulness

를 측정해야 한다.

## 9.5 비용

Perspective가 `m`개일 때 모든 pair를 검사하면 조합 수가 증가한다.

```text
O(m²)
```

규모가 큰 경우 graph retrieval 또는 conflict candidate filtering을 Tableau 앞단에 두는 hybrid 구조가 필요하다.

---

# 10. 결론

본 연구는 Tableau가 기존에 잘 수행해온 `SAT/UNSAT` reasoning을 버리지 않고, 실제 multi-source 환경에서 필요한 두 가지 정보인 **모순의 위치**와 **설명의 다양성**을 추가로 보존하는 Rashomon-Tableau를 제안하였다.

제안 구조는 다음 네 단계로 정리된다.

```text
Semantic Tableau
       ↓
Dual-Proof Check
       ↓
Perspective-Indexed SAT
       ↓
MUS + Rashomon Proof Set
```

직접 재현한 결과는 다음과 같다.

```text
FOLIO supported fragment
Forward → Tableau
Accuracy +21.43 pp
Macro-F1 +22.15 pp

LogicNLI 2,000 statements
Single-path → Dual-proof
Accuracy +24.40 pp
Macro-F1 +32.63 pp
Paradox F1 +97.92 pp

Merged → Perspective Tableau
Scope Accuracy +25.00 pp
Macro-F1 +33.33 pp

Single Proof → Rashomon Set
Explanation Coverage +50.00 pp
```

따라서 본 연구의 결론은 “Rashomon을 붙이면 모든 데이터에서 Accuracy가 오른다”가 아니다.

> **Tableau는 올바른 논리 판정을 담당하고, dual-proof reasoning은 상충하는 추론을 동시에 보존하며, Perspective Index는 모순이 어디에서 발생했는지를 식별하고, Rashomon Set은 동일 결론을 설명하는 여러 타당한 proof를 보존한다.**

이러한 구조는 CONAN과 같은 다중 관점 서사를 넘어, provenance와 competing explanation이 중요한 다양한 reasoning system에 적용될 가능성을 가진다.

---

# References

1. Baader, F., & Sattler, U. (2000). **Tableau Algorithms for Description Logics.** TABLEAUX 2000. https://doi.org/10.1007/10722086_1
2. Baader, F., & Sattler, U. (2001). **An Overview of Tableau Algorithms for Description Logics.** Studia Logica, 69, 5–40.
3. Motik, B., Shearer, R., & Horrocks, I. (2009). **Hypertableau Reasoning for Description Logics.** JAIR.
4. Breiman, L. (2001). **Statistical Modeling: The Two Cultures.** Statistical Science, 16(3), 199–231.
5. Fisher, A., Rudin, C., & Dominici, F. (2019). **All Models are Wrong, but Many are Useful: Learning a Variable's Importance by Studying an Entire Class of Prediction Models Simultaneously.** JMLR, 20(177), 1–81. https://jmlr.org/papers/v20/18-760.html
6. Xin, R., Zhong, C., Chen, Z., Takagi, T., Seltzer, M., & Rudin, C. (2022). **Exploring the Whole Rashomon Set of Sparse Decision Trees.** NeurIPS 2022.
7. Rudin, C., et al. (2024). **Position: Amazing Things Come From Having Many Good Models.** ICML 2024.
8. Tian, J., Li, Y., Chen, W., Xiao, L., He, H., & Jin, Y. (2021). **Diagnosing the First-Order Logical Reasoning Ability Through LogicNLI.** EMNLP 2021. https://aclanthology.org/2021.emnlp-main.303/
9. Han, S., et al. (2022). **FOLIO: Natural Language Reasoning with First-Order Logic.** arXiv:2209.00840.
10. Pan, L., Albalak, A., Wang, X., & Wang, W. (2023). **Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning.** Findings of EMNLP 2023. https://aclanthology.org/2023.findings-emnlp.248/
11. Olausson, T., et al. (2023). **LINC: A Neurosymbolic Approach for Logical Reasoning by Combining Language Models with First-Order Logic Provers.** EMNLP 2023. https://aclanthology.org/2023.emnlp-main.313/
12. Tafjord, O., Dalvi, B., & Clark, P. (2021). **ProofWriter: Generating Implications, Proofs, and Abductive Statements over Natural Language.** Findings of ACL-IJCNLP 2021.
13. Xu, F., et al. (2024). **Faithful Logical Reasoning via Symbolic Chain-of-Thought.** ACL 2024.
14. Han, S., et al. (2024). **P-FOLIO: Evaluating and Improving Logical Reasoning with Abundant Human-Written Reasoning Chains.** arXiv:2410.09207.
15. Zhao, W., et al. (2024). **Large Language Models Fall Short: Understanding Complex Relationships in Detective Narratives.** Findings of ACL 2024.
16. Hu, R., Lin, S., Xiu, Y., & Liu, Y. (2025). **LTRAG: Enhancing Autoformalization and Self-refinement for Logical Reasoning with Thought-Guided RAG.** Findings of ACL 2025.

---

# Reproducibility

직접 실행 결과:

- [`results/folio_fragment_metrics.json`](./results/folio_fragment_metrics.json)
- [`results/logicnli_metrics.json`](./results/logicnli_metrics.json)
- [`results/ablation_metrics.json`](./results/ablation_metrics.json)

실행:

```bash
python scripts/evaluate_folio_fragment.py
python scripts/evaluate_logicnli.py
python scripts/run_ablation.py
pytest -q
```

GitHub Actions:

```text
.github/workflows/external-benchmarks.yml
```

외부 데이터셋은 실행 시 공식 repository에서 직접 다운로드하며 저장소에 재배포하지 않는다.
