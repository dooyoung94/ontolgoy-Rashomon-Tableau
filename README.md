# 조건부 경계 인식 지연 가지치기를 이용한 다중 홉 지식그래프 추론

## 1. 연구 개요

다중 홉 지식그래프 추론에서는 탐색 공간의 폭발을 제어하기 위해 매 단계에서 후보 경로를 제거하는 가지치기(pruning)가 필요하다. 대표적인 고정 폭 빔 탐색은 점수가 높은 상위 `K`개 후보만 유지하므로 계산 비용을 안정적으로 제한할 수 있다. 그러나 `K`번째와 `K+1`번째 후보의 점수가 거의 동일하더라도 순위 하나의 차이만으로 `K+1`번째 경로를 제거한다. 이 경로가 이후 단계에서 정답 또는 상반 증거로 이어지는 유일한 경로라면 해당 정보는 복구할 수 없다.

초기 BADP(Boundary-Aware Delayed Pruning)는 Top-K 경계 주변 후보를 항상 추가 보존하였다. 그러나 반복 탐색과 WebQSP 연결 실험에서는 경계가 이미 충분히 분리된 경우에도 추가 폭을 사용할 수 있다는 한계가 확인되었다. 따라서 현재 최종 제안은 **조건부 BADP(Conditional BADP)**이다.

핵심 질문은 다음과 같다.

> **Top-K 경계가 실제로 불확실한 경우에만 가지치기를 지연하면, 항상 후보 폭을 늘리는 방식보다 적은 추가 비용으로 비가역적인 유효 경로 손실을 줄일 수 있는가?**

현재 연구 범위는 최종 진실 판정이 아니라 **탐색 중 증거와 유효 경로의 보존**이다. 온톨로지·Tableau·가능세계 기반 상충 해결은 본 연구로 이어진 선행 과정이지만, 현재 논문의 직접적인 최적화 대상은 pruning operator이다.

---

## 2. 제안 방법

깊이 `k`에서 활성 경로 집합을 $P_k$, 확장 후보를 $C_{k+1}$라 하면 다음과 같다.

$$
C_{k+1}=\operatorname{Expand}(P_k,G)
$$

각 후보 경로 $p$에는 질의 $q$와의 점수를 부여한다.

$$
s_\theta(p,q)\in[0,1]
$$

### 2.1 고정 Top-K

후보 점수를 내림차순으로 정렬하면

$$
s_{(1)}\ge s_{(2)}\ge\cdots\ge s_{(|C|)}
$$

고정 Top-K는 다음 후보만 유지한다.

$$
T_K(C)=\{p_{(1)},\ldots,p_{(\min(K,|C|))}\}
$$

### 2.2 Always-on BADP

Top-K 경계 $s_{(K)}$ 아래에서 $\delta$ 이내인 후보를 추가 보존한다.

$$
B_{K,\delta}(C)
=
T_K(C)
\cup
\left\{p_{(j)}\mid j>K,\;s_{(K)}-s_{(j)}\le\delta\right\}
$$

이 방식은 실제 제거 경계 주변을 본다는 장점이 있지만, 모든 단계에서 작동하므로 추가 폭을 불필요하게 사용할 수 있다.

### 2.3 최종 제안: Conditional BADP

실제 Top-K 경계의 불확실성을 다음과 같이 측정한다.

$$
\Delta_K=s_{(K)}-s_{(K+1)}
$$

경계 margin이 임계값 $\tau$ 이하일 때에만 BADP를 발동한다.

$$
P_{k+1}^{CBADP}
=
\begin{cases}
B_{K,\delta}(C_{k+1}), & \Delta_K\le\tau \\
T_K(C_{k+1}), & \Delta_K>\tau
\end{cases}
$$

파라미터의 의미는 다음과 같다.

- $K$: 기본 Top-K 탐색 폭
- $\tau$: **경계가 위험한지 판단하는 발동 임계값**
- $\delta$: **발동한 뒤 추가 후보를 얼마나 보존할지 정하는 폭**

즉,

```text
tau   = 지금 Top-K 경계가 불확실한가?
delta = 불확실하다면 얼마나 더 보존할 것인가?
```

---

## 3. 왜 이 방법까지 오게 되었는가

본 연구는 처음부터 pruning만 연구한 것은 아니다.

```text
Rashomon Worlds + Tableau로 상충 해결
    ↓
실제 ontology에 필요한 relation semantics가 없음
    ↓
다중 홉 경로로 (h, ?, t)의 relation 후보를 예측
    ↓
Semantic scorer + Ontology/Tableau 제약 검증
    ↓
좋은 후보가 있어도 ranking/pruning에서 먼저 소실 가능
    ↓
Pruning Regret 측정
    ↓
전역 near-optimal 보존은 반복 탐색에서 비용/scale 문제
    ↓
실제 Top-K 경계를 보는 BADP
    ↓
항상 BADP를 켜도 비용만 증가하는 경우 발견
    ↓
Conditional BADP
```

특히 불완전한 온톨로지에서는 다음 세 문제를 구분해야 한다.

$$
\text{Graph Reachability}
\neq
\text{Semantic Relation}
\neq
\text{Logical Contradiction}
$$

온톨로지가 `(h, ?, t)`의 `?`를 스스로 생성하는 것은 아니므로, 선행 단계에서는 multi-hop relation completion을 이용해 관계 후보를 생성하고 Tableau를 **관계 생성기**가 아니라 **논리 제약 검증기**로 사용하는 구조를 구현하였다. 이 연구 발전 과정은 `studycase.md`에 상세히 정리한다.

---

## 4. 핵심 평가 지표

후보를 많이 남기면 성공 가능성은 올라갈 수 있지만 noise와 계산량도 증가한다. 따라서 세 축을 함께 평가한다.

| 평가 축 | 주요 지표 |
|---|---|
| 증거·경로 보존 | 탐색 성공률, 골드 경로 생존율, 유효 경로 생존율, 가지치기 후회 |
| 보존 집합의 유효성 | Precision, Recall, F1, 비유효 후보 보존율 |
| 탐색 비용 | 평균 활성 폭, 확장 후보 수, scorer 호출 수, LLM 호출·토큰·지연시간 |

### 4.1 가지치기 후회

가지치기 전에는 목표까지 도달 가능한 경로가 존재했으나 가지치기 후에는 하나도 남지 않은 경우를 Pruning Regret으로 정의한다.

$$
PR_{i,k}
=
\mathbf{1}
\left[
\exists p\in C_{i,k}:v_k(p)=1
\land
\nexists p\in P_{i,k}:v_k(p)=1
\right]
$$

### 4.2 Conditional BADP 발동 지표

조건부 방법은 실제로 얼마나 자주 켜졌는지를 반드시 함께 보고한다.

- boundary checks
- activation count
- activation rate
- activation당 추가 보존 후보 수
- 평균/최소/최대 boundary margin

이 값이 있어야 성능 향상이 단순한 폭 증가 때문인지, **위험한 경계에서만 선택적으로 예산을 쓴 결과인지** 구분할 수 있다.

---

## 5. 현재까지 검증된 주요 결과

### 5.1 MAGIC 외부 골드 상충 증거 보존

가지치기 이전에 골드 상충 경로가 존재하는 recoverable query 420개에서 다음 결과를 얻었다.

| 방법 | 상충 경로 생존율 | 골드 정밀도 | 골드 F1 | 평균 폭 |
|---|---:|---:|---:|---:|
| Top-3 | 94.76% | 59.38% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 70.54% | 1.79 |
| 전역 점수대 $\epsilon=.10$ | 97.14% | 50.18% | 66.18% | 1.94 |
| 상대 손실 $\epsilon=.25$ | 83.81% | 74.26% | 78.66% | 1.13 |
| Always BADP Top-3 $\delta=.01$ | **97.86%** | 55.30% | 70.67% | 1.77 |
| 무가지치기 | 100% | 46.67% | 63.64% | 2.15 |

후보 경로가 5개 이상인 고분기 query에서는 Top-3 생존율이 37.50%, Top-5가 75.00%까지 하락했다. 현재까지 가장 강하게 확인된 위험 요인은 **branching factor**이다.

### 5.2 WN18RR 반복 탐색

20개 2–4홉 질의의 기존 always-on 비교 결과는 다음과 같다.

| 방법 | 탐색 성공률 | 가지치기 후회 ↓ | 유효성 F1 | 평균 폭 | 확장 수 |
|---|---:|---:|---:|---:|---:|
| Top-3 | 50% | 50% | **33.58%** | 2.71 | 24.80 |
| Top-5 | 55% | 45% | 29.97% | 4.06 | 32.35 |
| Always BADP Top-3 $\delta=.005$ | 55% | 45% | 32.05% | 3.34 | 27.15 |
| Always BADP Top-5 $\delta=.010$ | 60% | 40% | 28.10% | 5.00 | 35.10 |
| Always BADP Top-5 $\delta=.050$ | **65%** | **35%** | 26.20% | 6.16 | 38.25 |

BADP는 추가 비용을 사용하면 성공률과 regret을 개선할 수 있었지만 retained-set F1과 비용이 함께 악화될 수 있었다. 이 결과가 Conditional BADP로 전환한 이유다.

### 5.3 WebQSP 초기 연결 검증

ToG 공식 WebQSP 질문을 사용한 첫 성공 연결은 `n=3`으로 수행되었다. Top-3, Top-5, always-on BADP가 모두 66.67% search success였고 BADP는 추가 정답을 복구하지 못하면서 폭만 증가하였다.

따라서 이 `n=3` 결과는 **성능 주장용이 아니라 파이프라인 연결과 always-on 방식의 실패 가능성을 확인한 파일럿**으로만 취급한다.

---

## 6. 현재 확대 실험

Conditional BADP를 다음 두 환경에서 확대 검증한다.

### WN18RR

- 50개 deterministic 2–4홉 query
- Top-3 / Top-5 / global / relative-loss / always BADP / Conditional BADP 동일 비교
- search success, pruning regret, viability F1, width, expansion 측정
- Conditional BADP activation diagnostics 추가

### WebQSP

- 초기 `n=3`에서 **`n=20`으로 확대**
- ToG 공식 WebQSP 질문 사용
- `qid_topic_entity`를 이용한 Wikidata entity exploration
- 동일 DeBERTa scorer와 동일 candidate generation을 모든 pruning policy에 공유
- Freebase 기반 ToG 전체 재현이 아니라 **pruning operator의 in-framework 비교**로 한정

최종 confirmatory 단계에서는 development set에서 $\tau$와 $\delta$를 선택하고 test에서는 고정한다.

---

## 7. 결과 검증 원칙

연구 과정에서 scorer input, API transport accounting, analyzer eligibility 등 구현 오류가 발견되었으므로 다음 원칙을 적용한다.

1. 수정 이전 실행값을 최종 정확도로 사용하지 않는다.
2. provenance metadata가 semantic scorer 입력에 포함되었던 자연어 MAGIC 결과는 최종 근거에서 제외한다.
3. retry와 logical-call accounting 수정 이전 비용 수치는 최종 비교에 사용하지 않는다.
4. analyzer eligibility 수정 이전 compute-matched 결과는 최종 통계로 사용하지 않는다.
5. workflow 표시 오류와 실제 산출물 오류를 구분한다.
6. scorer와 독립적인 외부 골드가 있으면 이를 우선한다.
7. post-hoc parameter 선택은 탐색적 결과로 표시한다.
8. 최종 시험에서는 development에서 hyperparameter를 동결한다.

---

## 8. 비교 연구

직접 비교군은 다음과 같다.

- Think-on-Graph(ToG): 고정 폭 반복 KG 탐색의 대표 기준선
- Think-on-Graph 2.0: 그래프와 문맥을 결합한 반복 검색
- Paths-over-Graph: 다단계 경로 가지치기
- FastToG: 커뮤니티 단위의 효율적 그래프 탐색
- Plan-on-Graph: 적응형 탐색 폭
- ProgRAG: 점진적 관계·트리플 검색
- Flow-RAG: 점수 분포 기반 적응형 경계

따라서 본 연구는 **최초의 적응형 가지치기**를 주장하지 않는다. 차별점은 Top-K의 `K/K+1` 경계를 명시적인 비가역적 의사결정 지점으로 정의하고, 실제 유효 경로가 소실된 사건을 Pruning Regret으로 측정하며, **경계 위험이 관찰되는 경우에만** 추가 보존을 수행한다는 데 있다.

---

## 9. 저장소 구성

| 파일 | 역할 |
|---|---|
| `RESEARCH_PAPER.md` | 국문 논문 본문 초안 |
| `studycase.md` | 선행 실험과 연구 질문 발전 과정 |
| `PEER_GROUP.md` | 관련 연구 및 비교군 정의 |
| `PEER_COMPARISON.md` | 비교 실험 및 공개 성능 참조 |
| `scripts/evaluate_iterative_pruning_budgeted.py` | WN18RR 기존 반복 pruning 비교 |
| `scripts/evaluate_iterative_pruning_conditional_badp.py` | WN18RR Conditional BADP 평가 |
| `scripts/evaluate_magic_conflict_preservation.py` | MAGIC 외부 골드 보존 분석 |
| `scripts/evaluate_webqsp_pruning_wikidata.py` | WebQSP 기본 pruning 비교 |
| `scripts/evaluate_webqsp_conditional_badp.py` | WebQSP Conditional BADP 평가 |
| `scripts/evaluate_kgqa_peer_metrics.py` | KGQA 공통 평가 지표 계산 |

---

## 10. 현재 연구 주장

현재 주장해야 할 내용은 `BADP가 항상 Top-K보다 우수하다`가 아니다.

보다 정확한 가설은 다음과 같다.

$$
\boxed{
\text{경계가 명확하면 Top-K}
\quad / \quad
\text{경계가 불확실할 때만 BADP}
}
$$

즉 본 연구는 **얼마나 많이 보존할 것인가**보다 **언제 고정 Top-K 경계를 신뢰하지 말아야 하는가**를 연구한다.
