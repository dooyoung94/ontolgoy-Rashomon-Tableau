# Rashomon-Tableau: Perspective-Aware Neuro-Symbolic Contradiction Reasoning over Multi-Perspective Detective Narratives

## 라쇼몽-태블로: 다중 관점 탐정 서사에서의 관점 인식형 뉴로-심볼릭 모순 추론

---

## 초록

다중 관점 자연어 서사에서는 동일 사건이나 인물 관계가 서로 다른 화자의 관점에서 상이하게 기술될 수 있다. 그러나 관점 간 서술 차이는 곧바로 논리적 모순을 의미하지 않는다. 기존 Natural Language Inference(NLI) 기반 모순 탐지는 주로 문장 쌍의 의미적 불일치를 판별하며, 그래프 기반 추론 방법은 지식그래프에서 정답을 지지하는 관계 경로를 탐색하는 데 초점을 둔다. 이러한 방법은 관점별 세계를 분리해 유지하면서 각 세계의 논리적 양립 가능성을 판정하거나, 온톨로지에 의해 간접적으로 유도되는 implicit contradiction을 설명 가능한 증명 경로로 제시하는 데 한계가 있다.

본 연구는 이를 해결하기 위해 **Rashomon-Tableau**를 제안한다. 제안 방법은 CONAN 탐정 서사의 각 인물 관점을 독립적인 ABox로 표현하고, 공통 관계 Ontology를 TBox로 구성한다. 이후 Ontology closure를 통해 inverse, hierarchy, symmetry 등 관계 의미를 확장하고, lightweight relational Tableau를 이용해 각 관점 및 관점 간 결합 지식베이스의 satisfiability를 검사한다. 개별 관점은 satisfiable하지만 두 관점을 결합했을 때 unsatisfiable한 경우를 inter-perspective contradiction으로 정의하고, 관점 간 정보가 다르지만 동시에 참일 수 있는 경우를 perspective divergence로 구분한다. 또한 모순 발생 시 Minimal Unsatisfiable Subset(MUS)을 추출하고, 하나의 최적 설명만 선택하지 않고 동등하거나 유사하게 타당한 복수의 증명 경로를 Rashomon explanation set으로 유지한다.

예비 controlled verification에서는 CONAN Gold relation으로부터 생성한 80개 사례를 대상으로 explicit contradiction, hierarchy-based implicit contradiction, inverse-based implicit contradiction, consistent, divergence를 평가하였다. 현재 구현은 Accuracy 1.000, Macro-F1 1.000, Implicit Contradiction Recall 1.000을 기록하였다. 단, 이 결과는 동일한 온톨로지 의미론으로 생성된 controlled benchmark에 대한 **reasoner correctness 검증값**이며 자연 서사 일반화 성능으로 해석하지 않는다. 향후 human-annotated CONAN perspective benchmark와 함께 SNLI, MultiNLI, ANLI, LogicNLI, FOLIO, FEVER, EX-FEVER 및 AVeriTeC를 보조 실험 데이터셋으로 활용해 자연어 모순 탐지, 논리 추론, 다중 증거 설명가능성을 교차 검증할 예정이다.

**주요어:** Rashomon Effect, Tableau Algorithm, Ontology Reasoning, Contradiction Detection, Multi-Perspective Narrative, Neuro-Symbolic AI, CONAN, Explainable AI

---

# 1. 서론

## 1.1 연구 배경

자연어 기반 지식 추론에서는 하나의 사건이나 관계가 서로 다른 화자에 의해 다르게 서술되는 상황이 빈번하게 발생한다. 특히 탐정 서사, 법률 진술, 뉴스 보도, 회의 기록, 정책 논쟁과 같이 여러 이해관계자의 관점이 동시에 존재하는 환경에서는 동일한 대상에 대해 서로 다른 정보가 제공될 수 있다.

이때 중요한 문제는 **정보의 차이와 논리적 모순을 구분하는 것**이다. 예를 들어 한 화자가 `John likes Mary`라고 말하고 다른 화자가 `John works with Susan`이라고 말하는 경우 두 서술은 서로 다르지만 동시에 참일 수 있다. 반면 한 관점에서 `Mary is Tom's daughter`라고 서술하고 다른 관점에서 `Mary is not Tom's child`라고 서술한다면 `DaughterOf ⊑ ChildOf`라는 온톨로지 규칙을 통해 간접적인 모순이 발생한다.

기존 NLI 기반 접근은 문장 쌍의 entailment, neutral, contradiction을 분류하는 데 효과적이지만, 여러 관계 규칙을 따라 추론한 후 나타나는 implicit contradiction이나 관점별 세계의 독립성을 명시적으로 다루기 어렵다. 반대로 ToG와 같은 그래프 기반 추론은 지식그래프에서 질문에 답하기 위한 관계 경로 탐색에 강점을 가지지만, 그래프 경로 자체의 존재보다 **여러 명제 집합이 동시에 참일 수 있는지**를 판정하는 문제와는 목표가 다르다.

## 1.2 문제 정의

본 연구의 핵심 문제는 다음과 같다.

```text
Different Perspective ≠ Contradiction
```

본 연구는 다중 관점 서사를 다음 네 범주로 구분한다.

1. **Consistent**: 동일하거나 양립 가능한 사실
2. **Perspective Divergence**: 서로 다른 정보를 제공하지만 동시에 참일 수 있음
3. **Intra-Perspective Contradiction**: 하나의 관점 내부에서 논리적 충돌 발생
4. **Inter-Perspective Contradiction**: 각 관점은 독립적으로 일관적이나 결합 시 충돌 발생

## 1.3 연구 질문

- **RQ1.** LLM은 다중 관점 자연어 서사를 논리 명제로 얼마나 정확하게 변환할 수 있는가?
- **RQ2.** 개별 관점의 내부 모순과 관점 간 모순을 Tableau 기반 satisfiability 검사로 구분할 수 있는가?
- **RQ3.** NLI 기반 pairwise contradiction과 비교했을 때 Ontology + Tableau 기반 논리 추론 방법이 implicit contradiction을 더 잘 탐지하는가?
- **RQ4.** 모순의 논리 경로와 최소 충돌 집합을 제공함으로써 설명가능성을 향상시킬 수 있는가?

## 1.4 연구 기여

- 관점 차이와 논리적 모순을 분리하는 **Perspective-Aware Contradiction Definition** 제안
- Ontology implication 기반 **implicit contradiction** 탐색
- Tableau satisfiability 기반 **검증 가능한 clash** 제공
- MUS와 복수 proof path를 결합한 **Rashomon Explanation Set** 제안
- CONAN 기반 재현 가능한 명제화/추론 평가 파이프라인 제공
- NLI, FOL, Fact Verification 계열 benchmark를 활용한 외부 타당성 검증 설계

---

# 2. 관련 연구

## 2.1 자연어 추론과 모순 탐지

SNLI는 대규모 자연어 추론 데이터셋을 제공하며 entailment, neutral, contradiction의 3-class 분류를 표준화한 대표 benchmark이다. 이후 MultiNLI는 10개의 서로 다른 장르를 포함해 도메인 일반화와 cross-genre reasoning을 평가하도록 확장되었다. ANLI는 human-and-model-in-the-loop adversarial 수집 방식으로 기존 NLI 모델의 취약점을 적극적으로 드러내도록 설계되었다.

이러한 데이터셋은 본 연구에서 Pairwise NLI baseline을 구축하는 데 유용하지만, 기본 단위가 `premise-hypothesis pair`라는 점에서 다중 관점 세계와 ontology-mediated contradiction을 직접 모델링하지는 않는다.

## 2.2 논리 추론 benchmark

LogicNLI는 first-order logic(FOL) 추론 능력을 진단하기 위해 구축된 NLI-style benchmark이며 accuracy, robustness, generalization, interpretability 관점에서 모델의 논리 능력을 분석한다. FOLIO는 자연어 premise와 FOL annotation을 동시에 제공하며, 1,430개의 conclusion example과 487개의 premise set을 포함한다. FOL 표현의 논리적 정합성을 inference engine으로 검증한다는 점에서 본 연구의 `Natural Language → Logical Proposition → Tableau` 구조와 직접적인 관련이 있다.

LogicBench는 명제논리, 일차논리, 비단조논리에 걸친 25개 추론 패턴을 체계적으로 평가하며 LLM이 복잡한 추론과 부정(negation)에서 어려움을 보인다는 결과를 보고한다. 최근 FOL-Traces는 프로그램적으로 검증된 대규모 first-order logic reasoning trace를 제공하여 추론 과정 자체의 정확성을 평가한다.

본 연구는 이들과 달리 논리 추론 자체뿐 아니라 **관점별 ABox 분리와 cross-perspective satisfiability**를 핵심 문제로 설정한다.

## 2.3 Fact Verification과 증거 기반 모순

FEVER는 Wikipedia 기반 claim을 Supported, Refuted, NotEnoughInfo로 분류하고 판단에 필요한 evidence sentence를 함께 제공한다. 이는 claim-evidence 수준에서 contradiction과 근거를 동시에 평가할 수 있다는 점에서 본 연구의 설명가능성 평가에 유용하다.

EX-FEVER는 2-hop과 3-hop 추론을 요구하는 60,000개 이상의 claim을 제공해 multi-hop explainable fact verification을 평가한다. AVeriTeC는 실제 fact-checker가 검증한 real-world claim에 대해 웹 증거를 검색하고 veracity를 판정하는 benchmark로, closed dataset을 넘어 실제 환경에서 evidence quality와 claim verification을 함께 평가한다.

본 연구에서는 FEVER 계열 데이터를 `관점 A = claim`, `관점 B = evidence-derived proposition` 형태로 변환해 contradiction proof와 evidence faithfulness를 검증할 수 있다.

## 2.4 그래프 기반 추론

ToG(Think-on-Graph)는 LLM이 Knowledge Graph의 관계와 엔티티를 반복적으로 탐색하며 질문에 답하기 위한 유망한 reasoning path를 선택한다. 이 방식의 핵심은 `answer-supporting path search`이며, 본 연구가 다루는 `logical compatibility test`와는 목적이 다르다.

본 연구는 그래프 경로가 존재하는가를 묻지 않고 다음을 묻는다.

```text
Can all propositions from multiple perspectives be true at the same time?
```

즉 graph traversal이 아니라 satisfiability와 clash를 핵심 연산으로 한다.

## 2.5 설명가능성과 Rashomon 관점

NILE은 NLI 모델이 label뿐 아니라 natural-language explanation을 생성하도록 하고 explanation faithfulness를 명시적으로 평가한다. 본 연구는 explanation을 자연어 rationale에만 의존하지 않고, ontology rule과 Tableau clash, MUS, derivation path를 통해 검증 가능한 구조로 표현한다.

Rashomon 관점은 하나의 관측에 대해 복수의 유사하게 타당한 설명 또는 모델이 존재할 수 있음을 강조한다. 본 연구는 이를 contradiction explanation으로 확장해 하나의 대표 proof만 고르는 대신, 일정 기준 내에서 타당한 여러 최소/근사 최소 proof path를 함께 보존한다.

---

# 3. 연구 방법

## 3.1 전체 구조

```text
CONAN Multi-Perspective Narrative
        ↓
Perspective Separation
        ↓
LLM / Gold Proposition Extraction
        ↓
Perspective-specific ABoxes
        ↓
Ontology Closure
        ↓
Intra / Cross-Perspective Tableau
        ↓
SAT / UNSAT
        ↓
Consistent / Divergence / Contradiction
        ↓
MUS
        ↓
Rashomon Explanation Set
```

## 3.2 관점별 지식베이스

관점 집합을 다음과 같이 정의한다.

```text
P = {P1, P2, ..., Pm}
```

각 관점 `P_i`의 명제 집합은

```text
A_i = {phi_i1, phi_i2, ..., phi_in}
```

이며 공통 온톨로지 TBox를 `T`라 하면

```text
K_i = T ∪ A_i
```

이다.

## 3.3 내부 모순

```text
C_intra(P_i) = 1 - SAT(T ∪ A_i)
```

`SAT(T ∪ A_i)=0`이면 한 관점 내부에서 이미 충돌이 발생한 것이다.

## 3.4 관점 간 모순

```text
SAT(T ∪ A_i) = 1
SAT(T ∪ A_j) = 1
SAT(T ∪ A_i ∪ A_j) = 0
```

이면

```text
C_inter(P_i,P_j)=1
```

로 정의한다.

## 3.5 Divergence

```text
A_i != A_j
SAT(T ∪ A_i ∪ A_j) = 1
```

이면 두 관점은 서로 다르지만 동시에 참일 수 있으므로 contradiction이 아니라 divergence로 분류한다.

## 3.6 Implicit Contradiction

직접적인 `phi`, `NOT phi` pair가 없더라도

```text
T ∪ A_i |= phi
T ∪ A_j |= NOT phi
```

이면 implicit contradiction으로 정의한다.

## 3.7 Ontology Rule

현재 PoC는 다음 관계 규칙을 사용한다.

- Symmetry
- Inverse
- Hierarchy
- Incompatible relation
- Exclusive / functional relation

예:

```text
DaughterOf(x,y) -> ChildOf(x,y)
HusbandOf(x,y) -> WifeOf(y,x)
```

## 3.8 Tableau 판정

Ontology closure 이후 다음 clash를 검사한다.

- Positive literal vs negated literal
- Incompatible relation pair
- Exclusive relation violation
- Hierarchy / inverse / symmetry로 유도된 implicit clash

## 3.9 MUS와 Rashomon Explanation Set

UNSAT이 발생하면 최소 충돌 집합을 추출한다.

```text
MUS_ij
= min {M subset A_i ∪ A_j | SAT(T ∪ M)=0}
```

모순 `c`를 설명하는 경로 집합을 `Pi(c)`라 할 때

```text
R_epsilon(c)
= {pi | pi proves c, Score(pi) >= Score(pi*) - epsilon}
```

으로 정의해 하나의 설명만 선택하지 않는다.

---

# 4. 실험 데이터셋

## 4.1 Primary Dataset: CONAN

본 연구의 핵심 데이터셋은 CONAN이다. CONAN은 동일 이야기 안에서 등장인물별 서사와 관계 라벨을 제공하므로 perspective-specific ABox를 구축하기에 적합하다.

사용 구조:

```text
data/english/data_final/<story>/txt/<character>.txt
data/english/label/<story>/<character>.json
```

관계 라벨은 다음 형태로 명제화한다.

```text
Subject -> [Object, Relation]
→ Relation(Subject, Object)
```

## 4.2 추가 비교/보조 데이터셋

| Dataset | 원 연구 목적 | 규모/특징 | 본 연구에서의 역할 | 연계 RQ |
|---|---|---|---|---|
| **SNLI** | NLI | 570K+ premise-hypothesis pairs | Pairwise contradiction baseline | RQ3 |
| **MultiNLI** | Multi-genre NLI | 433K examples, 10 genres | 장르 변화에 대한 NLI generalization | RQ3 |
| **ANLI** | Adversarial NLI | Human-model adversarial collection | 어려운 contradiction baseline | RQ3 |
| **LogicNLI** | FOL reasoning diagnosis | NLI-style logical reasoning | logical consistency / implicit contradiction 검증 | RQ1, RQ3 |
| **FOLIO** | NL + FOL reasoning | 1,430 conclusions, 487 premise sets | NL→FOL 명제화 + logical proof 검증 | RQ1, RQ3, RQ4 |
| **LogicBench** | Systematic logical reasoning | 25 logical reasoning patterns | negation/conditional/inference rule robustness | RQ3 |
| **FEVER** | Fact verification | 185,445 claims + evidence | Refuted claim을 evidence-based contradiction으로 변환 | RQ3, RQ4 |
| **EX-FEVER** | Multi-hop explainable fact verification | 60K+ claims, 2-hop/3-hop | 다중 단계 모순 경로와 설명 평가 | RQ3, RQ4 |
| **AVeriTeC** | Real-world claim verification | Web evidence + real fact-check claims | 실제 환경 외부 타당성 검증 | RQ3, RQ4 |
| **FOL-Traces** | Verified FOL reasoning traces | Programmatically verified traces | Tableau derivation path correctness 비교 | RQ4 |

### 권장 우선순위

논문 본 실험에서 모든 데이터셋을 동시에 사용하는 것은 범위가 지나치게 커질 수 있다. 따라서 다음 순서를 권장한다.

```text
Primary:
CONAN

Core External Validation:
FOLIO + LogicNLI + FEVER

Strong NLI Baseline:
ANLI or MultiNLI

Explainability Extension:
EX-FEVER

Real-world Extension:
AVeriTeC
```

가장 현실적인 본 논문 구성은 다음 5개 데이터셋이다.

```text
CONAN + FOLIO + LogicNLI + ANLI + FEVER
```

- CONAN: 관점 효과
- FOLIO: NL→Logic 변환
- LogicNLI: 논리 추론
- ANLI: 강한 NLI contradiction baseline
- FEVER: evidence 기반 contradiction / explanation

---

# 5. 실험 설계

## 5.1 RQ1: 자연어 명제 변환

### CONAN

```text
Character Narrative
→ LLM Proposition Extraction
→ CONAN Gold Triple
```

평가:

- Triple Precision
- Triple Recall
- Triple F1

### FOLIO 보조 평가

FOLIO의 NL-FOL pair를 이용해 다음을 추가로 평가한다.

- Predicate identification
- Argument alignment
- Polarity / negation accuracy
- Logical form exact match

이를 통해 CONAN 관계 라벨만으로 평가하기 어려운 복잡 논리식 변환 능력을 보완한다.

## 5.2 RQ2: 내부/관점 간 모순

CONAN에서 각 perspective ABox를 분리해 다음 세 번의 검사를 수행한다.

```text
SAT(T ∪ A_i)
SAT(T ∪ A_j)
SAT(T ∪ A_i ∪ A_j)
```

## 5.3 RQ3: NLI 대비 implicit contradiction

비교 모델:

- Pairwise NLI
- LLM Direct Judge
- Ontology Rule Only
- Vanilla Tableau
- Perspective-separated Tableau
- Rashomon-Tableau

평가 데이터:

- CONAN annotated contradiction benchmark
- ANLI contradiction subset
- LogicNLI
- FOLIO
- FEVER Refuted subset

핵심 지표:

- Accuracy
- Macro-F1
- Explicit Contradiction Recall
- Implicit Contradiction Recall
- Negation-sensitive Accuracy

## 5.4 RQ4: 설명가능성

데이터:

- CONAN
- FOLIO
- FEVER
- EX-FEVER

평가:

- Proof Validity
- Evidence Faithfulness
- Path Completeness
- MUS Minimality
- Alternative Explanation Coverage
- Human Evaluation

EX-FEVER의 2-hop/3-hop 구조를 이용하면 `단일 clash`가 아니라 `다단계 derivation path`의 설명 품질을 평가할 수 있다.

---

# 6. Baseline 및 Ablation

## 6.1 Baseline

```text
B1. Pairwise NLI
B2. LLM Direct Contradiction Judge
B3. Ontology Rule Only
B4. Vanilla Merged-ABox Tableau
B5. Perspective-separated Tableau
B6. Rashomon-Tableau
```

## 6.2 Ablation

```text
Tableau
  vs
Tableau + Ontology
  vs
Tableau + Ontology + Perspective Separation
  vs
Tableau + Ontology + Perspective Separation + Rashomon
```

이를 통해 각각 다음 효과를 분리한다.

- Ontology inference contribution
- Perspective separation contribution
- MUS contribution
- Rashomon multiple-explanation contribution

---

# 7. 예비 실험 결과

## 7.1 Controlled Verification

현재 구현의 correctness를 확인하기 위해 CONAN Gold relation으로 controlled case를 구성하였다.

### 설정

- Story: `655-The Mysterious Case of Zhangdong Town (6 people)`
- Sample perspectives: `Xiting`, `Yang Minxi`
- Seed: `42`
- Total cases: `80`

### 사례 구성

| Subtype | Cases |
|---|---:|
| Explicit contradiction | 20 |
| Hierarchy implicit contradiction | 10 |
| Inverse implicit contradiction | 10 |
| Consistent | 20 |
| Divergence | 20 |

### 결과

| Metric | Score |
|---|---:|
| Accuracy | **1.000** |
| Macro-F1 | **1.000** |
| Implicit Contradiction Recall | **1.000** |

Subtype별 Accuracy도 모두 1.000이었다.

## 7.2 결과 해석의 제한

이 결과는 자연어 일반화 성능이 아니다. Controlled benchmark는 CONAN Gold proposition에 Ontology 규칙을 적용해 생성한 사례이므로, 동일한 의미론을 사용하는 Tableau reasoner가 올바르게 구현되었는지 확인하는 **unit/functional correctness evaluation**에 가깝다.

따라서 다음 주장을 해서는 안 된다.

```text
Rashomon-Tableau achieves 100% contradiction detection accuracy on natural narratives.
```

대신 다음과 같이 기술해야 한다.

```text
The current controlled evaluation verifies that the implemented reasoner
correctly handles explicit, hierarchy-mediated, inverse-mediated contradictions,
consistency, and divergence under the encoded ontology semantics.
```

자연 서사 성능은 human-annotated benchmark 및 외부 데이터셋 실험 이후 별도로 보고해야 한다.

---

# 8. 논의

## 8.1 NLI와의 차이

NLI는 기본적으로 `premise → hypothesis` 관계를 분류한다. 반면 본 연구는 여러 관점의 명제 집합 전체를 하나의 논리 세계로 보고 satisfiability를 검사한다.

```text
NLI:
P(contradiction | premise, hypothesis)

Rashomon-Tableau:
SAT(T ∪ A_i ∪ A_j) ?
```

따라서 결과가 확률 score가 아니라 논리적 `SAT/UNSAT`와 clash 경로라는 점이 다르다.

## 8.2 ToG와의 차이

ToG는 답을 지지하는 경로를 탐색한다.

```text
pi* = argmax P(pi | q, G)
```

본 연구는 답 경로가 아니라 관점의 동시 만족 가능성을 검사한다.

```text
SAT(T ∪ A_i ∪ A_j)
```

즉 graph search와 logical compatibility test의 차이이다.

## 8.3 Rashomon의 역할

일반적인 Tableau는 모순 여부를 판정할 수 있지만, 동일한 contradiction에 대해 복수의 최소/근사 최소 설명이 존재할 수 있다. 본 연구는 이를 제거하지 않고 explanation set으로 유지한다.

이 구조는 다음 두 가지 효과를 기대한다.

- 특정 proof path 하나에 대한 과도한 의존 감소
- 사용자에게 대안적 원인/설명 경로 제공

## 8.4 데이터셋 확장의 의미

CONAN만 사용하면 탐정 서사와 인물 관계라는 특정 도메인에 결과가 종속될 수 있다. 따라서 외부 데이터셋을 다음과 같이 역할별로 분리해 검증하는 것이 중요하다.

```text
CONAN   → Perspective reasoning
FOLIO   → NL-to-FOL / deductive reasoning
LogicNLI→ Formal logical consistency
ANLI    → Adversarial contradiction
FEVER   → Evidence-backed contradiction
EX-FEVER→ Multi-hop explanation
AVeriTeC→ Real-world verification
```

이렇게 하면 단일 데이터셋 성능이 아니라 방법론의 각 구성 요소를 독립적으로 검증할 수 있다.

---

# 9. 한계

현재 연구의 주요 한계는 다음과 같다.

1. 현재 Tableau는 full OWL-DL reasoner가 아니라 binary relation 중심 lightweight reasoner이다.
2. 현재 Ontology rule은 수작업으로 정의된 관계 규칙을 포함한다.
3. CONAN은 원래 contradiction benchmark가 아니므로 human annotation이 추가로 필요하다.
4. Controlled score 1.000은 자연어 generalization 성능이 아니다.
5. Rashomon explanation quality에 대한 인간 평가가 아직 수행되지 않았다.
6. LLM proposition extraction error가 downstream Tableau result에 직접 영향을 줄 수 있다.

향후 OWLReady2, Pellet, HermiT 등의 reasoner와 비교하고, ontology induction 자동화 및 confidence-aware proposition handling을 추가할 필요가 있다.

---

# 10. 결론

본 연구는 다중 관점 자연어 서사에서 단순한 정보 차이와 실제 논리적 모순을 구분하기 위한 **Rashomon-Tableau** 프레임워크를 제안하였다. 핵심은 각 관점을 독립적인 ABox로 유지하고, 공통 Ontology에 기반한 의미 확장 이후 Tableau satisfiability 검사를 수행하는 것이다.

이를 통해 각 관점 자체는 일관적이지만 결합할 경우에만 발생하는 inter-perspective contradiction을 명시적으로 정의할 수 있으며, hierarchy나 inverse rule을 거쳐 발생하는 implicit contradiction도 탐색할 수 있다. 또한 MUS와 Rashomon explanation set을 활용해 하나의 설명 경로만 제시하지 않고 여러 타당한 논리 경로를 보존한다.

예비 controlled verification에서 explicit, hierarchy implicit, inverse implicit contradiction과 consistent/divergence 사례를 모두 정확히 처리함을 확인하였다. 다음 단계에서는 human-annotated CONAN benchmark와 함께 FOLIO, LogicNLI, ANLI, FEVER, EX-FEVER를 이용해 실제 자연어 환경에서의 정확도, implicit contradiction 탐지력, explanation faithfulness를 평가해야 한다.

본 연구의 최종 목표는 단순히 `contradiction 여부`를 분류하는 것이 아니라 다음 질문에 답하는 것이다.

```text
Can these perspectives coexist?
If not, why not?
And are there multiple equally valid ways to explain the inconsistency?
```

---

# 11. 참고문헌

1. Bowman, S. R., Angeli, G., Potts, C., & Manning, C. D. (2015). **A Large Annotated Corpus for Learning Natural Language Inference.** EMNLP 2015. https://aclanthology.org/D15-1075/
2. Williams, A., Nangia, N., & Bowman, S. R. (2018). **A Broad-Coverage Challenge Corpus for Sentence Understanding through Inference.** NAACL 2018. https://aclanthology.org/N18-1101/
3. Nie, Y., Williams, A., Dinan, E., Bansal, M., Weston, J., & Kiela, D. (2020). **Adversarial NLI: A New Benchmark for Natural Language Understanding.** ACL 2020. https://aclanthology.org/2020.acl-main.441/
4. Tian, J., Li, Y., Chen, W., Xiao, L., He, H., & Jin, Y. (2021). **Diagnosing the First-Order Logical Reasoning Ability Through LogicNLI.** EMNLP 2021. https://aclanthology.org/2021.emnlp-main.303/
5. Han, S. et al. (2024). **FOLIO: Natural Language Reasoning with First-Order Logic.** EMNLP 2024. https://aclanthology.org/2024.emnlp-main.1229/
6. Parmar, M. et al. (2024). **LogicBench: Towards Systematic Evaluation of Logical Reasoning Ability of Large Language Models.** ACL 2024. https://aclanthology.org/2024.acl-long.739/
7. Thorne, J., Vlachos, A., Christodoulopoulos, C., & Mittal, A. (2018). **FEVER: a Large-scale Dataset for Fact Extraction and VERification.** NAACL 2018. https://aclanthology.org/N18-1074/
8. Ma, H. et al. (2024). **EX-FEVER: A Dataset for Multi-hop Explainable Fact Verification.** Findings of ACL 2024. https://aclanthology.org/2024.findings-acl.556/
9. Schlichtkrull, M. et al. (2024). **The Automated Verification of Textual Claims (AVeriTeC) Shared Task.** FEVER 2024. https://aclanthology.org/2024.fever-1.1/
10. Kumar, S., & Talukdar, P. (2020). **NILE: Natural Language Inference with Faithful Natural Language Explanations.** ACL 2020. https://aclanthology.org/2020.acl-main.771/
11. Schuster, T. et al. (2019). **Towards Debiasing Fact Verification Models.** EMNLP-IJCNLP 2019. https://aclanthology.org/D19-1341/
12. Pratapa, A., Jayanthi, S. M., & Nerella, K. (2020). **Constrained Fact Verification for FEVER.** EMNLP 2020. https://aclanthology.org/2020.emnlp-main.629/
13. Portelli, B., Zhao, J., Schuster, T., Serra, G., & Santus, E. (2020). **Distilling the Evidence to Augment Fact Verification Models.** FEVER 2020. https://aclanthology.org/2020.fever-1.7/
14. Saakyan, A., Chakrabarty, T., & Muresan, S. (2021). **COVID-Fact: Fact Extraction and Verification of Real-World Claims on COVID-19 Pandemic.** ACL 2021. https://aclanthology.org/2021.acl-long.165/
15. Wang, S. et al. (2022). **Logic-Driven Context Extension and Data Augmentation for Logical Reasoning of Text.** Findings of ACL 2022. https://aclanthology.org/2022.findings-acl.127/
16. Ryb, S., Giulianelli, M., Sinclair, A., & Fernández, R. (2022). **AnaLog: Testing Analytical and Deductive Logic Learnability in Language Models.** *SEM 2022. https://aclanthology.org/2022.starsem-1.5/
17. Yuan, Z., Hu, S., Vulić, I., Korhonen, A., & Meng, Z. (2023). **Can Pretrained Language Models (Yet) Reason Deductively?** EACL 2023. https://aclanthology.org/2023.eacl-main.106/
18. Zhao et al. (2024). **Large Language Models Fall Short: Understanding Complex Relationships in Detective Narratives.** Findings of ACL 2024.
19. Zhao et al. (2026). **SymbolicThought: Integrating Language Models and Symbolic Reasoning for Consistent and Interpretable Human Relationship Understanding.** ACL 2026 Demo. https://aclanthology.org/2026.acl-demo.4/
20. **It Takes Two to Tango: The Rashomon Effect in Machine Translation.** NLPerspectives 2026. https://aclanthology.org/2026.nlperspectives-1.2/
21. Sun et al. (2024). **Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph.** ICLR 2024.
22. **FOL-Traces: Verified First-Order Logic Reasoning Traces at Scale.** Findings of EACL 2026. https://aclanthology.org/2026.findings-eacl.115/

---

## 권장 논문 실험 패키지

최종 논문에서 가장 균형 잡힌 실험 조합은 다음과 같다.

```text
CONAN
+ ANLI
+ LogicNLI
+ FOLIO
+ FEVER
```

설명가능성까지 강조하려면 다음을 추가한다.

```text
+ EX-FEVER
```

실제 웹 기반 claim verification까지 확장하려면 다음을 추가한다.

```text
+ AVeriTeC
```
