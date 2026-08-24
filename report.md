# Rashomon-Tableau: Perspective-Indexed Satisfiability Reasoning for Multi-View Contradiction Detection and Multi-Proof Explanation

## 라쇼몽-태블로: 다중 관점 모순 탐지를 위한 관점 인덱스 기반 만족가능성 추론과 복수 증명 설명

---

## 초록

자연어 추론 시스템은 여러 문장이나 지식 조각 사이의 모순을 판별할 때 흔히 모든 정보를 하나의 지식베이스로 병합하거나, 문장 쌍을 Natural Language Inference(NLI) 문제로 변환한다. 그러나 서로 다른 화자, 문서, 시점, 관측원 또는 에이전트가 제공한 정보를 하나의 지식베이스로 조기에 병합하면 **모순이 존재한다는 사실은 검출할 수 있어도 그 모순이 한 관점 내부에서 발생한 것인지, 서로 독립적으로 일관적인 두 관점 사이에서 발생한 것인지 구분하기 어렵다.** 또한 NLI 기반 모델은 표면 문장 간 모순에는 강하지만 관계의 역관계, 계층 관계, 대칭성 등의 온톨로지 규칙을 따라 간접적으로 발생하는 implicit contradiction을 검증 가능한 논리 경로로 설명하기 어렵다.

본 연구는 이러한 문제를 해결하기 위해 **Rashomon-Tableau**를 제안한다. 핵심은 특정 탐정 서사 데이터셋에 특화된 모델이 아니라, 기존 Tableau satisfiability reasoning에 **Perspective Index**를 도입하는 것이다. 각 관점 `P_i`의 명제 집합을 독립 ABox `A_i`로 유지하고, 공통 Ontology/TBox `T`를 적용한 뒤 `SAT(T∪A_i)`, `SAT(T∪A_j)`, `SAT(T∪A_i∪A_j)`를 단계적으로 검사한다. 이를 통해 단순한 정보 차이인 **Divergence**, 하나의 관점 자체가 모순인 **Intra-Perspective Contradiction**, 개별 관점은 일관적이지만 결합 시 모순인 **Inter-Perspective Contradiction**을 분리한다. 모순이 발생하면 Minimal Unsatisfiable Subset(MUS)을 계산하고, 하나의 proof만 반환하는 대신 여러 독립적 또는 거의 동등한 최소 증명을 **Rashomon Explanation Set**으로 보존한다.

동일한 논리 규칙과 80개 controlled scope-ablation 사례에서 기존 merged-ABox Tableau는 4-way `Consistent / Divergence / Intra / Inter` 분류에서 Accuracy 0.750, Macro-F1 0.667을 기록한 반면, Perspective-Indexed Tableau는 Accuracy 1.000, Macro-F1 1.000을 기록하여 각각 **+25.0 percentage points**, **+33.3 percentage points** 개선되었다. 이 차이는 일반 SAT 판정 능력의 향상이 아니라 **모순의 발생 범위를 보존하는 능력의 향상**이다. 별도의 20개 multi-clash explanation 사례에서는 단일 proof 반환 방식의 최소 모순 설명 coverage가 0.500인 반면 Rashomon explanation enumeration은 1.000으로 **+50.0 percentage points** 향상되었다. 한편 기존 논리 추론 연구에서도 뉴로심볼릭 접근은 순수 LLM 대비 일관된 개선을 보고한다. Logic-LM은 5개 논리 benchmark 평균에서 standard prompting 대비 39.2%, CoT 대비 18.4% 향상을 보고했으며, LTRAG는 FOLIO에서 GPT-4o Standard 73.63%와 CoT 78.02% 대비 80.77%, AR-LSAT에서 40.26%와 43.72% 대비 56.71%를 기록하였다. 본 연구는 이러한 뉴로심볼릭 추론 흐름을 **다중 관점의 논리적 양립 가능성, 모순 범위 추적, 복수 proof 설명** 문제로 확장한다.

CONAN은 본 방법론의 multi-perspective 특성을 검증하기 위한 대표 데이터셋으로 사용하며, 방법 자체는 탐정 서사에 한정되지 않는다. LogicNLI, FOLIO, ProofWriter, AR-LSAT, FEVER 계열과 같은 논리/NLI/fact-verification benchmark로 확장할 수 있도록 데이터 어댑터와 평가 프로토콜을 설계한다.

**주요어:** Tableau Algorithm, Perspective-Aware Reasoning, Satisfiability, Ontology, Contradiction Detection, Rashomon Effect, Minimal Unsatisfiable Subset, Neuro-Symbolic AI, Explainable AI

---

# 1. 서론

## 1.1 연구 배경

현실의 지식은 하나의 일관된 출처에서만 생성되지 않는다. 뉴스 기사, 법률 진술, 회의 기록, 장애 분석 로그, 의료 기록, 다중 에이전트 시스템, 탐정 서사와 같은 환경에서는 동일 대상에 대해 여러 관측원과 화자가 서로 다른 정보를 제공한다. 따라서 모순 탐지 문제에서 중요한 것은 단순히 `A`와 `¬A`를 찾는 것이 아니라 **어떤 관점의 어떤 명제들이 결합될 때 모순이 발생하는지**를 보존하는 것이다.

기존 접근은 크게 두 방향으로 나뉜다.

첫째, NLI 기반 접근은 premise-hypothesis pair를 entailment, neutral, contradiction으로 분류한다. SNLI, MultiNLI, ANLI는 이 접근의 대표 benchmark다. 이러한 모델은 자연어 표현의 다양성을 처리하는 데 강하지만, 논리 규칙에 의해 여러 단계를 거쳐 발생하는 implicit contradiction과 proof-level explanation에는 한계가 있다.

둘째, symbolic 또는 neuro-symbolic 접근은 자연어를 논리 표현으로 변환한 후 theorem prover 또는 constraint solver를 사용한다. Logic-LM, LINC, LTRAG, Logic-Thinker 등은 FOLIO, ProofWriter, AR-LSAT 등에서 순수 prompting보다 높은 성능을 보고했다. 그러나 이들 연구의 핵심 문제는 주로 **하나의 문제 인스턴스 안에서 정답을 도출하는 것**이다. 서로 다른 출처/관점의 지식베이스를 독립적으로 유지한 뒤 모순의 발생 범위를 분류하는 문제는 별도의 축이다.

본 연구는 기존 Tableau의 SAT/UNSAT 판단 능력을 유지하면서 **Perspective Index**를 추가한다. 따라서 제안 방법의 핵심 주장은 “Tableau 자체보다 더 강력한 SAT solver를 만들었다”가 아니다. 오히려 다음 세 가지다.

1. **Perspective Separation**으로 기존 merged-KB가 잃어버리는 모순의 발생 범위를 보존한다.
2. **Ontology-mediated Tableau**로 explicit뿐 아니라 implicit contradiction을 검증한다.
3. **Rashomon Explanation Set**으로 하나의 proof를 선택할 때 손실되는 대안적 최소 설명을 보존한다.

## 1.2 핵심 문제 정의

본 연구의 출발점은 다음 문장이다.

```text
Different information ≠ Contradiction
Contradiction existence ≠ Contradiction scope
One valid proof ≠ All valid explanations
```

따라서 단순 binary contradiction을 다음처럼 확장한다.

| 상태 | 의미 |
|---|---|
| Consistent | 두 관점이 동일하거나 논리적으로 양립 가능 |
| Divergence | 서로 다른 정보를 제공하지만 동시에 참일 수 있음 |
| Intra-Perspective Contradiction | 적어도 하나의 관점 자체가 UNSAT |
| Inter-Perspective Contradiction | 각 관점은 SAT이나 결합된 지식베이스가 UNSAT |

## 1.3 연구 질문

- **RQ1. Autoformalization:** 자연어를 ontology-compatible proposition으로 얼마나 정확히 변환할 수 있는가?
- **RQ2. Perspective Scope:** Perspective-Indexed Tableau는 기존 merged-ABox Tableau보다 `Intra / Inter / Divergence / Consistent`를 더 정확히 구분하는가?
- **RQ3. Implicit Contradiction:** Ontology closure와 Tableau를 결합하면 NLI/LLM direct judge보다 간접 논리 모순을 안정적으로 검출할 수 있는가?
- **RQ4. Explanation Multiplicity:** Rashomon explanation set은 single-proof 방식보다 유효한 최소 모순 설명 coverage를 향상시키는가?
- **RQ5. Cross-Dataset Generality:** 제안한 관점-인덱스 추론 구조를 서사 데이터 외의 FOL/NLI/fact-verification benchmark에도 적용할 수 있는가?

## 1.4 연구 기여

본 연구의 기여는 다음과 같다.

1. **Perspective-Indexed Tableau**: 관점별 ABox를 유지하면서 local SAT와 joint SAT를 분리 검사하는 추론 구조.
2. **Contradiction Scope Classification**: contradiction existence를 넘어 intra/inter scope를 정의하고 정량 평가.
3. **Ontology-mediated Implicit Contradiction**: inverse, hierarchy, symmetry, incompatibility 등의 관계 의미를 통한 간접 clash 검출.
4. **Rashomon Explanation Set**: MUS 기반으로 복수의 최소 또는 근사 최소 증명을 보존하는 설명 구조.
5. **Controlled Ablation Protocol**: merged Tableau, perspective Tableau, Rashomon-Tableau의 기여를 분리해 평가.
6. **Cross-Dataset Evaluation Framework**: CONAN을 하나의 사례로 사용하되 LogicNLI, FOLIO, ProofWriter, AR-LSAT, FEVER 계열로 확장 가능한 평가 설계.

---

# 2. 관련 연구 및 기존 성능

## 2.1 NLI 기반 모순 탐지

LogicNLI는 모델의 first-order logical reasoning을 진단하기 위해 구축된 benchmark다. 공개 결과에서 RoBERTa는 Test-A Accuracy 68.3%, robustness Test-R 80.4%, generalization Test-G 49.9%를 기록했다. BERT는 각각 55.9%, 66.0%, 31.6%, XLNet은 65.4%, 78.9%, 43.0%를 기록했다. 특히 RoBERTa조차 generalization에서 49.9%에 머무른 것은 학습 기반 NLI 모델이 논리 구조의 분포 변화에 민감할 수 있음을 보여준다.

### LogicNLI 공개 결과

| Model | Test-A Accuracy | Test-R Robustness | Test-G Generalization |
|---|---:|---:|---:|
| BERT | 55.9 | 66.0 | 31.6 |
| RoBERTa | **68.3** | **80.4** | **49.9** |
| XLNet | 65.4 | 78.9 | 43.0 |

출처: Tian et al., *Diagnosing the First-Order Logical Reasoning Ability Through LogicNLI*, EMNLP 2021.

이 결과는 본 연구의 성능과 직접 동일 조건에서 비교한 것이 아니다. 본 연구에서는 이를 **학습 기반 logical NLI의 기준점**으로 사용하고, 추후 LogicNLI adapter를 통해 동일 데이터에서 직접 비교해야 한다.

## 2.2 Neuro-Symbolic Logical Reasoning

Logic-LM은 LLM을 semantic parser로 사용하고 symbolic solver에 추론을 위임한다. 저자들은 ProofWriter, PrOntoQA, FOLIO, LogicalDeduction, AR-LSAT의 5개 benchmark 평균에서 standard prompting 대비 **39.2%**, CoT prompting 대비 **18.4%**의 성능 향상을 보고했다.

이는 “LLM의 자연어 이해 + 결정적 symbolic reasoning”이라는 구조가 논리 문제에서 유효하다는 강한 근거다. Rashomon-Tableau도 동일한 큰 흐름에 속하지만, 차이는 symbolic solver의 목적이 최종 answer selection만이 아니라 **perspective-local consistency와 cross-perspective consistency를 분리해서 검증**한다는 데 있다.

## 2.3 FOLIO와 AR-LSAT에서의 공개 성능 비교

LTRAG 논문의 Table 1은 FOLIO와 AR-LSAT에서 Standard, CoT, LINC, Logic-LM, LTRAG를 비교한다. GPT-4o 기준 FOLIO에서는 Standard 73.63%, CoT 78.02%, LTRAG 80.77%를 기록한다. 같은 표에 인용된 기존 GPT-4 기반 Logic-LM은 78.92%, LINC는 72.50%다. AR-LSAT에서는 GPT-4o Standard 40.26%, CoT 43.72%, LTRAG 56.71%이며, 기존 Logic-LM 결과는 43.04%다.

### Published logical reasoning results

| Dataset | Method | Accuracy (%) | Source status |
|---|---|---:|---|
| FOLIO | GPT-4o Standard | 73.63 | LTRAG Table 1 |
| FOLIO | GPT-4o CoT | 78.02 | LTRAG Table 1 |
| FOLIO | LINC | 72.50 | imported by LTRAG from original paper |
| FOLIO | Logic-LM | 78.92 | imported by LTRAG from original paper |
| FOLIO | **LTRAG** | **80.77** | LTRAG Table 1 |
| AR-LSAT | GPT-4o Standard | 40.26 | LTRAG Table 1 |
| AR-LSAT | GPT-4o CoT | 43.72 | LTRAG Table 1 |
| AR-LSAT | Logic-LM | 43.04 | imported by LTRAG from original paper |
| AR-LSAT | **LTRAG** | **56.71** | LTRAG Table 1 |

이 표에서 LTRAG는 FOLIO에서 GPT-4o Standard 대비 **+7.14 pp**, CoT 대비 **+2.75 pp** 향상되며, AR-LSAT에서는 Standard 대비 **+16.45 pp**, CoT 대비 **+12.99 pp** 향상된다.

본 연구에서 이 수치를 제시하는 이유는 Rashomon-Tableau가 이미 이 결과를 능가했다고 주장하기 위해서가 아니다. 오히려 **symbolic solver를 결합하면 복잡한 논리 추론에서 순수 LLM보다 개선될 수 있다는 기존 실험적 근거**를 제시하고, 그 다음 연구 공백으로 “다중 관점과 contradiction scope”를 제안하기 위함이다.

## 2.4 ProofWriter/FOLIO의 추가 공개 결과

Logic-Thinker는 여러 logical benchmark에서 다음과 같은 결과를 보고한다.

| Method | ProofWriter | FOLIO |
|---|---:|---:|
| GPT-4 | 52.67 | 69.11 |
| GPT-CoT | 68.11 | 70.58 |
| Logic-LM | 79.66 | 78.92 |
| LINC | 98.30 | 72.50 |
| SymbolCoT | 82.50 | 83.33 |
| **Logic-Thinker** | **100.00** | 80.10 |

출처: *Logic-Thinker: Teaching Large Language Models to Think more Logically*, Findings of EMNLP 2025.

이 결과에서도 dataset에 따라 가장 좋은 접근이 달라진다. ProofWriter에서는 LINC와 Logic-Thinker가 매우 높지만 FOLIO에서는 SymbolCoT가 더 높다. 즉 **하나의 reasoning architecture가 모든 논리 데이터에서 항상 최고라고 볼 수 없으며**, 본 연구도 cross-dataset 실험이 필수적이다.

## 2.5 기존 Tableau와 본 연구의 차이

전통적인 Tableau는 하나의 knowledge base `K`에 대해 satisfiability를 판단한다.

```text
Tableau(K) -> SAT or UNSAT
```

다중 관점 정보가 `A_i`, `A_j`로 주어졌을 때 단순 병합하면

```text
Tableau(T ∪ A_i ∪ A_j)
```

만 검사하게 된다. 이 경우 union이 UNSAT이라는 사실은 알 수 있지만, 다음 두 경우를 구분하지 못한다.

### Case A: Intra contradiction

```text
SAT(T ∪ A_i) = 0
SAT(T ∪ A_j) = 1
SAT(T ∪ A_i ∪ A_j) = 0
```

### Case B: Inter contradiction

```text
SAT(T ∪ A_i) = 1
SAT(T ∪ A_j) = 1
SAT(T ∪ A_i ∪ A_j) = 0
```

두 경우 모두 merged Tableau의 최종 출력은 `UNSAT`이다. 따라서 본 연구의 novelty는 SAT solver 자체의 논리 완전성을 개선한 것이 아니라, **reasoning context를 perspective-indexed form으로 확장하여 UNSAT의 발생 범위를 추적**하는 것이다.

---

# 3. 제안 방법: Perspective-Indexed Tableau

## 3.1 관점별 지식베이스

관점 집합을

```text
P = {P_1, P_2, ..., P_m}
```

이라 하고, 각 관점의 명제 집합을

```text
A_i = {phi_i1, phi_i2, ..., phi_in}
```

으로 정의한다.

공통 ontology를 `T`라 하면 각 관점 KB는

```text
K_i = T ∪ A_i
```

이다.

핵심은 처음부터

```text
A_1 ∪ A_2 ∪ ... ∪ A_m
```

으로 병합하지 않는 것이다.

## 3.2 Intra-Perspective Contradiction

```text
C_intra(P_i) = 1 - SAT(T ∪ A_i)
```

`SAT(T∪A_i)=0`이면 그 모순은 외부 관점과 결합하기 전부터 존재한다.

## 3.3 Inter-Perspective Contradiction

```text
C_inter(P_i,P_j)
=
SAT(T∪A_i)
· SAT(T∪A_j)
· [1 - SAT(T∪A_i∪A_j)]
```

즉 각 관점은 독립적으로 일관적이지만 함께 참일 수 없는 경우다.

## 3.4 Divergence

```text
A_i != A_j
AND
SAT(T∪A_i∪A_j)=1
```

이면 contradiction이 아니라 divergence로 분류한다.

## 3.5 Ontology-mediated Implicit Contradiction

직접적인 동일 predicate의 positive/negative pair가 없어도

```text
T ∪ A_i |= phi
T ∪ A_j |= ¬phi
```

이면 implicit contradiction이다.

현재 PoC는 다음 관계 규칙을 지원한다.

- inverse
- hierarchy
- symmetry
- incompatible relation pair
- exclusive relation

예:

```text
father_of_x(A,B)
father_of_x ⊑ parent_of_x
¬parent_of_x(A,B)

→ parent_of_x(A,B)
→ CLASH
```

또는

```text
host_of_x(A,B)
host_of_x inverse guest_of_x
¬guest_of_x(B,A)

→ guest_of_x(B,A)
→ CLASH
```

---

# 4. Rashomon Explanation Set

## 4.1 문제: 하나의 proof만 반환할 때의 설명 손실

하나의 UNSAT knowledge base에는 서로 독립적인 여러 최소 모순 집합이 존재할 수 있다.

예를 들어

```text
MUS_1 = {
  father_of_x(P,C),
  ¬parent_of_x(P,C)
}

MUS_2 = {
  host_of_x(H,G),
  ¬guest_of_x(G,H)
}
```

가 동시에 존재할 수 있다.

기존 single-proof 출력은 하나를 찾는 순간 종료할 수 있다. 이는 contradiction existence에는 충분하지만 “왜 모순인가?”에 대한 가능한 설명을 일부 버린다.

## 4.2 Minimal Unsatisfiable Subset

```text
MUS(K)
=
min_{⊆}
{M ⊆ K : SAT(T∪M)=0}
```

## 4.3 Rashomon Explanation Set

모순 `c`를 증명하는 설명 경로들의 집합을

```text
Pi(c) = {pi_1, ..., pi_k}
```

라고 한다.

최고 점수와 충분히 가까운 증명을

```text
R_epsilon(c)
=
{pi : pi ⊢ contradiction,
      Score(pi) >= Score(pi*) - epsilon}
```

로 보존한다.

이때 Rashomon의 역할은 classification label을 바꾸는 것이 아니라 **설명의 다양성과 coverage를 유지하는 것**이다.

---

# 5. 데이터셋의 역할: CONAN은 사례이며 방법은 일반적이다

본 연구에서 CONAN은 연구 대상 자체가 아니라 **여러 인물 관점이 명시적으로 분리되어 있다는 장점 때문에 선택한 multi-perspective validation dataset**이다.

방법론을 데이터셋에 따라 다음처럼 매핑할 수 있다.

| Dataset | 원래 목적 | Perspective/Tableau 적용 |
|---|---|---|
| CONAN | 관계 추출, 다중 인물 서사 | character별 ABox, cross-character contradiction |
| LogicNLI | FOL logical NLI | premise groups를 perspective/context로 분리해 logical clash 검증 |
| FOLIO | NL + FOL reasoning | Gold FOL을 직접 Tableau 입력, autoformalization 오류 분리 평가 |
| ProofWriter | synthetic rule reasoning | proof correctness 및 implicit contradiction stress test |
| AR-LSAT | analytical constraint reasoning | competing constraint sets의 satisfiability 비교 |
| SNLI/MultiNLI/ANLI | pairwise NLI | neural contradiction baseline |
| FEVER/EX-FEVER | claim verification | claim vs evidence-source perspective, evidence proof evaluation |
| AVeriTeC | real-world fact checking | 출처별 evidence context를 perspective로 유지 |

따라서 논문의 핵심 claim은 다음이다.

> **Perspective-indexed satisfiability reasoning은 source-attributed multi-view knowledge가 존재하는 모든 domain에 적용 가능하며, CONAN은 그 중 하나의 실험 데이터셋이다.**

---

# 6. 실험 설계

## 6.1 Experiment 1: Controlled Reasoner Correctness

목적: ontology closure와 SAT/UNSAT 구현 검증.

CONAN Gold relation에서 생성된 80개 controlled 사례:

- Explicit contradiction: 20
- Hierarchy implicit contradiction: 10
- Inverse implicit contradiction: 10
- Consistent: 20
- Divergence: 20

현재 Rashomon-Tableau reasoner는 이 benchmark에서 Accuracy 1.000, Macro-F1 1.000, Implicit Contradiction Recall 1.000을 기록한다.

이 결과는 자연어 일반화 성능이 아니라 **symbolic reasoner correctness**다.

## 6.2 Experiment 2: 기존 Tableau 대비 Perspective Scope Ablation

### 비교 방법

- **Vanilla merged-ABox Tableau**: `SAT(T∪A_i∪A_j)`만 검사
- **Perspective Tableau**: local SAT `A_i`, `A_j` 후 union SAT 검사
- **Rashomon-Tableau**: Perspective Tableau와 동일한 판정 + multi-proof explanation

4개 클래스 각각 20개, 총 80개 controlled 사례를 구성한다.

```text
Consistent: 20
Divergence: 20
Intra contradiction: 20
Inter contradiction: 20
```

### 결과

| Method | Accuracy | Macro-F1 | Δ Accuracy vs Vanilla | Δ Macro-F1 vs Vanilla |
|---|---:|---:|---:|---:|
| Vanilla merged Tableau | 0.750 | 0.667 | - | - |
| **Perspective Tableau** | **1.000** | **1.000** | **+25.0 pp** | **+33.3 pp** |
| **Rashomon-Tableau** | **1.000** | **1.000** | **+25.0 pp** | **+33.3 pp** |

### 해석

이 결과는 “Perspective Tableau의 SAT solver가 Vanilla Tableau보다 더 강력하다”는 의미가 아니다.

Vanilla merged Tableau도 contradiction 자체는 발견한다. 그러나 이미 병합된 KB만 보면 intra contradiction과 inter contradiction의 provenance를 잃는다. 따라서 개선되는 것은

```text
Generic SAT accuracy          X
Contradiction scope accuracy  O
```

이다.

구체적으로 Vanilla baseline은 모든 UNSAT union을 inter contradiction으로 귀속하기 때문에 `Intra` 20개를 모두 오분류한다. Perspective Tableau는 local satisfiability를 먼저 검사하여 이를 복원한다.

## 6.3 Experiment 3: Rashomon Explanation Ablation

20개 사례 각각에 독립적인 최소 모순 2개를 구성한다.

```text
MUS A: hierarchy-mediated clash
MUS B: inverse-mediated clash
```

총 Gold minimal explanations = 40이다.

### 결과

| Explanation Method | Minimal Explanation Coverage |
|---|---:|
| Single best/first proof | 0.500 |
| **Rashomon explanation set** | **1.000** |
| Improvement | **+50.0 pp** |

이 결과도 classification 성능 향상이 아니다. 같은 contradiction label에 대해 **유효한 대안적 설명을 얼마나 보존하는지**의 차이다.

## 6.4 Experiment 4: Natural Multi-Perspective Benchmark

CONAN character pair에서 자동 후보를 추출하고 사람 annotator가 다음을 라벨링한다.

```text
consistent
divergence
intra_contradiction
inter_contradiction
unknown / insufficient evidence
```

비교군:

1. Pairwise NLI
2. LLM Direct Judge
3. Vanilla merged Tableau
4. Perspective Tableau
5. Rashomon-Tableau

평가:

- Accuracy
- Macro-F1
- Intra F1
- Inter F1
- Divergence F1
- Implicit contradiction recall
- Proof validity
- Evidence faithfulness
- Explanation coverage

## 6.5 Experiment 5: Cross-Dataset Logical Generalization

향후 동일 adapter interface로 다음 benchmark를 실행한다.

### LogicNLI

- 목적: neural NLI 대비 symbolic logical inference
- 주요 비교: RoBERTa Test-A 68.3, Test-G 49.9

### FOLIO

- 목적: 자연어 autoformalization과 FOL inference 분리
- published reference range: Standard GPT-4o 73.63, CoT 78.02, Logic-LM 78.92, LTRAG 80.77

### ProofWriter

- 목적: rule depth 증가에 따른 implicit inference 검증
- published reference: GPT-4 52.67, GPT-CoT 68.11, Logic-LM 79.66, LINC 98.30, Logic-Thinker 100.00

### AR-LSAT

- 목적: constraint-dense reasoning
- published reference: GPT-4o Standard 40.26, CoT 43.72, Logic-LM 43.04, LTRAG 56.71

### FEVER / EX-FEVER

- 목적: claim-evidence contradiction + multi-hop explanation
- 본 연구에서는 evidence source별 named context를 perspective index로 매핑한다.

---

# 7. 종합 결과 비교

## 7.1 우리 방법 내부 ablation

| 평가 축 | Vanilla Tableau | Perspective Tableau | Rashomon-Tableau |
|---|---:|---:|---:|
| SAT/UNSAT existence | O | O | O |
| Divergence 구분 | 부분 가능 | O | O |
| Intra vs Inter scope | X | **O** | **O** |
| Scope Accuracy | 75.0% | **100.0%** | **100.0%** |
| Scope Macro-F1 | 66.7% | **100.0%** | **100.0%** |
| Multi-MUS explanation | X | 기본적으로 single | **O** |
| Explanation Coverage | 50.0%* | 50.0%* | **100.0%** |

`*` single-proof baseline under the controlled two-MUS explanation benchmark.

## 7.2 기존 모델 공개 성능과의 위치

아래 표는 **동일 데이터에서 본 방법을 직접 실행한 결과가 아니라 관련 연구의 published benchmark results**다. 따라서 숫자 자체를 우리 방법과 직접 우열 비교하면 안 된다. 본 연구가 해결하려는 문제의 위치를 보여주기 위한 참고다.

| Dataset | Neural / Prompt Baseline | Neuro-Symbolic / Symbolic | Published Gain |
|---|---|---|---|
| Logic-LM 5-dataset avg. | Standard prompting | Logic-LM | +39.2% reported |
| Logic-LM 5-dataset avg. | CoT | Logic-LM | +18.4% reported |
| FOLIO | GPT-4o Standard 73.63 | LTRAG 80.77 | +7.14 pp |
| FOLIO | GPT-4o CoT 78.02 | LTRAG 80.77 | +2.75 pp |
| AR-LSAT | GPT-4o Standard 40.26 | LTRAG 56.71 | +16.45 pp |
| AR-LSAT | GPT-4o CoT 43.72 | LTRAG 56.71 | +12.99 pp |
| ProofWriter | GPT-4 52.67 | Logic-Thinker 100.00 | +47.33 pp |
| ProofWriter | GPT-CoT 68.11 | Logic-Thinker 100.00 | +31.89 pp |

이 공개 결과들이 반복해서 보여주는 것은 **논리 구조가 명확한 문제에서는 symbolic verification을 결합했을 때 순수 생성형 추론보다 개선될 가능성이 크다**는 점이다.

Rashomon-Tableau의 차별점은 이 성능 향상 흐름을 단순 answer accuracy가 아니라 다음으로 확장하는 데 있다.

```text
Answer correctness
        ↓
Logical satisfiability
        ↓
Perspective-aware contradiction scope
        ↓
Multiple valid contradiction explanations
```

---

# 8. 논의

## 8.1 본 연구의 실제 차별점

본 연구의 가장 중요한 차별점은 CONAN도, 탐정 서사도 아니다.

### 차별점 1: Tableau의 입력 구조

기존:

```text
K = T ∪ A_1 ∪ ... ∪ A_m
Tableau(K)
```

제안:

```text
Tableau(T ∪ A_1)
Tableau(T ∪ A_2)
...
Tableau(T ∪ A_i ∪ A_j)
```

즉 **perspective provenance를 추론 과정 끝까지 유지**한다.

### 차별점 2: Divergence와 Contradiction 분리

두 관점의 명제가 다르다는 이유만으로 contradiction으로 보지 않는다.

```text
Different + Joint SAT = Divergence
Different + Local SAT + Joint UNSAT = Inter Contradiction
Local UNSAT = Intra Contradiction
```

### 차별점 3: 단일 proof 강제 선택 방지

하나의 원인을 설명하는 여러 최소 충돌 경로가 존재할 수 있다. 본 연구에서는 이를 제거하지 않고 explanation set으로 보존한다.

## 8.2 ToG와의 차이

ToG가 묻는 질문:

```text
Which graph path is useful for answering q?
```

Rashomon-Tableau가 묻는 질문:

```text
Can these attributed sets of propositions coexist?
If not, where does inconsistency arise and what minimal proofs establish it?
```

ToG-like retrieval은 향후 large-scale KG에서 relevant subgraph를 줄이는 front-end로 결합할 수 있다.

```text
Graph Retrieval / ToG
        ↓
Relevant perspective subgraph
        ↓
Perspective-Indexed Tableau
        ↓
SAT / UNSAT / MUS
```

따라서 두 접근은 반드시 경쟁 관계가 아니라 retrieval과 verification의 역할 분리가 가능하다.

## 8.3 적용 가능 도메인

Perspective는 사람의 “관점”에만 한정되지 않는다.

```text
Person perspective
Document source
News outlet
Sensor
Log source
Database snapshot
Time window
Agent
Model hypothesis
```

모두 `context index`로 일반화할 수 있다.

따라서 최종적으로는 **Perspective-Indexed Tableau**보다 더 일반적인 용어인 **Context-Indexed Tableau Reasoning**으로 확장 가능하다.

---

# 9. 한계

첫째, 현재 구현은 full OWL-DL Tableau가 아니라 binary relation을 중심으로 한 lightweight relational Tableau다. existential restriction, disjunction, cardinality, qualified restriction 등은 지원하지 않는다.

둘째, +25.0 pp와 +33.3 pp의 scope 성능 개선은 controlled ablation 결과다. 자연어에서 자동 추출한 proposition error가 포함되면 성능은 낮아질 수 있다.

셋째, Rashomon explanation coverage +50.0 pp 역시 두 개의 독립 MUS를 의도적으로 포함한 controlled benchmark다. 자연 데이터에서 실제 대안 proof 분포가 어떻게 되는지 별도 평가가 필요하다.

넷째, FOLIO, LogicNLI, ProofWriter, AR-LSAT 표의 수치는 기존 논문에서 인용한 published results이며 현재 Rashomon-Tableau를 해당 benchmark에서 실행한 결과가 아니다. 향후 adapter 구현 후 동일 split과 동일 metric에서 직접 비교해야 한다.

다섯째, 자연어 autoformalization의 정확도가 전체 시스템의 상한을 결정할 수 있다. Logic-LM 계열 연구 역시 real-world FOLIO/AR-LSAT에서 executable logical form 생성이 synthetic benchmark보다 어렵다고 보고했다.

---

# 10. 결론

본 연구는 Tableau 기반 모순 추론에서 단순한 `SAT/UNSAT` 판정만으로는 다중 출처 지식의 구조를 충분히 설명할 수 없다는 문제에서 출발하였다.

제안한 Rashomon-Tableau는 각 정보 출처를 Perspective Index로 유지하여 다음 세 가지 질문을 분리한다.

```text
1. Is each perspective internally satisfiable?
2. Can multiple perspectives coexist?
3. If not, how many minimal valid explanations exist?
```

controlled scope ablation에서 기존 merged-ABox Tableau는 Accuracy 75.0%, Macro-F1 66.7%였으나 Perspective Tableau는 각각 100.0%, 100.0%로 향상되었다. 이는 **+25.0 pp Accuracy, +33.3 pp Macro-F1** 개선이다. 또한 multi-clash explanation benchmark에서 single-proof coverage 50.0% 대비 Rashomon explanation set은 100.0%를 기록하여 **+50.0 pp explanation coverage**를 보였다.

그러나 이 수치의 의미를 정확히 제한해야 한다. 본 연구는 기존 Tableau보다 더 강한 SAT solver를 주장하는 것이 아니다. 개선되는 것은 **perspective provenance가 필요한 contradiction-scope classification과 multi-proof explanation**이다.

Logic-LM, LINC, LTRAG, Logic-Thinker 등 기존 연구가 FOLIO, ProofWriter, AR-LSAT에서 보여준 symbolic reasoning의 성능 향상을 고려하면, 본 연구의 다음 핵심 단계는 Perspective-Indexed Tableau를 CONAN뿐 아니라 LogicNLI, FOLIO, ProofWriter, FEVER 계열에 직접 적용하여 동일 조건에서 cross-dataset generalization을 검증하는 것이다.

본 연구의 최종 주장은 다음 한 문장으로 요약된다.

> **모순을 탐지하는 것만으로는 충분하지 않다. 어떤 관점에서 모순이 발생했는지, 서로 다른 관점이 함께 참일 수 있는지, 그리고 그 모순을 설명하는 복수의 최소 증명이 무엇인지까지 보존해야 한다.**

---

# 참고문헌

1. Tian, J., Li, X., et al. **Diagnosing the First-Order Logical Reasoning Ability Through LogicNLI.** EMNLP 2021. https://aclanthology.org/2021.emnlp-main.303/
2. Bowman, S. R., et al. **A Large Annotated Corpus for Learning Natural Language Inference.** EMNLP 2015.
3. Williams, A., Nangia, N., Bowman, S. R. **A Broad-Coverage Challenge Corpus for Sentence Understanding through Inference.** NAACL 2018.
4. Nie, Y., et al. **Adversarial NLI: A New Benchmark for Natural Language Understanding.** ACL 2020.
5. Han, S., et al. **FOLIO: Natural Language Reasoning with First-Order Logic.** 2022.
6. Pan, L., Albalak, A., Wang, X., Wang, W. Y. **Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning.** Findings of EMNLP 2023. https://aclanthology.org/2023.findings-emnlp.248/
7. Olausson, T., et al. **LINC: A Neurosymbolic Approach for Logical Reasoning by Combining Language Models with First-Order Logic Provers.** EMNLP 2023.
8. Hu, R., Lin, S., Xiu, Y., Liu, Y. **LTRAG: Enhancing Autoformalization and Self-refinement for Logical Reasoning with Thought-Guided RAG.** Findings of ACL 2025. https://aclanthology.org/2025.findings-acl.126/
9. **Logic-Thinker: Teaching Large Language Models to Think more Logically.** Findings of EMNLP 2025.
10. Tafjord, O., et al. **ProofWriter: Generating Implications, Proofs, and Abductive Statements over Natural Language.** Findings of ACL/IJCAI-era logical reasoning work.
11. Thorne, J., et al. **FEVER: a Large-scale Dataset for Fact Extraction and VERification.** NAACL 2018.
12. Zhao, et al. **Large Language Models Fall Short: Understanding Complex Relationships in Detective Narratives.** Findings of ACL 2024.
13. Zhao, et al. **SymbolicThought: Integrating Language Models and Symbolic Reasoning for Consistent and Interpretable Human Relationship Understanding.** ACL 2026 Demo.
14. Sun, J., et al. **Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph.** 2023/ICLR-era work.
15. Musen, M. A. et al. OWL/Description Logic reasoner literature on Tableau-based satisfiability and ontology reasoning.

---

## 재현 가능한 본 저장소 결과

```bash
python scripts/run_ablation.py
```

결과 파일:

```text
results/ablation_metrics.json
```

현재 기록된 controlled 결과:

```text
Perspective scope ablation
- Vanilla merged Tableau: Accuracy 0.750 / Macro-F1 0.667
- Perspective Tableau:     Accuracy 1.000 / Macro-F1 1.000
- Gain:                    +25.0 pp / +33.3 pp

Rashomon explanation ablation
- Single proof coverage:    0.500
- Rashomon coverage:        1.000
- Gain:                    +50.0 pp
```
