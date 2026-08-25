# 관련 연구 및 비교군 정의

## 1. 비교군 선정 목적

본 연구는 다중 홉 지식그래프 추론에서 발생하는 가지치기 손실을 분석하고, 고정 Top-K의 경계에서 가지치기를 선택적으로 지연하는 경계 인식 지연 가지치기(Boundary-Aware Delayed Pruning, BADP)를 평가한다. 따라서 비교 연구는 단순히 지식그래프 질의응답 정확도가 높은 방법을 나열하기보다, **탐색 폭 제어와 경로 가지치기 방식이 본 연구와 직접 연결되는 연구**를 중심으로 선정한다.

비교는 두 수준으로 구분한다.

1. **방법론 수준 비교**: 탐색 단위, 가지치기 기준, 탐색 폭 조정 방식, 비용 제어 방법을 비교한다.
2. **공통 벤치마크 비교**: WebQSP와 CWQ 등 동일 데이터셋에서 최종 정답 성능과 탐색 비용을 비교한다.

WN18RR의 탐색 성공률이나 MAGIC의 상충 경로 생존율은 KGQA의 최종 정답 정확도와 정의가 다르므로, 공개 peer의 WebQSP/CWQ 점수와 직접 순위를 매기지 않는다.

---

## 2. 고정 폭 그래프 추론

### 2.1 Think-on-Graph

Think-on-Graph(ToG)는 LLM이 지식그래프에서 관계와 개체를 반복적으로 탐색하면서 후보를 평가하고, 상위 `N`개를 유지하는 방식이다. 다중 경로를 유지한다는 점에서 본 연구와 공통점이 있으나, 후보 보존 기준은 기본적으로 고정된 순위 폭에 기반한다.

본 연구에서 ToG-style Top-3와 Top-5는 가장 중요한 내부 기준선이다. 비교의 핵심은 “ToG가 하나의 경로만 유지한다”는 것이 아니라 다음 차이에 있다.

\[
\text{Top-K}: \text{순위가 }K\text{를 넘으면 제거}
\]

\[
\text{BADP}: \text{Top-K를 유지하되 경계 점수가 불명확하면 인접 후보를 추가 보존}
\]

따라서 ToG는 **고정 폭 가지치기의 대표 비교군**으로 사용한다.

### 2.2 Think-on-Graph 2.0

ToG 2.0은 그래프 탐색과 문서 문맥 검색을 반복적으로 결합한다. 최종 시스템은 본 연구보다 넓은 검색 증강 생성 구조를 다루므로 BADP와 직접적인 알고리즘 단위 비교는 어렵다. 다만 다단계 검색 과정에서 후보를 반복적으로 축소한다는 점에서 외적 비교군으로 포함한다.

---

## 3. 경로 중심 가지치기 연구

### 3.1 Paths-over-Graph

Paths-over-Graph는 다중 홉 경로를 탐색하면서 그래프 구조, LLM, 언어모델 기반 점수를 조합해 후보를 단계적으로 줄인다. 경로 자체가 주요 검색 단위라는 점에서 BADP와 가까운 비교군이다.

차이는 연구 초점에 있다. Paths-over-Graph는 고품질 경로를 효율적으로 검색하는 전체 절차를 설계하는 반면, 본 연구는 **가지치기 직전에 존재했던 유효 경로가 제거되는 현상 자체를 측정**하고 그 손실을 줄이는 연산자에 초점을 둔다.

### 3.2 ProgRAG

ProgRAG는 관계와 트리플을 점진적으로 검색·정제하여 다중 홉 질의응답을 수행한다. 최근 KGQA에서 높은 성능을 보이는 비교군으로, 최종 WebQSP/CWQ 외적 타당성 비교에 포함한다. 그러나 본 연구의 가지치기 후회와 같은 비가역 경로 손실 지표를 직접 연구 대상으로 삼지는 않는다.

---

## 4. 효율성과 탐색 단위 확장 연구

### 4.1 FastToG

FastToG는 개별 경로 대신 그래프 커뮤니티를 탐색 단위로 사용하고, 거친 단계와 세밀한 단계의 가지치기를 통해 탐색 폭과 깊이를 확보한다. 따라서 BADP와 가지치기 단위는 다르지만, 정확도와 탐색 비용의 균형을 연구한다는 점에서 효율성 비교군으로 의미가 있다.

---

## 5. 적응형 탐색 폭 및 경계 연구

### 5.1 Plan-on-Graph

Plan-on-Graph는 질의와 현재 탐색 상태에 따라 탐색 폭을 조정한다. 공개 ablation에서도 적응형 폭이 최종 성능 개선에 기여하는 결과가 보고되었다. 따라서 **탐색 폭을 동적으로 바꾸는 것 자체는 본 연구의 신규성이 아니다.**

BADP의 차별점은 탐색 폭을 늘리는 기준을 Top-K의 실제 제거 경계에 국한한다는 것이다.

### 5.2 Query-Driven Adaptive Graph Retrieval

해당 연구는 질의 복잡도와 경로 점수 분포를 이용해 검색 규모를 적응적으로 결정한다. HotpotQA와 2WikiMultiHopQA를 중심으로 평가되어 WebQSP/CWQ 직접 비교군은 아니지만, “적응형 가지치기”가 이미 선행 연구에 존재함을 명확히 하는 방법론 비교군이다.

### 5.3 Flow-RAG

Flow-RAG는 점수 분포에 따라 문맥 적응형 결정 경계를 구성한다는 점에서 BADP와 가장 가까운 최근 개념 비교군이다. 따라서 본 연구는 “점수 분포를 이용한 최초의 적응형 경계”를 주장할 수 없다.

두 방법의 구별점은 다음과 같다.

| 구분 | Flow-RAG | BADP |
|---|---|---|
| 주요 목적 | 학습된 그래프 흐름 기반 검색 품질 향상 | 가지치기 단계의 비가역 손실 분석 및 완화 |
| 경계 기준 | 점수 분포를 이용한 적응형 결정 경계 | 고정 Top-K의 `K/K+1` 제거 경계 |
| 핵심 진단 | 검색·정답 성능 | 가지치기 후회, 유효 경로 생존 |
| 보존 방식 | 전체 검색 프레임워크 내 동적 필터링 | Top-K core + 경계 인접 후보의 국소 보존 |

---

## 6. 본 연구의 위치

선행 연구를 고려할 때 다음 주장은 사용하지 않는다.

- 최초의 적응형 가지치기
- 최초의 동적 빔 폭
- 최초의 다중 경로 지식그래프 추론
- 최초의 점수 분포 기반 가지치기
- 모든 조건에서 BADP가 Top-K보다 우수하다는 주장

대신 본 연구의 기여는 다음 네 항목으로 한정한다.

### 6.1 Top-K 경계를 비가역 의사결정 지점으로 정의

고정 Top-K에서 `K`번째와 `K+1`번째 사이의 점수 차이

\[
\Delta_K=s_{(K)}-s_{(K+1)}
\]

를 제거 의사결정의 불확실성으로 본다.

### 6.2 가지치기 후회 정식화

가지치기 전에는 목표까지 도달 가능한 경로가 존재했으나 가지치기 후 모두 제거된 경우를 별도 오류로 측정한다.

### 6.3 경계 국소 지연

최고점 주변의 후보를 광범위하게 보존하는 대신 `K`번째 cutoff 주변 후보만 추가 유지한다.

### 6.4 유효성과 비용을 포함한 평가

경로 생존율뿐 아니라 정밀도·재현율·F1, 평균 활성 폭, 확장 후보 수, 모델 호출과 토큰 비용을 함께 보고한다.

---

## 7. 최종 비교군 구성

| 분류 | 방법 | 본 연구에서의 역할 |
|---|---|---|
| 고정 폭 탐색 | ToG | Top-K 기준선의 대표 peer |
| 혼합 검색 | ToG 2.0 | 강한 KG/RAG 시스템 비교 |
| 경로 가지치기 | Paths-over-Graph | 경로 수준 pruning peer |
| 커뮤니티 탐색 | FastToG | 효율성·탐색 단위 비교 |
| 적응형 폭 | Plan-on-Graph | 동적 breadth 선행 연구 |
| 적응형 검색 규모 | Query-Driven Adaptive Graph Retrieval | novelty 경계 설정 |
| 적응형 결정 경계 | Flow-RAG | 가장 가까운 개념적 비교군 |
| 점진적 KGQA | ProgRAG | 최신 강한 WebQSP/CWQ 외적 비교군 |
| 제안 방법 | BADP | Top-K 경계 불확실성의 국소 지연 |

---

## 8. 비교 원칙

내부 ablation에서는 다음 조건을 동일하게 유지한다.

- 동일 그래프
- 동일 질의
- 동일 후보 생성
- 동일 점수기
- 동일 최대 홉 수
- 동일 전처리
- 가지치기 정책만 변경

적응형 정책의 파라미터는 최종 실험에서 개발 집합으로 선택하고 시험 집합에서는 고정해야 한다. Top-3와 Top-5를 비용 기준점으로 두며, 평균 활성 폭과 확장 후보 수가 유사한 설정끼리 우선 비교한다.

공개 논문의 Accuracy, EM, Hit@1은 평가 구현이 서로 다를 수 있으므로 원 논문 명칭을 유지해 참조하고, 직접 재현 실험에서는 공통 평가기로 EM, Macro-F1, Micro-F1, Hit@1을 동시에 계산한다.

---

## 9. 참고 문헌

1. Sun, J. et al. *Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph*. ICLR, 2024.
2. Ma, S. et al. *Think-on-Graph 2.0: Deep and Faithful Large Language Model Reasoning with Knowledge-guided Retrieval Augmented Generation*. ICLR, 2025.
3. Tan, X. et al. *Paths-over-Graph: Knowledge Graph Empowered Large Language Model Reasoning*. WWW, 2025.
4. Liang, X. and Gu, Z. *Fast Think-on-Graph: Wider, Deeper and Faster Reasoning of Large Language Model on Knowledge Graph*. AAAI, 2025.
5. Wang, H. et al. *A Query-Driven Graph Retrieval Framework with Adaptive Pruning for Multi-Hop Question Answering*. Electronics, 2026.
6. Zhang, W. et al. *Flow-RAG: Retrieval-Augmented Generation for Knowledge Graph Question Answering via Gated Flow Propagation*. Knowledge-Based Systems, 2026.
