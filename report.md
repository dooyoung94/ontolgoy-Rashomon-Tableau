# Rashomon-Tableau: Perspective-Indexed Tableau Reasoning for Contradiction Scope Localization and Multi-Proof Explanation

## 라쇼몽-태블로: 모순 범위 식별과 복수 증명 설명을 위한 관점 인덱스 기반 Tableau 추론

---

## 초록

논리 기반 모순 탐지는 일반적으로 여러 사실과 규칙을 하나의 지식베이스에 결합한 뒤 전체 지식베이스의 만족가능성(satisfiability)을 검사한다. 이 방식은 지식베이스가 모순인지 여부를 판정하는 데 효과적이지만, 서로 다른 출처·화자·문서·시점·에이전트가 제공한 사실을 하나로 합칠 경우 **모순이 특정 관점 내부에서 이미 존재했는지, 아니면 서로 독립적으로 일관적인 두 관점을 결합했을 때 새롭게 발생했는지**를 구분하기 어렵다. 또한 전통적인 추론 시스템은 모순을 입증하는 하나의 증명 또는 하나의 최소 충돌 집합만 제시하는 경우가 많아, 동일한 결론을 뒷받침하는 복수의 독립적 설명이 존재할 때 설명의 다양성을 잃을 수 있다.

본 연구는 이 두 문제를 해결하기 위해 **Rashomon-Tableau**를 제안한다. 제안 방법의 핵심은 새로운 Tableau calculus 자체가 아니라, 기존의 만족가능성 검사를 **관점별 지식베이스에 인덱싱하여 수행하는 Perspective-Indexed Tableau**와, 하나의 최적 증명만 선택하지 않고 복수의 최소 모순 증명을 유지하는 **Rashomon Explanation Set**을 결합하는 것이다. 관점 `P_i`의 사실 집합을 `A_i`, 공통 온톨로지 또는 규칙 집합을 `T`라고 할 때, 제안법은 `SAT(T∪A_i)`, `SAT(T∪A_j)`, `SAT(T∪A_i∪A_j)`를 별도로 계산한다. 이를 통해 단순한 정보 차이(Divergence), 관점 내부 모순(Intra-Contradiction), 관점 간 결합에서만 발생하는 모순(Inter-Contradiction)을 분리한다. 모순이 검출되면 Minimal Unsatisfiable Subset(MUS)을 열거하고, 설명 품질이 최선의 설명에서 허용 오차 `ε` 이내인 복수의 증명을 Rashomon set으로 보존한다.

세 개의 분리된 실험을 통해 각 구성요소의 효과를 검증하였다. 첫째, 공식 **FOLIO v0.0 validation** 204개 예제 중 현재 구현이 완전하게 처리하도록 제한한 universal-Horn/explicit-negation fragment 28개에서 Semantic Clause Tableau는 Accuracy **96.43%**, Macro-F1 **96.33%**를 기록하였다. 이는 동일 subset의 Forward-Horn baseline(Accuracy 75.00%, Macro-F1 74.18%)보다 각각 **+21.43 percentage points(pp)**, **+22.15 pp** 높았다. 둘째, 80개의 multi-context controlled scope benchmark에서 기존 merged-ABox Tableau는 Accuracy 75.00%, Macro-F1 66.67%였으며 Intra-Contradiction F1은 0이었다. Perspective-Indexed Tableau는 Accuracy와 Macro-F1 모두 100%를 기록하여 각각 **+25.00 pp**, **+33.33 pp** 향상되었다. 셋째, 각 사례에 두 개의 독립적인 최소 모순 설명이 존재하도록 구성한 20개 사례에서 single-proof 방식의 explanation coverage는 50%였으나 Rashomon explanation set은 100%를 보존하여 **+50.00 pp** 향상되었다.

이 결과는 Rashomon-Tableau가 모든 논리 데이터셋에서 분류 정확도를 일률적으로 높인다는 것을 의미하지 않는다. 단일 관점 데이터에서는 Perspective Index와 Rashomon layer가 class prediction을 변화시키지 않으며, 그 경우 성능은 underlying Tableau reasoner에 의해 결정된다. 본 연구의 기여는 **(1) Tableau 기반 논리 추론 능력을 유지하면서, (2) multi-context 환경에서 모순의 발생 범위를 식별하고, (3) 동일 결론을 설명하는 복수의 논리 증명을 손실 없이 노출하는 것**에 있다. CONAN 탐정 서사는 이러한 multi-perspective 특성을 보여주기 위한 응용 데이터셋으로 사용되며, 제안법 자체는 뉴스 출처, 법률 진술, 시스템 로그, 시점별 스냅샷, 멀티에이전트 추론 등 다양한 context-aware reasoning 문제에 적용 가능하다.

**주요어:** Tableau Algorithm, Rashomon Effect, Satisfiability, Contradiction Localization, Multi-Perspective Reasoning, Minimal Unsatisfiable Subset, Explainable AI, Neuro-Symbolic Reasoning

---

# 1. 서론

## 1.1 연구 문제

논리 추론에서 가장 기본적인 질문 중 하나는 다음과 같다.

> **주어진 모든 명제가 동시에 참일 수 있는가?**

Tableau 계열 알고리즘은 이 질문을 만족가능성 문제로 변환한다. 명제와 규칙을 확장하면서 가능한 논리 세계를 구성하고, 모든 branch가 `φ`와 `¬φ`를 동시에 포함하는 clash로 닫히면 해당 지식베이스를 unsatisfiable로 판정한다. Description Logic 분야에서는 이러한 tableau-like algorithm이 satisfiability와 subsumption을 결정하는 핵심 기법으로 오랫동안 사용되어 왔다.

그러나 실제 데이터는 하나의 동일한 관찰자가 작성한 단일 지식베이스만으로 구성되지 않는다. 예를 들어 다음과 같은 상황을 생각할 수 있다.

- 서로 다른 목격자의 진술
- 서로 다른 언론사의 동일 사건 보도
- 개발팀과 운영팀의 장애 원인 가설
- 시간 `t1`, `t2`에서 관찰된 시스템 상태
- 여러 AI Agent가 생성한 독립 가설
- 서로 다른 문서 버전이나 데이터베이스 snapshot

이러한 사실을 출처 구분 없이 하나의 ABox로 합치면 Tableau는 전체 집합이 `UNSAT`이라는 사실은 알려줄 수 있지만, **모순이 어디에서 발생했는지**에 대한 정보는 사라질 수 있다.

예를 들어 관점 `A`가 이미 내부적으로 모순이고 관점 `B`는 정상인 경우와, `A`와 `B`가 각각 독립적으로는 완전히 일관적이지만 두 관점을 합쳤을 때만 충돌하는 경우는 의미가 다르다.

```text
Case 1 — Intra contradiction
A: P(a), NOT P(a)
B: Q(b)

Case 2 — Inter contradiction
A: P(a)
B: NOT P(a)
```

기존 merged-KB Tableau는 두 경우 모두 다음과 같이 처리한다.

```text
Tableau(T ∪ A ∪ B) = UNSAT
```

따라서 **contradiction detection**은 가능하지만 **contradiction scope localization**은 불가능하다.

본 연구가 해결하려는 문제는 바로 이 지점이다.

## 1.2 핵심 주장

본 연구의 주장은 하나로 요약된다.

> **Tableau의 satisfiability 검사를 관점별로 인덱싱하면 기존의 논리적 엄밀성을 유지하면서 모순의 발생 범위를 식별할 수 있고, 그 결과 생성되는 복수의 최소 모순 증명을 Rashomon set으로 유지하면 단일 proof 선택으로 인한 설명 손실을 줄일 수 있다.**

즉 제안법은 세 층으로 구성된다.

```text
Layer 1. Semantic Tableau
         논리적 참/거짓/불확실성 판정

Layer 2. Perspective Index
         모순의 위치: Intra / Inter / Divergence 식별

Layer 3. Rashomon Explanation
         하나가 아닌 복수의 최소·근사최적 증명 보존
```

이 세 층은 서로 다른 목적을 가진다. 따라서 논문에서도 하나의 Accuracy 숫자로 모든 기여를 주장하지 않는다.

## 1.3 연구 질문

본 연구는 다음 세 개의 핵심 연구 질문을 설정한다.

**RQ1. Logical Core**  
Semantic Tableau는 단순 사실 대조 또는 forward-only rule chaining에 비해 외부 논리 추론 데이터셋에서 어떤 이점을 가지는가?

**RQ2. Contradiction Scope**  
Perspective별 satisfiability를 별도로 검사하면 merged-ABox Tableau가 구분하지 못하는 Intra/Inter contradiction을 식별할 수 있는가?

**RQ3. Explanation Multiplicity**  
하나의 증명만 반환하는 방법과 비교할 때 Rashomon explanation set은 동등하게 타당한 복수의 최소 모순 설명을 얼마나 더 보존하는가?

CONAN 기반 실험은 별도의 핵심 RQ가 아니라 **multi-perspective application case**로 둔다.

## 1.4 연구 기여

본 연구의 기여는 다음 세 가지이다.

1. **Perspective-Indexed Tableau**  
   기존 Tableau calculus를 대체하지 않고 `SAT(T∪A_i)`와 `SAT(T∪A_i∪A_j)`를 분리하여 contradiction scope를 식별한다.

2. **Divergence와 Contradiction의 분리**  
   두 관점이 서로 다른 사실을 말하더라도 합집합이 satisfiable이면 모순이 아니라 정보 차이로 분류한다.

3. **Proof-level Rashomon Set**  
   전통적인 Rashomon set의 “거의 동등하게 좋은 여러 모델”이라는 아이디어를 **거의 동등하게 타당한 여러 논리 설명**으로 확장하여 여러 MUS/증명 경로를 보존한다.

---

# 2. 이론적 배경 및 관련 연구

## 2.1 기존 연구에서 Tableau는 어떻게 사용되는가

Tableau는 본래 분류 모델이 아니라 **논리식의 만족가능성을 결정하기 위한 증명 절차**이다. Description Logic 연구에서는 satisfiability, concept consistency, subsumption과 같은 reasoning service를 tableau-like algorithm으로 해결해 왔다. Baader와 Sattler는 Description Logic의 주요 추론 문제가 tableau-like algorithm으로 결정될 수 있음을 체계적으로 정리하였다.

기본 개념은 다음과 같다.

```text
Knowledge Base
    ↓
Expansion Rules
    ↓
Possible Branches
    ↓
φ and NOT φ ?
    ↓
Clash → branch closed
```

모든 branch가 닫히면:

```text
UNSAT
```

하나 이상의 open branch가 존재하면:

```text
SAT
```

Description Logic이 복잡해지면서 단순 Tableau는 blocking, number restriction, role constructor 등을 처리하도록 확장되었다. HermiT과 같은 현대 OWL reasoner는 classical Tableau의 직접 구현이라기보다 **hypertableau calculus**를 사용한다. 즉 Tableau 계열 연구의 핵심 발전 방향은 주로 **더 표현력 있는 논리를 sound/complete하게, 그리고 더 효율적으로 결정하는 것**이었다.

본 연구의 차이는 calculus의 표현력을 확장하는 데 있지 않다. 본 연구는 **동일한 satisfiability oracle을 여러 context에 어떻게 적용할 것인가**에 초점을 둔다.

```text
기존:
SAT(T ∪ A ∪ B)

제안:
SAT(T ∪ A)
SAT(T ∪ B)
SAT(T ∪ A ∪ B)
```

따라서 기존 Tableau와 경쟁하는 새로운 theorem prover라기보다 **Tableau를 multi-context reasoning에 배치하는 새로운 reasoning protocol**에 가깝다.

## 2.2 Neuro-Symbolic Logical Reasoning

최근 LLM 논리 추론 연구는 자연어 문제를 LLM이 직접 풀게 하는 방식과, 자연어를 논리식으로 변환한 뒤 외부 symbolic solver에 추론을 위임하는 방식을 비교한다.

Logic-LM은 자연어를 symbolic formulation으로 변환하고 symbolic solver가 실제 추론을 수행하도록 구성하였다. 보고된 GPT-4 결과에서 FOLIO Accuracy는 Standard prompting 69.11%, CoT 70.58%, Logic-LM 78.92%였다. 이는 symbolic solver를 이용한 구조적 추론이 단순 언어모델 추론보다 유리할 수 있음을 보여준다.

LINC 역시 LLM을 자연어와 FOL 사이의 translator로 사용하고 theorem prover가 deductive inference를 수행하도록 한다. LINC 논문은 ProofWriter에서 GPT-4 + LINC가 CoT보다 큰 폭으로 향상되었으며, FOLIO에서는 두 방식의 실패 유형이 상호 보완적이라는 점을 보고한다. 이는 **논리 solver 자체뿐 아니라 자연어를 올바르게 formalize하는 과정이 전체 성능의 병목**임을 보여준다.

본 연구도 이러한 neuro-symbolic 관점을 따른다. 다만 중심 질문은 “LLM을 symbolic solver와 연결하면 정확도가 오르는가?”가 아니라, **solver에 들어가는 명제를 관점별로 분리했을 때 추가적으로 어떤 정보를 보존할 수 있는가?**이다.

## 2.3 Rashomon Effect는 기존 연구에서 어떻게 사용되는가

Rashomon Effect는 Breiman이 통계적 모델링에서 강조한 개념으로, 하나의 데이터셋에 대해 거의 동일한 예측 성능을 갖는 서로 다른 모델이 다수 존재할 수 있다는 현상을 의미한다.

Fisher, Rudin, Dominici는 한 개의 잘 맞는 모델만 해석할 경우 다른 잘 맞는 모델에서 변수 중요도가 달라질 수 있다는 문제를 지적하고, **전체 well-performing model class를 함께 분석하는 Model Class Reliance**를 제안하였다. 이후 sparse decision tree 연구에서는 거의 최적인 모든 tree의 Rashomon set 자체를 열거하여 하나의 모델이 아니라 여러 동등하게 좋은 모델을 분석하였다.

전통적인 Rashomon set을 다음과 같이 표현할 수 있다.

```text
R_epsilon = { f : Loss(f) <= Loss(f*) + epsilon }
```

여기서 중요한 것은 **하나의 best model만이 정답이라고 가정하지 않는 것**이다.

본 연구는 이 아이디어를 모델 공간이 아니라 **증명 공간(proof space)**으로 옮긴다. 이것은 기존 Rashomon 정의를 그대로 사용하는 것이 아니라 본 연구의 방법론적 확장이다.

```text
Model Rashomon Set
여러 개의 거의 동등하게 좋은 predictive model

                    ↓ conceptual transfer

Proof Rashomon Set
여러 개의 거의 동등하게 타당하고 간결한 contradiction proof
```

모순 `c`를 설명하는 증명 후보 집합을 `Π(c)`라고 할 때:

```text
R^proof_epsilon(c)
=
{ π ∈ Π(c) : Score(π) >= Score(π*) - epsilon }
```

으로 정의한다.

이 구조는 “원인은 하나다”라고 강제하지 않는다. 예를 들어 동일한 UNSAT 결과가 두 개의 독립적인 clash로 설명될 수 있다면 둘 다 사용자에게 보여준다.

## 2.4 여러 reasoning chain과의 관계

최근 P-FOLIO는 인간이 작성한 reasoning chain을 제공하고, 하나의 생성 reasoning chain이 인간의 chain과 다른 경로를 취할 수 있기 때문에 여러 chain을 sampling하여 `pass@k`를 평가한다. 이는 **동일한 논리 결론에 여러 reasoning path가 존재할 수 있다**는 점을 실험적으로 다룬다는 점에서 본 연구와 밀접하다.

차이는 P-FOLIO가 주로 생성 reasoning chain의 품질을 평가하는 반면, 본 연구는 symbolic solver가 검증한 **MUS/contradiction proof set 자체를 명시적으로 열거**한다는 것이다.

## 2.5 선행연구의 공백

관련 연구를 정리하면 다음과 같다.

| 연구 축 | 잘하는 것 | 본 연구가 보는 공백 |
|---|---|---|
| Classical / DL Tableau | SAT/UNSAT의 엄밀한 판정 | 여러 출처의 contradiction scope를 별도 label로 다루지 않음 |
| Logic-LM / LINC | NL → Logic → Solver | source/perspective provenance가 핵심 연구 대상이 아님 |
| NLI | 문장 pair contradiction 분류 | multi-hop ontology implication과 formal clash 설명이 약함 |
| Rashomon ML | 여러 near-optimal model 분석 | 여러 symbolic proof의 집합을 직접 다루지 않음 |
| P-FOLIO | multiple reasoning chains 평가 | context-indexed contradiction localization이 목적이 아님 |

따라서 본 연구의 위치는 다음 교차점이다.

```text
Tableau satisfiability
        +
Context / Perspective provenance
        +
Multiple valid explanations
```

---

# 3. 문제 정의

## 3.1 Perspective-Indexed Knowledge Base

관점 집합을 다음과 같이 정의한다.

```text
P = {P1, P2, ..., Pm}
```

각 관점 `P_i`에서 얻은 명제 집합은:

```text
A_i = {φ_i1, φ_i2, ..., φ_in}
```

공통 규칙 또는 Ontology TBox를 `T`라고 하면:

```text
K_i = T ∪ A_i
```

이다.

여기서 `Perspective`는 반드시 사람이 아니어도 된다.

```text
Perspective / Context
= person
= document
= news source
= timestamp
= database snapshot
= sensor
= log source
= AI agent
= competing hypothesis
```

## 3.2 네 가지 판정

### Consistent

두 관점의 사실이 동일하거나 양립 가능하다.

```text
SAT(T ∪ A_i ∪ A_j) = 1
```

이며 사실 집합이 실질적으로 동일하면 `Consistent`이다.

### Divergence

```text
A_i != A_j
SAT(T ∪ A_i ∪ A_j) = 1
```

이면 두 관점은 다르지만 동시에 참일 수 있다.

### Intra-Perspective Contradiction

```text
SAT(T ∪ A_i) = 0
```

또는

```text
SAT(T ∪ A_j) = 0
```

이면 특정 관점 내부 모순이다.

### Inter-Perspective Contradiction

```text
SAT(T ∪ A_i) = 1
SAT(T ∪ A_j) = 1
SAT(T ∪ A_i ∪ A_j) = 0
```

이면 각 관점은 독립적으로는 일관적이지만 결합했을 때만 모순이다.

이 정의가 본 연구의 가장 중요한 형식적 기여이다.

---

# 4. 제안 방법: Rashomon-Tableau

## 4.1 전체 구조

```text
Natural Language / Structured Facts
            ↓
      Symbolization
            ↓
Perspective-indexed ABoxes
     A1     A2     ... Am
       \     |      /
       Shared TBox T
            ↓
Semantic Tableau
  ├─ SAT(T ∪ A1)
  ├─ SAT(T ∪ A2)
  └─ SAT(T ∪ Ai ∪ Aj)
            ↓
Scope Classification
  Consistent / Divergence
  Intra / Inter Contradiction
            ↓
UNSAT cases only
            ↓
MUS Enumeration
            ↓
Proof Scoring
            ↓
Rashomon Explanation Set
```

## 4.2 Semantic Tableau Logical Core

외부 FOLIO 비교를 위해 기존 relational closure 외에 ground-clause semantic Tableau backend를 추가하였다.

규칙

```text
P(x) AND Q(x) -> R(x)
```

은 ground substitution 후 clause

```text
NOT P(a) OR NOT Q(a) OR R(a)
```

로 변환한다.

Query `R(a)`가 entail되는지를 검사하려면 knowledge base에 `NOT R(a)`를 추가한 뒤 satisfiability를 확인한다.

```text
KB |= R(a)
iff
SAT(KB ∪ {NOT R(a)}) = 0
```

이 방식은 단순 forward chaining과 달리 clause satisfiability를 사용하므로 classical implication에 따른 간접 충돌을 처리할 수 있다.

## 4.3 Perspective-Indexed Decision Rule

```text
s_i   = SAT(T ∪ A_i)
s_j   = SAT(T ∪ A_j)
s_ij  = SAT(T ∪ A_i ∪ A_j)
```

판정은 다음과 같다.

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

기존 merged-ABox 방식은 `s_ij`만 계산하기 때문에 첫 번째와 두 번째 경우를 구분할 수 없다.

## 4.4 Minimal Unsatisfiable Subset

전체 fact set이 UNSAT일 때 모든 사실이 모순의 원인은 아니다. 따라서 최소한의 사실만으로도 UNSAT이 유지되는 부분집합을 구한다.

```text
MUS
=
min_subset { M ⊆ A : SAT(T ∪ M)=0 }
```

MUS는 설명에 사용되는 evidence를 최소화한다.

## 4.5 Rashomon Explanation Set

하나의 UNSAT 집합에 여러 MUS가 존재할 수 있다.

```text
MUS_1 = {a, NOT a}
MUS_2 = {b, NOT b}
```

Single-proof 방식은 둘 중 하나만 반환한다.

```text
Output = MUS_1
```

Rashomon-Tableau는 여러 후보를 평가한다.

현재 PoC에서 explanation score는 간결성과 관점 다양성으로 구성된다.

```text
Score(π)
= 1 / |π|
  + 0.05 × NumberOfPerspectives(π)
```

최고 score와 `ε` 이내인 설명을 보존한다.

```text
R^proof_epsilon(c)
=
{ π : Score(π) >= Score(π*) - ε }
```

따라서 Rashomon layer의 목표는 Accuracy 향상이 아니라 **Explanation Set Recall/Coverage 향상**이다.

---

# 5. 평가 지표

## 5.1 Accuracy

전체 사례 중 정확히 맞힌 비율이다.

```text
Accuracy = Correct / Total
```

직관적이지만 특정 클래스를 전부 틀려도 다른 클래스가 많으면 높은 값이 나올 수 있다.

## 5.2 Precision, Recall, F1

특정 클래스 `c`에 대해:

```text
Precision_c = TP_c / (TP_c + FP_c)
Recall_c    = TP_c / (TP_c + FN_c)
```

F1은 둘의 조화평균이다.

```text
F1_c = 2 × Precision_c × Recall_c
       / (Precision_c + Recall_c)
```

### 이 논문에서 F1이 뜻하는 바

예를 들어 Vanilla merged Tableau가 80개 중 60개를 맞히면 Accuracy는 75%이다. 그러나 `Intra-Contradiction` 20개를 전부 `Inter-Contradiction`으로 잘못 분류하면:

```text
Intra Precision = 0
Intra Recall    = 0
Intra F1        = 0
```

이다.

따라서 단순 Accuracy만 보면 “75%로 괜찮다”고 볼 수 있지만 F1을 보면 **특정 모순 유형을 전혀 식별하지 못한다**는 사실이 드러난다.

## 5.3 Macro-F1

모든 class의 F1을 동일한 비중으로 평균한다.

```text
Macro-F1
= (F1_consistent
 + F1_divergence
 + F1_intra
 + F1_inter) / 4
```

본 연구에서는 class imbalance보다 **각 논리 상태를 제대로 구분하는 능력**이 중요하므로 Macro-F1을 주요 지표로 사용한다.

## 5.4 Explanation Coverage

한 사례에 존재하는 검증 가능한 최소 설명을 `G`라고 하고 시스템이 반환한 설명을 `E`라고 한다.

```text
Explanation Coverage = |E ∩ G| / |G|
```

분류 Accuracy와 분리하여 평가한다.

## 5.5 Logical Grammar Coverage

외부 데이터셋 전체 중 현재 reasoner가 완전하게 지원하도록 선언한 논리 fragment의 비율이다.

```text
Grammar Coverage
= Supported Examples / Total Examples
```

이 값을 보고하는 이유는 지원하지 않는 FOL 문법을 억지로 처리하여 정확도를 부풀리지 않기 위해서이다.

---

# 6. 실험 설계

## 6.1 Experiment 1 — 외부 데이터셋에서 Logical Core 평가

### Dataset

**FOLIO v0.0 validation**을 사용한다.

FOLIO는 자연어 premise와 First-Order Logic annotation을 함께 제공하는 human-authored logical reasoning benchmark이다. 공식 validation은 현재 실험 기준 204개 example을 포함한다.

현재 구현은 full FOL solver가 아니므로 다음 fragment만 지원 대상으로 선언하였다.

- Ground facts
- Ground conjunction
- Universal Horn implication
- Explicit negation
- Single ground-literal query

현재 미지원:

- Existential quantifier
- Disjunction
- XOR
- Biconditional
- 복합 quantified conclusion

따라서 204개 중 **28개(13.73%)**가 strict supported fragment에 포함되었다.

### Compared Methods

1. **Direct Fact Baseline**: query 또는 negated query가 explicit fact로 존재하는지만 검사
2. **Forward Horn Baseline**: 규칙을 정방향으로만 적용
3. **Semantic Clause Tableau**: clause satisfiability로 entailment 검사
4. **Rashomon-Tableau Logical Core**: 단일 context에서는 3과 동일한 class decision

이 실험은 Perspective/Rashomon 효과가 아니라 **Tableau logical core 자체의 효과**를 검증한다.

## 6.2 Experiment 2 — 기존 Tableau 대비 Contradiction Scope 평가

80개 controlled case를 다음 네 클래스에 동일하게 20개씩 구성하였다.

```text
Consistent             20
Divergence             20
Intra-Contradiction    20
Inter-Contradiction    20
```

비교:

```text
Vanilla Merged Tableau
vs
Perspective-Indexed Tableau
vs
Rashomon-Tableau
```

Rashomon layer는 classification 결과를 바꾸지 않으므로 Perspective Tableau와 동일 Accuracy가 예상된다.

## 6.3 Experiment 3 — Rashomon Explanation 평가

20개 controlled UNSAT case를 생성하였다. 각 case에는 독립적인 최소 contradiction이 정확히 두 개 존재한다.

```text
20 cases × 2 independent MUS
= 40 minimal explanations
```

비교:

- Single Proof: 하나의 MUS만 반환
- Rashomon Explanation Set: `ε` 범위 내 모든 MUS 반환

평가지표는 Explanation Coverage이다.

## 6.4 CONAN의 역할

CONAN은 본 연구 방법 자체의 정의가 아니다. CONAN은 서로 다른 인물이 같은 사건·인물관계를 서로 다른 범위로 알고 있다는 구조를 제공하기 때문에 **Perspective-Indexed Reasoning을 적용하기 좋은 application benchmark**이다.

따라서 연구 구조는 다음과 같이 둔다.

```text
Method validation:
FOLIO + controlled logical benchmarks

Multi-perspective application:
CONAN
```

---

# 7. 실험 결과

## 7.1 Experiment 1 — FOLIO External Logical Reasoning

GitHub Actions에서 공식 FOLIO validation 파일을 직접 내려받아 동일 환경에서 재현하였다.

- CI run: `32702509600`
- Total validation examples: `204`
- Strict supported fragment: `28`
- Coverage: `13.73%`
- Supported label distribution: True 9 / False 8 / Unknown 11

### Table 1. FOLIO Supported Fragment — 직접 실행 결과

| Method | Accuracy | Macro-F1 | Δ Accuracy vs Forward | Δ Macro-F1 vs Forward |
|---|---:|---:|---:|---:|
| Direct Fact | 42.86% | 26.71% | -32.14 pp | -47.11 pp |
| Forward Horn | 75.00% | 74.18% | - | - |
| **Semantic Clause Tableau** | **96.43%** | **96.33%** | **+21.43 pp** | **+22.15 pp** |
| **Rashomon-Tableau Logical Core** | **96.43%** | **96.33%** | **+21.43 pp** | **+22.15 pp** |

Class별 Semantic Tableau F1:

| Class | F1 |
|---|---:|
| True | **100.00%** |
| False | **93.33%** |
| Unknown | **95.65%** |

### 해석

가장 중요한 결과는 두 가지이다.

첫째, 단순 forward chaining보다 semantic satisfiability를 사용하는 Tableau가 supported logical fragment에서 명확한 성능 향상을 보였다.

```text
Accuracy: 75.00 → 96.43
          +21.43 pp

Macro-F1: 74.18 → 96.33
          +22.15 pp
```

둘째, FOLIO는 단일 context이므로 Perspective Index와 Rashomon layer를 추가해도 **class prediction은 달라지지 않는다**.

```text
Semantic Tableau = 96.43%
Rashomon-Tableau = 96.43%
```

이것은 실패가 아니라 본 논문의 구조를 확인해주는 결과이다. Rashomon layer가 분류 Accuracy까지 항상 높인다고 주장하면 안 된다.

### Full FOLIO에 대한 정직한 한계

지원하지 않는 176개 예제를 모두 `Unknown`으로 abstain한 보수적 full-validation 결과는:

```text
Accuracy  = 41.67%
Macro-F1  = 31.97%
```

이다.

따라서 현재 PoC를 full FOLIO SOTA와 직접 경쟁하는 FOL reasoner로 주장하지 않는다. 현재 external result가 의미하는 것은 **지원하는 fragment에서 logical core가 정확하게 작동한다는 것**이며, full-FOL 확장은 향후 과제이다.

## 7.2 기존 Neuro-Symbolic 연구의 FOLIO 결과와의 위치

다음 수치는 본 연구에서 재실행한 결과가 아니라 각 선행연구에서 보고한 값이다. 프로토콜과 formalizer가 다르므로 Table 1의 28-example fragment와 직접적인 순위 비교에 사용하지 않는다.

### Logic-LM이 보고한 GPT-4 FOLIO Accuracy

| Method | FOLIO Accuracy |
|---|---:|
| GPT-4 Standard | 69.11% |
| GPT-4 CoT | 70.58% |
| **Logic-LM** | **78.92%** |

Logic-LM은 GPT-4 CoT 대비 약 **+8.34 pp**의 향상을 보고하였다. 이는 자연어 reasoning을 모두 LLM 내부에 두는 대신 symbolic solver를 이용하는 것이 효과적일 수 있음을 보여준다.

### LINC의 관찰

LINC는 external theorem prover를 결합했을 때 ProofWriter에서 매우 큰 향상을 보고했지만, FOLIO에서는 GPT-4 + LINC와 GPT-4 CoT의 차이가 통계적으로 유의하지 않았다고 보고하였다. 논문은 두 접근이 서로 다른 실패 유형을 보인다고 분석한다.

이 결과는 본 연구에도 중요하다.

```text
Solver의 논리 능력
        ≠
전체 자연어 시스템 성능
```

전체 성능은 다음 둘의 곱에 가깝다.

```text
Formalization Quality
        ×
Reasoner Correctness
```

본 연구의 FOLIO 실험은 Gold FOL annotation을 이용하므로 주로 두 번째 요소를 측정한다.

## 7.3 Experiment 2 — Perspective Index의 효과

### Table 2. Contradiction Scope Classification — 직접 실행 결과

| Method | Accuracy | Macro-F1 | Intra F1 | Inter F1 |
|---|---:|---:|---:|---:|
| Vanilla Merged Tableau | 75.00% | 66.67% | **0.00%** | 66.67% |
| **Perspective-Indexed Tableau** | **100.00%** | **100.00%** | **100.00%** | **100.00%** |
| **Rashomon-Tableau** | **100.00%** | **100.00%** | **100.00%** | **100.00%** |

향상폭:

```text
Accuracy
75.00 → 100.00
= +25.00 pp

Macro-F1
66.67 → 100.00
= +33.33 pp
```

### 왜 Vanilla Tableau의 Intra F1이 0인가

Vanilla baseline은 다음 하나만 검사한다.

```text
SAT(T ∪ A ∪ B)
```

따라서 `A` 내부가 이미 UNSAT이어도 최종 union이 UNSAT이라는 사실만 관찰한다. 실험 baseline은 모든 UNSAT union을 `Inter-Contradiction`으로 분류하기 때문에 20개의 Intra case를 모두 놓친다.

Perspective-Indexed 방식은 다음 세 값을 별도로 갖는다.

```text
SAT(T ∪ A)
SAT(T ∪ B)
SAT(T ∪ A ∪ B)
```

따라서 동일한 Tableau solver를 사용하면서도 contradiction location을 복원한다.

이 결과가 **기존 Tableau 대비 본 연구가 주장할 수 있는 가장 직접적인 성능 향상**이다.

## 7.4 Experiment 3 — Rashomon의 효과

### Table 3. Multi-Proof Explanation Coverage — 직접 실행 결과

| Method | Cases | Gold Minimal Explanations | Explanation Coverage |
|---|---:|---:|---:|
| Single-Proof Selection | 20 | 40 | 50.00% |
| **Rashomon Explanation Set** | 20 | 40 | **100.00%** |

향상:

```text
50.00 → 100.00
= +50.00 pp
```

각 case에는 두 개의 독립적 MUS가 있다.

Single-proof는 하나만 보여주므로:

```text
1 / 2 = 50%
```

Rashomon set은 두 설명을 모두 유지하므로:

```text
2 / 2 = 100%
```

### 중요한 해석

Rashomon layer의 효과는 다음과 같다.

```text
Classification Accuracy 향상      X
Alternative Explanation Coverage 향상 O
```

따라서 “Rashomon을 붙여 Accuracy가 25% 상승했다”라고 해석하면 잘못이다. Accuracy +25 pp는 **Perspective Index**의 효과이며, explanation coverage +50 pp가 **Rashomon layer**의 효과이다.

---

# 8. 전체 결과 요약

### Table 4. 각 구성요소가 실제로 개선한 대상

| 구성요소 | 평가 데이터 | 비교 기준 | 개선 전 | 개선 후 | 실제 향상 |
|---|---|---|---:|---:|---:|
| Semantic Tableau logical core | FOLIO supported fragment | Forward Horn Accuracy | 75.00% | 96.43% | **+21.43 pp** |
| Semantic Tableau logical core | FOLIO supported fragment | Forward Horn Macro-F1 | 74.18% | 96.33% | **+22.15 pp** |
| Perspective Index | 4-way scope benchmark | Merged Tableau Accuracy | 75.00% | 100.00% | **+25.00 pp** |
| Perspective Index | 4-way scope benchmark | Merged Tableau Macro-F1 | 66.67% | 100.00% | **+33.33 pp** |
| Rashomon Proof Set | multi-clash benchmark | Single-proof coverage | 50.00% | 100.00% | **+50.00 pp** |

이 표가 본 연구의 전체 주장을 가장 간단하게 보여준다.

```text
Tableau
→ 논리 추론 정확성

Perspective Index
→ 모순이 어디에서 생겼는지 식별

Rashomon Set
→ 얼마나 많은 타당한 설명을 보존하는지 개선
```

---

# 9. 논의

## 9.1 무엇이 새롭고, 무엇은 새롭지 않은가

### 새롭지 않은 것

- SAT/UNSAT 개념
- Tableau calculus 자체
- MUS 자체
- Rashomon Effect 자체
- LLM + symbolic solver 구조 자체

### 본 연구가 제안하는 것

```text
기존 요소들을
multi-context contradiction 문제에 맞게
하나의 reasoning protocol로 결합
```

구체적으로:

```text
Context-indexed SAT tests
        +
Contradiction scope semantics
        +
MUS enumeration
        +
Rashomon proof preservation
```

이다.

## 9.2 왜 Perspective가 중요한가

실제 시스템에서 provenance는 단순 metadata가 아니다.

예를 들어 장애 분석에서:

```text
APM Agent A: DB latency normal
DB Monitor B: DB latency abnormal
```

은 관점 간 모순일 수 있다.

반면 APM Agent A가 동시에:

```text
DB latency normal
DB latency not normal
```

을 말한다면 source 자체의 데이터 품질 또는 temporal alignment 문제일 수 있다.

두 상황은 조치가 완전히 다르다.

같은 원리는 다음에 적용된다.

- 법률 진술의 witness consistency
- 뉴스 source conflict
- 멀티에이전트 consensus
- 데이터 품질 검증
- 서로 다른 시점의 정책/규정 버전
- 지식그래프 merge conflict
- 의료·과학 문헌의 conflicting evidence

## 9.3 Rashomon을 왜 사용하는가

모순이 여러 독립 원인으로 발생할 수 있는데 하나의 MUS만 반환하면 사용자는 첫 번째로 발견된 clash를 전체 원인으로 오해할 수 있다.

Rashomon 관점은 다음 질문으로 바뀐다.

```text
"가장 좋은 설명은 무엇인가?"
            ↓
"거의 동등하게 타당한 설명은 몇 개인가?"
```

이렇게 하면 설명의 불확실성 자체를 사용자에게 보여줄 수 있다.

## 9.4 P-FOLIO와의 가능성

P-FOLIO는 같은 결론에 여러 reasoning chain이 존재할 수 있기 때문에 multiple sampled chains와 pass@k를 사용한다. 이는 향후 본 연구의 proof-level Rashomon set을 실제 human-written reasoning chain과 비교하기 좋은 데이터셋이다.

향후 평가에서는 다음이 가능하다.

```text
Human reasoning chains
vs
Single symbolic proof
vs
Rashomon symbolic proof set
```

평가 지표:

- proof coverage
- pass@k
- evidence faithfulness
- proof minimality
- human preference

---

# 10. 한계

## 10.1 Full FOLIO Coverage

현재 외부 FOLIO 실험은 204개 중 28개, 즉 13.73%의 strict fragment만 완전 지원한다.

따라서 96.43%를 **full FOLIO 성능이라고 표현해서는 안 된다.**

Full FOLIO를 지원하려면 다음 연산이 필요하다.

- `∃` existential quantification
- `∨` disjunction branching
- `↔` biconditional expansion
- XOR
- nested quantification
- equality / identity 처리

향후 HermiT, Pellet, Prover9 또는 full FOL backend를 붙여 확장해야 한다.

## 10.2 Controlled Scope Benchmark

Perspective scope +25 pp는 제안법의 구조적 차이를 검증하기 위해 설계한 controlled benchmark 결과이다. 자연 발생 multi-perspective corpus에서 동일한 향상폭이 보장되는 것은 아니다.

이를 위해 human-annotated CONAN 또는 다른 multi-source contradiction benchmark가 필요하다.

## 10.3 Controlled Rashomon Benchmark

Explanation +50 pp 역시 각 case에 두 개의 MUS가 존재하도록 명시적으로 구성한 실험이다. 실제 데이터에서는 MUS의 수와 품질이 다양하므로 P-FOLIO 등의 human proof data를 통한 후속 검증이 필요하다.

## 10.4 Natural Language Formalization Error

Gold logical form을 사용한 실험은 reasoner 성능을 분리해 측정할 수 있다는 장점이 있지만 실제 end-to-end 시스템에서는 자연어를 잘못 symbolization할 수 있다.

따라서 최종 end-to-end 성능은 다음 두 요소를 별도로 측정해야 한다.

```text
NL → Logic F1
        ×
Logic Reasoner Accuracy
```

---

# 11. 결론

본 연구는 multi-context 환경에서 전통적인 satisfiability reasoning이 잃어버릴 수 있는 **모순의 위치와 설명의 다양성**을 보존하기 위해 Rashomon-Tableau를 제안하였다.

연구 결과를 하나의 문장으로 정리하면 다음과 같다.

> **Semantic Tableau는 논리 추론을 담당하고, Perspective Index는 모순의 발생 범위를 식별하며, Rashomon Set은 하나의 결론에 존재하는 복수의 타당한 증명을 보존한다.**

실제 재현 실험에서는:

```text
FOLIO supported fragment
Forward → Semantic Tableau
Accuracy +21.43 pp
Macro-F1 +22.15 pp

Merged → Perspective Tableau
Scope Accuracy +25.00 pp
Macro-F1 +33.33 pp

Single Proof → Rashomon Set
Explanation Coverage +50.00 pp
```

를 확인하였다.

동시에 현재 구현의 한계도 분명하다. FOLIO 전체 문법 coverage는 13.73%에 불과하며, Perspective와 Rashomon의 개선폭은 controlled benchmark에서 측정되었다. 따라서 다음 단계는 full-FOL reasoner와 human-annotated multi-context benchmark를 연결하여 외부 타당성을 검증하는 것이다.

그럼에도 본 연구는 기존 Tableau의 역할을 단순 `SAT/UNSAT` 판정에서 다음과 같이 확장할 가능성을 제시한다.

```text
Is the knowledge base contradictory?
            ↓
Where does the contradiction originate?
            ↓
Which contexts are individually consistent?
            ↓
Which combinations become inconsistent?
            ↓
How many equally valid explanations exist?
```

이러한 질문은 탐정 서사를 넘어 서로 다른 데이터 출처와 가설이 공존하는 실제 AI reasoning system에서 중요한 의미를 갖는다.

---

# References

1. Baader, F., & Sattler, U. (2000). **Tableau Algorithms for Description Logics.** TABLEAUX 2000, LNCS/LNAI 1847, 1–18. https://doi.org/10.1007/10722086_1
2. Baader, F., & Sattler, U. (2001). **An Overview of Tableau Algorithms for Description Logics.** Studia Logica, 69, 5–40. https://doi.org/10.1023/A:1013882326814
3. Motik, B., Shearer, R., & Horrocks, I. (2009). **Hypertableau Reasoning for Description Logics.** Journal of Artificial Intelligence Research.
4. Breiman, L. (2001). **Statistical Modeling: The Two Cultures.** Statistical Science, 16(3), 199–231.
5. Fisher, A., Rudin, C., & Dominici, F. (2019). **All Models are Wrong, but Many are Useful: Learning a Variable's Importance by Studying an Entire Class of Prediction Models Simultaneously.** JMLR, 20(177), 1–81. https://jmlr.org/papers/v20/18-760.html
6. Xin, R., Zhong, C., Chen, Z., Takagi, T., Seltzer, M., & Rudin, C. (2022). **Exploring the Whole Rashomon Set of Sparse Decision Trees.** NeurIPS 2022.
7. Rudin, C., et al. (2024). **Position: Amazing Things Come From Having Many Good Models.** ICML 2024, PMLR 235, 42783–42795. https://proceedings.mlr.press/v235/rudin24a.html
8. Han, S., et al. (2022). **FOLIO: Natural Language Reasoning with First-Order Logic.** arXiv:2209.00840. https://arxiv.org/abs/2209.00840
9. Pan, L., et al. (2023). **Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning.** Findings of EMNLP 2023.
10. Olausson, T., et al. (2023). **LINC: A Neurosymbolic Approach for Logical Reasoning by Combining Language Models with First-Order Logic Provers.** EMNLP 2023. https://aclanthology.org/2023.emnlp-main.313/
11. Han, S., et al. (2024). **P-FOLIO: Evaluating and Improving Logical Reasoning with Abundant Human-Written Reasoning Chains.** arXiv:2410.09207. https://arxiv.org/abs/2410.09207
12. Tafjord, O., Dalvi, B., & Clark, P. (2021). **ProofWriter: Generating Implications, Proofs, and Abductive Statements over Natural Language.** Findings of ACL-IJCNLP 2021.
13. Zhao, W., et al. (2024). **Large Language Models Fall Short: Understanding Complex Relationships in Detective Narratives.** Findings of ACL 2024. (CONAN)
14. Hu, R., Lin, S., Xiu, Y., & Liu, Y. (2025). **LTRAG: Enhancing Autoformalization and Self-refinement for Logical Reasoning with Thought-Guided RAG.** Findings of ACL 2025. https://aclanthology.org/2025.findings-acl.126/

---

# Reproducibility

직접 실행 결과 파일:

- [`results/folio_fragment_metrics.json`](./results/folio_fragment_metrics.json)
- [`results/ablation_metrics.json`](./results/ablation_metrics.json)

실행:

```bash
python scripts/run_ablation.py
python scripts/evaluate_folio_fragment.py
pytest -q
```

GitHub Actions workflow:

```text
.github/workflows/external-benchmarks.yml
```

공식 FOLIO validation은 실행 시 Yale-LILY/FOLIO 저장소에서 직접 내려받는다.
