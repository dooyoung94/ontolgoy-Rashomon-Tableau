# 다중 홉 지식그래프 추론에서 경계 불확실성을 이용한 조건부 지연 가지치기

## 초록

다중 홉 지식그래프 추론에서는 탐색 깊이가 증가할수록 후보 경로 수가 빠르게 증가하므로 가지치기가 필수적이다. 대표적인 고정 폭 빔 탐색은 각 단계에서 상위 `K`개 후보만 유지하여 비용을 안정적으로 제어한다. 그러나 `K`번째 후보와 `K+1`번째 후보의 점수가 거의 같은 경우에도 후자는 순위 하나의 차이만으로 비가역적으로 제거된다. 제거된 후보가 이후 정답이나 상반 증거로 이어지는 유일한 경로라면 후속 의미 검증기나 논리 추론기는 해당 정보를 복구할 수 없다.

본 연구는 가지치기 이전에 유효 경로가 존재했으나 선택 이후 모두 사라지는 사건을 **가지치기 후회(Pruning Regret)**로 정의한다. 초기에는 최고점 주변의 후보를 전역적으로 보존하는 Rashomon-inspired score band와 Top-K 경계 주변을 추가 보존하는 경계 인식 지연 가지치기(BADP)를 검토하였다. 그러나 반복 탐색과 WebQSP 연결 실험에서 항상 더 많은 후보를 보존하는 방식은 탐색 비용과 비유효 후보를 증가시킬 수 있음이 확인되었다. 이에 본 연구의 최종 제안법은 **조건부 경계 인식 지연 가지치기(Conditional BADP)**이다. Conditional BADP는 `K`번째와 `K+1`번째 점수 차이가 충분히 작을 때에만 BADP를 발동하고, 그 외에는 기존 Top-K를 그대로 사용한다.

MAGIC 외부 골드 분석에서는 recoverable conflict query 420개에서 Top-3의 conflict path survival이 94.76%였고, always-on Boundary Top-3는 평균 폭을 1.60에서 1.77로 늘리면서 97.86%까지 높였다. 반면 후보 경로가 5개 이상인 고분기 구간에서는 Top-3와 Top-5의 생존율이 각각 37.50%와 75.00%로 하락하여 branching이 고정 폭 가지치기의 주요 위험 요인임을 확인하였다. WN18RR 반복 탐색에서도 BADP가 성공률을 높일 수 있었지만 추가 탐색 비용을 사용하였다. WebQSP 3질의 연결 검증에서는 always-on BADP가 Top-K보다 추가 정답을 복구하지 못하면서 폭만 증가하였다. 이 결과들은 지연 가지치기를 항상 적용하기보다 **경계 위험이 관찰될 때만 선택적으로 적용해야 한다**는 현재 가설을 뒷받침한다.

본 연구는 최종 정답 정확도만으로 가지치기를 평가하지 않고, 정답·증거 생존, 보존 집합 유효성, 가지치기 후회, 평균 탐색 폭과 확장량을 함께 측정한다. 현재 Conditional BADP는 WN18RR 50질의와 WebQSP 20질의에서 직접 검증 중이며, 최종 주장은 개발 집합에서 `tau`와 `delta`를 고정한 뒤 독립 시험 집합에서 확인한다.

**주요어:** 지식그래프, 다중 홉 추론, 가지치기, 빔 탐색, 가지치기 후회, 경계 불확실성, 조건부 탐색

---

## 1. 서론

지식그래프 기반 다중 홉 추론은 하나의 시작 개체에서 관계와 개체를 반복적으로 확장하면서 답이나 근거에 도달한다. 깊이가 증가할수록 후보 경로의 수는 조합적으로 증가하기 때문에 실제 시스템은 모든 경로를 유지할 수 없으며, 점수가 낮은 후보를 중간 단계에서 제거한다.

고정 Top-K는 가장 단순하고 안정적인 방법이다. 후보 경로를 점수 순으로 정렬한 뒤 상위 `K`개만 다음 단계로 전달한다. 문제는 이 규칙이 **점수의 절대적 또는 상대적 확신과 무관하게 항상 동일한 개수만 남긴다**는 점이다. 예를 들어 `K`번째와 `K+1`번째의 점수가 각각 0.812와 0.809라면 두 후보 사이의 차이는 0.003에 불과하지만 후자는 즉시 제거된다.

다중 홉 검색에서 이 결정은 비가역적이다. 따라서 최종 답변기의 성능만 분석하면 검색 중간에 이미 발생한 정보 손실을 구분하기 어렵다. 본 연구는 이 중간 실패를 독립된 연구 대상으로 본다.

본 연구는 처음부터 가지치기 문제만을 다룬 것은 아니다. 초기에는 복수의 설명을 Rashomon Worlds로 유지하고, 불완전하거나 상충하는 관계를 온톨지와 Tableau로 검증하는 구조를 연구하였다. 그러나 실제 데이터에서는 온톨로지가 필요한 관계 의미를 모두 포함하지 않았고, 다중 홉 경로가 존재하더라도 직접 관계를 자동으로 만들어 주지 못했다. 이에 다중 홉 경로를 이용해 누락 관계 후보를 예측하고 semantic scorer로 점수화한 뒤 Tableau를 제약 검증기로 사용하는 relation completion 구조를 검토하였다. 이후 실험에서는 좋은 관계 후보가 존재하더라도 중간 pruning 단계에서 먼저 사라질 수 있다는 문제가 더 근본적인 병목으로 나타났다.

따라서 현재 연구의 핵심 질문은 다음과 같다.

> **Top-K 경계가 실제로 불확실한 경우에만 선택적으로 가지치기를 지연하면, always-on adaptive widening보다 적은 비용으로 비가역적인 유효 경로 손실을 줄일 수 있는가?**

본 연구의 주요 기여는 다음과 같다.

1. 유효 경로가 pruning 직전에 존재했지만 선택 이후 모두 제거되는 사건을 **Pruning Regret**으로 정식화한다.
2. Top-K의 실제 제거 경계인 `K/K+1` 점수 차이를 **경계 위험도(boundary risk)**로 정의한다.
3. 경계 위험도가 임계값 이하일 때에만 추가 후보를 보존하는 **Conditional BADP**를 제안한다.
4. 성능을 단순 survival이나 candidate count로 평가하지 않고 **성공/보존 × 보존 집합 유효성 × 탐색 비용**의 세 축으로 분석한다.
5. MAGIC 외부 골드, WN18RR 반복 탐색, WebQSP 실제 질의를 이용하여 통제된 구조 분석과 외적 타당성 검증을 분리한다.

---

## 2. 연구 배경 및 관련 연구

### 2.1 고정 폭 지식그래프 탐색

Think-on-Graph(ToG)는 LLM을 이용해 관계와 개체를 반복적으로 평가하면서 제한된 수의 후보를 유지한다. 본 연구는 ToG가 단일 경로만 사용하는 것으로 가정하지 않는다. 차이는 multi-path 여부가 아니라 **고정된 Top-K 경계를 언제 신뢰할 수 있는지**에 있다.

### 2.2 경로 단위 및 적응형 가지치기

Paths-over-Graph는 경로를 여러 단계로 축소하고, FastToG는 커뮤니티 단위 탐색과 coarse/fine pruning을 수행한다. Plan-on-Graph 및 최근 adaptive retrieval 연구는 질의 난이도나 탐색 상태에 따라 breadth를 조정한다. Flow-RAG와 같은 연구도 score distribution에 따른 적응형 decision boundary를 사용한다.

따라서 본 연구는 `adaptive pruning` 자체를 최초 기여로 주장하지 않는다. 차별점은 **Top-K의 바로 그 제거 경계를 오류 발생 지점으로 명시하고, 그 경계에서 실제 유효 경로가 사라지는 사건을 Pruning Regret으로 측정한다는 점**이다.

### 2.3 불완전한 온톨로지와 관계 예측

초기 연구에서는 온톨로지 규칙과 Tableau가 multi-hop conflict를 직접 해결할 수 있을 것으로 기대하였다. 그러나 실제 온톨로지는 필요한 관계 합성, 배타성, 역관계 등의 의미를 모두 포함하지 않는다.

관찰 경로가 다음과 같더라도,

$$
h \xrightarrow{r_1} e_1 \xrightarrow{r_2} \cdots \xrightarrow{r_m} t
$$

직접 관계

$$
(h, ?, t)
$$

를 Tableau가 스스로 생성하지는 않는다. 따라서 한때 본 연구는 다중 홉 경로로 관계 후보를 예측하고 semantic scorer와 Tableau를 결합하는 구조를 구현하였다. 이 과정에서 온톨로지의 역할을 **관계 생성기**가 아니라 **후보 관계의 논리적 제약 검증기**로 재정의하였다.

이 선행 연구는 현재 pruning 연구와 직접 연결된다. 관계 후보 생성과 검증이 아무리 좋아도 후보가 중간 검색에서 먼저 제거되면 후속 검증은 수행될 수 없기 때문이다.

---

## 3. 문제 정의

지식그래프를 다음과 같이 정의한다.

$$
G=(V,E,R)
$$

질의 `q`에 대해 깊이 `k`에서 유지되는 부분 경로 집합을 $P_k$라 하고, 다음 단계 후보는 다음과 같이 생성한다.

$$
C_{k+1}=\operatorname{Expand}(P_k,G)
$$

각 후보 경로 $p$에는 scorer가 점수를 부여한다.

$$
s_\theta(p,q)\in[0,1]
$$

현재 반복 WN18RR 실험에서는 edge별 DeBERTa support를 계산한 뒤 경로 평균을 사용한다.

$$
s_\theta(p,q)=\frac{1}{|p|}\sum_{e\in p}s_\theta(e,q)
$$

모든 pruning 정책에서 candidate generation과 scorer는 동일하게 고정한다. 실험 변수는 retention operator뿐이다.

### 3.1 고정 Top-K

후보를 점수 내림차순으로 정렬한다.

$$
s_{(1)}\ge s_{(2)}\ge\cdots\ge s_{(|C|)}
$$

고정 Top-K는 다음 집합만 유지한다.

$$
T_K(C)=\{p_{(1)},\ldots,p_{(\min(K,|C|))}\}
$$

### 3.2 유효 부분 경로

부분 경로 $p$가 남은 hop budget 내에서 목표까지 도달할 수 있다면 다음과 같이 정의한다.

$$
v_k(p)=1
$$

MAGIC에서는 graph reachability 대신 외부 골드 `perturb_triplet` provenance를 이용해 conflict evidence path의 유효성을 정의한다.

### 3.3 가지치기 후회

질의 $i$, 깊이 $k$에서 pruning 이전 후보 집합에 유효 경로가 존재하지만 pruning 이후 하나도 남지 않은 경우를 Pruning Regret으로 정의한다.

$$
PR_{i,k}
=
\mathbf{1}
\left[
\exists p\in C_{i,k}:v_k(p)=1
\;\land\;
\nexists p\in P_{i,k}:v_k(p)=1
\right]
$$

질의 수준의 Pruning Regret은 다음과 같다.

$$
QPR_i=\max_k PR_{i,k}
$$

데이터셋 수준에서는 평균을 사용한다.

$$
QPR=\frac{1}{N}\sum_{i=1}^{N}QPR_i
$$

---

## 4. 비교 가지치기 정책

### 4.1 전역 가산 점수대

최고 점수를

$$
s^*=\max_{p\in C}s_\theta(p,q)
$$

라 할 때 전역 near-optimal 집합은 다음과 같다.

$$
R_\epsilon(C)
=
\{p\in C\mid s_\theta(p,q)\ge s^*-\epsilon\}
$$

Frozen candidate 실험에서는 유망했지만 iterative search에서는 score scale에 민감하여 Top-K보다 나빠지는 경우가 확인되었다.

### 4.2 상대 손실 기준

점수 스케일 문제를 줄이기 위해 다음 손실을 정의한다.

$$
L(p,q)=1-s_\theta(p,q)
$$

최소 손실이 $L^*$일 때 다음 후보를 보존한다.

$$
R_{\epsilon}^{loss}(C)
=
\{p\mid L(p,q)\le(1+\epsilon)L^*\}
$$

점수 형태로 쓰면 다음과 같다.

$$
s_\theta(p,q)\ge s^*-\epsilon(1-s^*)
$$

### 4.3 Always-on BADP

BADP는 최고점이 아니라 실제 Top-K cutoff를 기준으로 한다.

$$
b_K(C)=s_{(K)}
$$

기본 BADP 집합은 다음과 같다.

$$
B_{K,\delta}(C)
=
T_K(C)
\cup
\left\{
p_{(j)}\mid j>K,\; s_{(K)}-s_{(j)}\le\delta
\right\}
$$

이 방법은 Top-K가 제거하려는 경계 주변의 후보만 추가 보존한다. 그러나 WebQSP 초기 연결에서는 항상 BADP를 적용해도 추가 정답 없이 비용만 증가하는 경우가 확인되었다.

---

## 5. 제안 방법: Conditional BADP

### 5.1 경계 불확실성

Top-K의 바로 다음 후보와의 점수 차이를 경계 margin으로 정의한다.

$$
\Delta_K(C)=s_{(K)}-s_{(K+1)}
$$

$\Delta_K$가 작으면 scorer가 $K$번째와 $K+1$번째 후보를 명확하게 구분하지 못한다고 해석한다.

### 5.2 조건부 발동 규칙

Conditional BADP는 경계 margin이 임계값 $\tau$ 이하인 경우에만 BADP를 사용한다.

$$
P_{k+1}^{CBADP}
=
\begin{cases}
B_{K,\delta}(C_{k+1}), & \Delta_K(C_{k+1})\le\tau \\
T_K(C_{k+1}), & \Delta_K(C_{k+1})>\tau
\end{cases}
$$

$|C|\le K$이면 모든 후보를 유지한다.

파라미터의 역할은 분리된다.

- $K$: 기본 탐색 폭
- $\tau$: **지연 가지치기를 발동할지 결정하는 경계 위험 임계값**
- $\delta$: **발동된 경우 K번째 점수 아래로 얼마나 추가 보존할지 결정하는 허용 폭**

즉,

```text
tau   : 지금 이 경계가 위험한가?
delta : 위험하다면 어느 정도까지 추가 보존할 것인가?
```

### 5.3 설계 목적

Always-on BADP의 문제는 모든 단계에서 추가 후보를 보존할 가능성이 있다는 점이다. Conditional BADP는 다음 두 상황을 분리한다.

```text
경계가 명확함
→ Top-K 그대로 사용
→ 추가 비용 없음

경계가 불확실함
→ BADP 일시 활성화
→ K 주변 후보만 추가 보존
```

따라서 목표는 최고 survival이 아니라 **필요한 순간에만 추가 budget을 사용하는 것**이다.

---

## 6. 평가 지표

### 6.1 탐색 성공률

목표 또는 골드 증거에 제한 hop 내 도달하면 성공으로 정의한다.

$$
Success_i=\mathbf{1}[\text{retained search reaches target evidence}]
$$

### 6.2 보존 집합 유효성

더 많이 남겼다는 이유만으로 좋은 pruning이라고 판단하지 않는다.

WN18RR에서 retained path가 남은 hop budget 내 목표까지 도달 가능하면 viable path로 정의한다.

$$
Precision_{viable}
=
\frac{\#\text{viable retained paths}}
{\#\text{retained paths}}
$$

$$
Recall_{viable}
=
\frac{\#\text{viable retained paths}}
{\#\text{viable candidate paths}}
$$

MAGIC에서는 외부 골드 conflict path에 대해 retained gold precision, recall, F1을 사용한다.

### 6.3 탐색 비용

다음 지표를 함께 보고한다.

- 평균 활성 폭
- 질의당 확장 후보 수
- unique scorer calls
- 가능한 경우 context token과 latency

최종 평가는 다음의 세 축으로 본다.

$$
\boxed{
\text{Search / Evidence Preservation}
\times
\text{Retained-set Validity}
\times
\text{Search Cost}
}
$$

---

## 7. 연구 가설

### H1. 고정 경계 손실

고정 Top-K에서는 pruning 직전 viable path가 존재했음에도 순위 cutoff 때문에 모두 소실되는 query가 존재한다.

### H2. 분기 민감성

candidate branching이 증가할수록 fixed Top-K의 Pruning Regret이 증가한다.

### H3. 경계 위험 가설

작은 boundary margin 구간에서 Pruning Regret 발생 확률이 더 높다.

$$
P(PR=1\mid\Delta_K\le\tau)
>
P(PR=1\mid\Delta_K>\tau)
$$

단, 기존 MAGIC top-2 margin 분석에서는 margin과 branching이 강하게 함께 변했기 때문에 margin의 독립 효과는 아직 확정하지 않는다.

### H4. 조건부 BADP 가설

동일하거나 유사한 평균 탐색 비용에서 Conditional BADP는 always-on BADP보다 불필요한 width 증가를 줄이면서 Top-K보다 낮은 Pruning Regret 또는 높은 search success를 달성한다.

---

## 8. 실험 설계

### 8.1 MAGIC: 외부 골드 conflict preservation

MAGIC의 `perturb_triplet` provenance를 scorer와 독립적인 외부 골드로 사용한다. 전체 1,056 query 중 candidate path가 존재한 query는 618개이고, pruning 이전에 골드 conflict path가 존재한 recoverable query는 420개이다.

이 실험은 최종 truth resolution이 아니라 **동일 frozen path scores에서 pruning operator가 conflict evidence를 얼마나 보존하는지**를 분석한다.

### 8.2 WN18RR: 반복 다중 홉 탐색

2–4 hop target path가 존재하도록 deterministic benchmark를 구성하고 각 단계에서 실제 후보 확장과 pruning을 반복한다. 동일 DeBERTa edge scorer를 모든 정책에 공유한다.

기존 n=10, n=20 결과는 방법 개발용 pilot이며, Conditional BADP는 n=50으로 확대한다.

### 8.3 WebQSP: 실제 KGQA 질의 연결

ToG가 공개한 WebQSP 질문과 `qid_topic_entity`를 사용하고 Wikidata entity statements를 탐색한다. 현재 연결 실험은 Freebase 기반 ToG 전체 재현이 아니라 **같은 실제 질문에서 pruning operator만 비교하기 위한 in-framework 외적 타당성 실험**이다.

초기 n=3 pipeline validation 이후 Conditional BADP 실험을 n=20으로 확대한다. 공개 Wikidata API rate limit 때문에 후보 폭과 요청 간격을 통제한다.

### 8.4 비교 정책

- Top-3
- Top-5
- Global additive band
- Relative-loss band
- Always-on BADP
- **Conditional BADP**

Conditional BADP의 pilot grid는 다음과 같다.

```text
Top-3:
tau = .005 / .010 / .020
delta = .005 / .010

Top-5:
tau = .010 / .020 / .050
delta = .010 / .020
```

최종 confirmatory test에서는 development 결과를 이용해 파라미터를 고정한 뒤 test에서 변경하지 않는다.

---

## 9. 결과

### 9.1 MAGIC 외부 골드: 전체 recoverable query

| 정책 | Conflict Path Survival | Gold Precision | Gold Recall | Gold F1 | 평균 폭 |
|---|---:|---:|---:|---:|---:|
| Top-1 | 80.71% | **80.71%** | 80.52% | **80.62%** | **1.00** |
| Top-3 | 94.76% | 59.38% | 94.77% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 98.10% | 70.54% | 1.79 |
| Global $\epsilon=.10$ | 97.14% | 50.18% | 97.15% | 66.18% | 1.94 |
| Relative-loss $\epsilon=.25$ | 83.81% | 74.26% | 83.61% | 78.66% | 1.13 |
| Always BADP Top-3 $\delta=.01$ | **97.86%** | 55.30% | **97.86%** | 70.67% | 1.77 |
| 무가지치기 | 100% | 46.67% | 100% | 63.64% | 2.15 |

Always BADP Top-3는 Top-3가 놓친 recoverable query 13개를 추가로 보존했고 반대 방향 사례는 0개였다. 다만 이 rule은 앞선 ablation을 본 뒤 도입했으므로 통계값은 탐색적으로만 해석한다.

### 9.2 고분기 구간

후보 경로가 5개 이상인 recoverable query 32개에서 결과는 다음과 같다.

| 정책 | Survival | Gold Precision | Gold F1 | 평균 폭 |
|---|---:|---:|---:|---:|
| Top-3 | 37.50% | 12.50% | 18.75% | 3.00 |
| Top-5 | 75.00% | **15.00%** | 25.00% | 5.00 |
| Global $\epsilon=.10$ | **96.88%** | 11.52% | 20.60% | 8.41 |
| Always BADP Top-3 $\delta=.01$ | 78.13% | 14.97% | **25.13%** | 5.22 |
| Always BADP Top-5 $\delta=.01$ | 84.38% | 13.78% | 23.68% | 6.13 |
| 무가지치기 | 100% | 10.26% | 18.61% | 9.75 |

이 결과는 **더 많이 보존하면 survival은 오르지만 precision과 비용이 악화될 수 있음**을 명확히 보여준다.

### 9.3 WN18RR iterative pilot

10질의 초기 반복 탐색에서는 다음 결과가 관찰되었다.

| 정책 | Search Success | Pruning Regret | 평균 폭 |
|---|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 |
| Top-5 | 60% | 40% | 3.88 |
| Global $\epsilon=.05$ | 40% | 60% | 2.65 |
| Global $\epsilon=.10$ | 40% | 60% | 3.62 |
| Relative-loss $\epsilon=.50$ | **70%** | **30%** | 5.97 |

전역 가산 점수대가 frozen diagnostic과 달리 iterative search에서 실패했고, relative-loss는 성공률을 높였지만 훨씬 큰 폭을 사용하였다.

20질의 budgeted 실험에서는 Top-3 50%, Top-5 55%, Always BADP Top-5 $\delta=.010$ 60%, $\delta=.050$ 65%의 search success를 보였다. 그러나 BADP의 성능 향상은 더 큰 width와 expansion을 사용했기 때문에 항상-on 방식 자체를 최종 제안으로 확정하기 어려웠다.

### 9.4 WebQSP 3질의 연결 검증

실제 WebQSP 질문을 이용한 첫 성공 연결에서는 다음과 같은 패턴이 관찰되었다.

| 정책 | Search Success | Hit@1 | 검색 F1 | 평균 폭 |
|---|---:|---:|---:|---:|
| Top-3 | 66.67% | 33.33% | **20.63%** | **3.00** |
| Top-5 | 66.67% | 33.33% | 13.47% | 5.00 |
| Global $\epsilon=.10$ | 33.33% | 33.33% | 11.11% | 4.33 |
| Always BADP Top-3 $\delta=.005$ | 66.67% | 33.33% | 16.93% | 3.83 |
| Always BADP Top-5 $\delta=.010$ | 66.67% | 33.33% | 10.83% | 6.50 |

표본이 3개이므로 성능 우월성을 주장할 수 없다. 다만 **always-on BADP가 정답을 추가 복구하지 않으면서 width만 증가할 수 있음**을 확인했고, 이 관찰이 Conditional BADP 설계의 직접적인 계기가 되었다.

### 9.5 Conditional BADP 확대 실험

현재 다음 두 실험을 분리 수행한다.

1. WN18RR 50질의 반복 탐색
2. WebQSP 20질의 실제 질문 탐색

이 절의 최종 수치는 workflow와 결과 artifact가 검증된 뒤에만 추가한다. 구현 오류로 중단된 실행은 성능값으로 집계하지 않는다.

---

## 10. 논의

### 10.1 본 연구의 핵심은 Rashomon 자체가 아니다

초기 연구는 Rashomon Worlds에서 출발했지만 현재 결과는 특정 possible-world 표현을 고집할 필요가 없음을 보여준다. 핵심은 **조기 단일 선택이 후속 추론 가능성을 제거할 수 있다는 문제**이다.

### 10.2 온톨로지의 역할

불완전한 온톨로지에서는 multi-hop 관계를 모두 hard rule로 정의할 수 없다. 따라서 semantic relation prediction과 logical consistency filtering을 분리하는 것이 타당하다. 그러나 현재 논문은 관계 예측 자체를 최종 기여로 삼지 않고, 그보다 앞선 검색 단계에서 후보가 소실되는 pruning 문제에 초점을 둔다.

### 10.3 branching과 margin

현재 가장 강한 관찰은 branching이 증가할수록 fixed Top-K survival이 크게 악화된다는 것이다. 반면 작은 score margin이 독립적으로 pruning failure를 유발하는지는 아직 충분히 증명되지 않았다. Conditional BADP의 핵심 검증은 이 부분이다.

### 10.4 왜 Conditional인가

Always-on BADP는 경계 주변 후보를 보존한다는 점에서는 합리적이지만, 경계가 이미 명확한 query에서도 추가 후보를 유지할 수 있다. Conditional BADP는 **추가 계산을 정당화할 위험 신호가 있을 때만 예산을 사용한다**는 점에서 한 단계 더 제한적인 설계이다.

---

## 11. 구현 및 결과 검증 원칙

연구 과정에서 scorer input, API transport accounting, analyzer eligibility 등 구현 오류가 발견되었다. 따라서 다음 원칙을 적용한다.

1. 수정 이전 실행의 높은 정확도를 최종 표에 재사용하지 않는다.
2. provenance용 metadata가 semantic scorer 입력에 섞인 자연어 MAGIC 결과는 최종 근거에서 제외한다.
3. transport retry와 logical call accounting 수정 전 비용값은 사용하지 않는다.
4. analyzer eligibility 수정 전 compute-matched 비교는 최종 통계로 사용하지 않는다.
5. workflow 출력 표시 오류와 실제 산출물 오류를 구분한다.
6. 외부 골드가 존재하는 경우 scorer와 독립적인 gold provenance를 우선한다.
7. post-hoc parameter 선택 결과는 탐색적 결과로 표시한다.
8. 최종 test에서는 development set에서 $\tau$와 $\delta$를 고정한다.

---

## 12. 한계

첫째, MAGIC은 conflict preservation 분석에 적합하지만 일반 KGQA end-task와 동일하지 않다. 둘째, WN18RR은 pruning mechanics를 분석하기 좋은 통제 환경이지만 자연어 질문 응답 성능을 직접 의미하지 않는다. 셋째, 현재 WebQSP 연결은 Wikidata를 사용하므로 Freebase 기반 ToG의 공개 성능과 직접 비교할 수 없다. 넷째, DeBERTa는 scorer의 한 구현일 뿐이며 scorer 교체에 대한 robustness 검증이 추가로 필요하다. 다섯째, Conditional BADP의 $\tau$와 $\delta$는 개발 집합에서 동결하는 절차가 완료되어야 최종 우월성을 주장할 수 있다.

---

## 13. 결론

본 연구는 다중 홉 지식그래프 추론의 가지치기 문제를 **얼마나 많이 남길 것인가**가 아니라 **언제 고정 순위 경계를 신뢰할 수 있는가**의 문제로 재정의한다.

고정 Top-K는 효율적이지만 경계가 불확실한 상황에서도 동일하게 비가역적 제거를 수행한다. 반대로 모든 near-optimal 후보를 항상 보존하면 survival은 높아질 수 있으나 noise와 비용이 증가한다. 이를 조정하기 위해 본 연구는 `K/K+1` boundary margin을 위험 신호로 사용하고, 위험이 감지된 경우에만 경계 인접 후보를 추가 유지하는 Conditional BADP를 제안한다.

현재까지의 결과는 다음 세 사실을 지지한다.

1. pruning 이전에 존재하던 유효 evidence가 fixed Top-K에 의해 실제로 소실될 수 있다.
2. 이 손실은 특히 branching이 큰 구간에서 증가한다.
3. always-on preservation은 성능 향상과 함께 비용·noise 증가를 초래할 수 있으므로 조건부 보존이 필요하다.

최종 검증의 핵심은 다음이다.

$$
\boxed{
\text{경계 위험을 감지하고}
\rightarrow
\text{필요한 순간에만 보존을 늘리며}
\rightarrow
\text{성공·유효성·비용을 함께 최적화한다}
}
$$

즉 본 연구의 최종 원칙은 다음과 같다.

> **Preserve when the boundary is uncertain; otherwise prune normally.**
