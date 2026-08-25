# 선행 실험과 연구 문제의 발전 과정

## 1. 문서 목적

본 문서는 제안 방법이 어떤 연구적 고민과 실패를 거쳐 도출되었는지를 정리한다. 단순한 개발 이력이나 성공 결과의 나열이 아니라, 각 단계에서 **무엇을 문제로 보았고, 어떤 가설을 세웠으며, 실제 실험 결과 때문에 연구 질문이 어떻게 바뀌었는지**를 기록한다.

또한 과거 실험 중 구현 오류가 확인된 실행은 최종 성능 근거에서 제외한다. 특히 자연어 MAGIC 실험은 이후 `scorer input`, provenance metadata, retry/accounting, analyzer eligibility 등이 수정되었으므로 수정 이전의 수치를 최종 성능으로 사용하지 않는다. 본 문서에서 수치를 제시하는 경우 현재 결과 파일 또는 수정 이후 검증된 실행을 기준으로 한다.

연구의 전체 흐름은 다음과 같다.

$$
\text{상충 주장 해결}
\rightarrow
\text{복수 해석 보존}
\rightarrow
\text{온톨로지 불완전성 문제}
\rightarrow
\text{관계 후보 예측}
\rightarrow
\text{의미 점수화}
\rightarrow
\text{가지치기 손실 발견}
\rightarrow
\text{경계 인식 보존}
\rightarrow
\text{조건부 BADP}
$$

현재 논문의 중심은 최종 진실 판정 자체가 아니라, **후속 추론에 필요한 유효 경로를 조기에 소실하지 않는 가지치기 정책**이다.

---

## 2. 출발점: Rashomon Worlds와 Tableau를 이용한 상충 해결

### 2.1 초기 연구 질문

초기에는 다음 문제를 해결하려 하였다.

> 다중 홉 경로에서 서로 다른 설명이나 주장이 동시에 존재할 때 하나의 설명을 즉시 선택하지 않고 여러 가능한 설명을 유지한 뒤, 온톨로지 제약과 Tableau를 이용해 논리적으로 불가능한 설명을 제거할 수 있는가?

초기 구조는 다음과 같았다.

```text
질의 / 주장
  ↓
다중 홉 경로 탐색
  ↓
복수의 설명 후보
  ↓
Rashomon / Possible Worlds
  ↓
Ontology constraints
  ↓
Tableau consistency checking
  ↓
일관된 world만 유지
  ↓
최종 설명 또는 주장
```

핵심 아이디어는 `Preserve before Resolve`, 즉 **판정 전에 대안을 보존한다**는 것이었다.

### 2.2 통제된 Tableau 실험에서 얻은 첫 번째 관찰

초기 통제 실험에서는 병합된 ABox보다 관점별로 명제를 분리했을 때 모순의 발생 위치를 더 정확히 구분할 수 있었다. 그러나 이 결과는 자연어 일반화 성능이 아니라 **의도적으로 구성된 논리 규칙에 대해 reasoner가 올바르게 작동하는지 확인한 단위 검증**이었다.

따라서 이 단계에서 얻은 핵심은 높은 정확도 자체가 아니라 다음이었다.

> 여러 설명을 하나로 합치기보다 서로 분리해 유지하면 모순의 범위와 설명 provenance를 보존할 수 있다.

이는 이후 복수 경로 보존이라는 연구 방향의 출발점이 되었다.

---

## 3. 첫 번째 한계: 실제 온톨로지는 완전하지 않다

### 3.1 문제 인식

통제 실험에서는 `inverse`, `symmetric`, `disjoint`, `exclusive` 등의 관계가 명시적으로 정의되어 있었다. 그러나 실제 KG나 자연어 데이터에서는 필요한 관계 의미가 온톨로지에 모두 들어 있지 않다.

예를 들어 관찰된 그래프가 다음과 같다고 하자.

$$
h \xrightarrow{r_1} e_1 \xrightarrow{r_2} e_2 \xrightarrow{r_3} t
$$

우리가 알고 싶은 직접 관계가

$$
(h, ?, t)
$$

라면, Tableau는 `?`에 들어갈 의미를 스스로 만들어 주지 않는다. 온톨로지에 합성 관계나 배타 제약이 정의되어 있지 않으면 다음 두 문제를 해결할 수 없다.

1. 경로가 존재한다는 사실만으로 `h`와 `t` 사이의 의미 관계를 알 수 없음
2. 두 경로가 의미적으로 상충하더라도 이를 논리적 contradiction으로 변환할 규칙이 없을 수 있음

즉 다음을 구분해야 했다.

$$
\text{Graph Reachability}
\neq
\text{Semantic Relation}
\neq
\text{Logical Contradiction}
$$

### 3.2 MAGIC에서 드러난 온톨로지 불완전성

MAGIC 다중 홉 실험에서는 경로 자체는 상당 부분 찾을 수 있었지만 hard ontology와 Tableau만으로 의미적 상충을 직접 검증하기 어려웠다. 대표적인 검증 실행에서 다중 홉 양방향 경로 coverage는 68.03%였지만 온톨로지/Tableau 기반 conflict detection은 5.44%였다.

이 차이는 다음 결론으로 이어졌다.

> 경로를 찾았다고 해서 그 경로의 의미적 관계를 온톨로지가 자동으로 알고 있는 것은 아니다.

따라서 연구는 단순한 `ontology lookup`에서 **불완전한 온톨로지의 누락 관계를 후보로 예측하고, 예측된 관계를 온톨로지가 후속 검증하는 구조**로 이동하였다.

---

## 4. 누락·모호 관계를 예측하려는 시도: Multi-hop Relation Completion

### 4.1 연구 질문의 변화

온톨로지에 관계가 없다고 추론을 중단하는 대신 다음 문제를 다루었다.

> 관찰된 다중 홉 경로를 바탕으로 직접 관계의 후보를 여러 개 예측하고, 온톨로지와 Tableau는 그 후보 중 논리적으로 불가능한 것만 제거할 수 있는가?

이를 다음과 같이 정식화하였다.

관찰 그래프가 주어졌을 때

$$
(h, ?, t)
$$

에 대한 관계 후보를

$$
\mathcal{R}(h,t)=\{r_1,r_2,\ldots,r_m\}
$$

으로 생성한다.

각 관계 후보와 경로의 조합에 의미 점수

$$
s_\theta(p,r) \in [0,1]
$$

을 부여하고, 여러 근접 후보를 가능한 world로 유지한다.

$$
W_{p,r}=G_{obs}\cup\{(h,r,t)\}
$$

그 뒤 온톨로지 `O`에 대해

$$
SAT(O\cup W_{p,r})
$$

를 검사하여 논리적으로 불가능한 world를 제거하는 구조였다.

### 4.2 구현으로 이어진 내용

이 아이디어는 이후 `multihop_completion.py`에 다음 구성으로 구현되었다.

- `RelationCandidate`
- `RelationWorld`
- `CompletionResult`
- near-optimal relation candidate 보존
- 후보 관계별 world 생성
- Ontology + Tableau SAT filtering
- surviving world의 relation marginal 계산

이 시점의 연구 관점은 다음과 같았다.

```text
불완전한 온톨로지
   ↓
관계를 못 찾음
   ↓
추론 종료  X

불완전한 온톨로지
   ↓
다중 홉 경로로 관계 후보 생성
   ↓
Semantic scorer로 plausibility 계산
   ↓
여러 후보 보존
   ↓
Ontology/Tableau는 불가능한 후보 제거
```

즉 **온톨로지는 관계 생성기가 아니라 제약 검증기**로 역할을 재정의하였다.

### 4.3 이 시도가 현재 논문과 연결되는 이유

이 구조에서 중요한 문제가 새로 나타났다. 관계 후보를 잘 생성해도 후보 선택 단계에서 정답 후보를 먼저 제거하면 Tableau는 아무것도 검증할 수 없다.

따라서 다음 관계가 명확해졌다.

$$
\text{후보 생성 성공}
\not\Rightarrow
\text{최종 추론 성공}
$$

그리고 연구의 병목은 점차 **관계 예측 자체보다 후보 보존과 가지치기**로 이동하였다.

---

## 5. DAFNA-EA: 후보가 존재하는 것과 정답을 고르는 것은 다르다

DAFNA-EA Books / AuthorsNamesList 100개 골드 subset을 이용한 가능세계 실험에서는 후보 생성 단계가 정답 world를 93% 포함했지만 최종 exact selection은 최고 62% 수준이었다.

대표 결과는 다음과 같다.

| 방법 | Exact-set 정확도 | 저자 F1 |
|---|---:|---:|
| 가능세계 균등 | 58% | 80.38% |
| hard commit reliability | 61% | 84.04% |
| 가능세계 marginal | **62%** | **84.13%** |
| 기존 atomic resolution | 61% | 82.88% |

이 실험에서 얻은 가장 중요한 결론은 62%라는 숫자 자체가 아니다.

$$
\text{Gold candidate coverage}=93\%
$$

임에도

$$
\text{Exact selection}=62\%
$$

였다는 점이다.

즉 **좋은 후보를 생성하는 문제와 좋은 후보를 선택하는 문제는 분리해야 한다.** 이후의 연구에서 scorer와 pruning을 별도 실험 변수로 분해한 이유가 여기에 있다.

---

## 6. MAGIC Possible Worlds: 후보 보존 후에도 점수화가 병목

MAGIC 588개 행, 1,056개 query를 이용한 structured possible-world 실험에서는 weak lexical scorer가 후보 world의 의미를 충분히 구분하지 못했다.

외부 골드 경로가 후보 중 존재하는지를 보는 existential coverage와 실제 weighted selection 사이에 큰 차이가 관찰되었다. 이 결과로 다음 질문이 생겼다.

> 가능한 설명을 많이 보존하는 것만으로 충분한가, 아니면 의미적으로 더 나은 점수기가 필요한가?

이에 weak lexical prior를 semantic NLI scorer로 교체하였다.

---

## 7. DeBERTa 의미 점수기: 의미 점수화의 유효성 확인

`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`를 사용한 이후 동일 candidate generation에서 다음 개선이 확인되었다.

| 지표 | weak lexical | DeBERTa | 개선 |
|---|---:|---:|---:|
| 행 단위 conflict recall | 22.79% | **41.50%** | **+18.71%p** |
| query conflict recall | 16.86% | **31.53%** | **+14.68%p** |
| structured exact localization | 7.14% | **15.48%** | **+8.33%p** |

이 결과는 현재도 다음 의미로 사용한다.

> 동일한 후보가 주어졌을 때 의미 기반 NLI scorer가 약한 lexical scorer보다 유용한 경로를 더 잘 구분한다.

다만 DeBERTa 자체를 논문의 novelty로 보지 않는다. 이후 실험에서는 scorer를 고정하고 pruning operator만 변경하였다.

### 7.1 scorer 입력 오류에서 얻은 교훈

자연어 MAGIC 실험을 진행하는 과정에서 scorer 입력에 다음과 같은 provenance용 metadata가 포함되어 있었다.

```text
[source=context1, sentence=...]
[source=context2, sentence=...]
```

이 정보는 proposition의 의미가 아니라 audit metadata인데, NLI 입력에 들어가면서 동일하거나 유사한 사실도 인위적으로 다른 문장처럼 보이게 할 수 있었다. 이후 scorer 입력을 자연어 triple만 사용하도록 수정하였다.

따라서 **수정 전 자연어 MAGIC 정확도는 최종 성능 근거로 사용하지 않는다.**

또한 이후 transport retry accounting, fixed-call budget, analyzer eligibility도 수정되었다. 이 때문에 코드 수정 이전 실행 결과는 연구 진행 과정의 디버깅 기록으로만 취급하고, 논문의 최종 표에는 재검증된 결과만 넣는 원칙을 세웠다.

---

## 8. 핵심 문제의 이동: 의미 점수기가 좋아도 pruning에서 정답이 사라질 수 있다

DeBERTa를 도입한 뒤에도 성능이 완전히 해결되지 않았다. 여기서 연구 질문이 다시 바뀌었다.

초기 질문:

```text
어떤 relation/world가 맞는가?
```

변경된 질문:

```text
맞는 relation/world가 후보에 있었는데
pruning에서 먼저 사라지는 것은 아닌가?
```

이 변화가 현재 논문의 직접적인 출발점이다.

---

## 9. WN18RR Frozen Candidate 실험: 가지치기 자체의 효과 분리

50개 질의와 11개 relation candidate를 고정하고 scorer도 고정한 뒤 pruning 정책만 바꿨다.

| 정책 | 골드 관계 생존율 | 가지치기 손실률 | 평균 보존 수 |
|---|---:|---:|---:|
| Top-1 | 16% | 84% | 1.00 |
| Top-3 | 32% | 68% | 3.00 |
| Top-5 | 40% | 60% | 5.00 |
| 전역 점수대 $\epsilon=.05$ | 42% | 58% | 3.82 |
| 전역 점수대 $\epsilon=.10$ | 58% | 42% | 5.08 |
| 무가지치기 | 100% | 0% | 11.00 |

이 단계에서는 전역 near-optimal 보존이 유망해 보였다. 그러나 후보를 한 번만 자르는 frozen diagnostic이므로 실제 반복 탐색에서는 결과가 달라질 수 있었다.

---

## 10. 반복 탐색에서 전역 Rashomon 점수대가 실패

실제 다중 홉 탐색에서 매 단계 후보를 확장하고 다시 pruning하는 실험에서는 전역 가산 점수대가 Top-K보다 나쁜 경우가 나타났다.

10질의 pilot:

| 정책 | 탐색 성공률 | query pruning regret | 평균 활성 폭 |
|---|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 |
| Top-5 | 60% | 40% | 3.88 |
| 전역 $\epsilon=.05$ | 40% | 60% | 2.65 |
| 전역 $\epsilon=.10$ | 40% | 60% | 3.62 |

이 실험으로 다음 가설을 폐기하였다.

> 전역 Rashomon score band가 일반적으로 Top-K보다 우수하다.

점수의 절대 스케일에 따라 동일 `epsilon`이 지나치게 좁거나 넓어질 수 있었기 때문이다.

---

## 11. 상대 손실 기준: scale 문제를 줄였지만 비용이 증가

전역 절대 점수차 대신 loss 비율을 이용하였다.

$$
L(p)=1-s(p)
$$

$$
R_{\epsilon}^{loss}
=
\left\{p \mid L(p)\le(1+\epsilon)L^*\right\}
$$

10질의 pilot에서 relative-loss `0.50`은 70% 탐색 성공, 30% pruning regret을 기록하여 Top-3/Top-5보다 높았다. 그러나 평균 활성 폭도 약 5.97까지 증가하였다.

즉 다음 평가 원칙을 확정하였다.

$$
\text{좋은 pruning}
\neq
\text{많이 보존하는 pruning}
$$

대신

$$
\text{Search Success}
\times
\text{Retained-set Validity}
\times
\text{Search Cost}
$$

를 함께 평가해야 한다.

---

## 12. MAGIC 외부 골드 분석: branching이 커질수록 Top-K 손실 증가

MAGIC에서 DeBERTa 점수와 독립적인 `perturb_triplet` provenance를 외부 골드로 사용하여 pruning 후 conflict evidence가 살아남는지 측정하였다.

전체 1,056 query 중 candidate path가 존재한 query는 618개였고, pruning 이전부터 외부 골드 conflict path가 존재했던 recoverable query는 420개였다.

### 12.1 전체 recoverable query

| 정책 | conflict path 생존율 | 골드 precision | 골드 F1 | 평균 폭 |
|---|---:|---:|---:|---:|
| Top-1 | 80.71% | **80.71%** | **80.62%** | 1.00 |
| Top-3 | 94.76% | 59.38% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 70.54% | 1.79 |
| 전역 $\epsilon=.10$ | 97.14% | 50.18% | 66.18% | 1.94 |
| Relative-loss $\epsilon=.25$ | 83.81% | 74.26% | 78.66% | 1.13 |
| Boundary Top-3 $\delta=.01$ | **97.86%** | 55.30% | 70.67% | 1.77 |
| 무가지치기 | 100% | 46.67% | 63.64% | 2.15 |

여기서 중요한 점은 `100% survival`인 무가지치기가 가장 좋은 정책이 아니라는 것이다. non-gold path도 함께 증가하여 precision/F1이 감소한다.

### 12.2 고분기 영역

후보 경로 수가 5개 이상인 recoverable query 32개에서는:

| 정책 | conflict path 생존율 |
|---|---:|
| Top-3 | 37.50% |
| Top-5 | 75.00% |
| 전역 $\epsilon=.10$ | 96.88% |
| Boundary Top-5 $\delta=.01$ | 84.38% |
| 무가지치기 | 100% |

Top-K의 손실이 전체 평균보다 고분기 영역에서 훨씬 커졌다.

따라서 현재까지 가장 강한 구조적 요인은 **branching factor**이다. score margin의 독립 효과는 아직 branching과 분리해 확정하지 않았다.

---

## 13. BADP: 최고점이 아니라 실제 Top-K 경계를 본다

전역 Rashomon 방식의 문제는 최고점 $s^*$를 중심으로 전체 후보를 판단한다는 점이다. 하지만 실제로 제거되는 지점은 최고점이 아니라 $K$번째와 $K+1$번째 사이이다.

후보 점수를 내림차순으로 정렬하면:

$$
s_{(1)}\ge s_{(2)}\ge\cdots\ge s_{(|C|)}
$$

기본 BADP는 다음과 같이 정의하였다.

$$
B_{K,\delta}(C)
=
T_K(C)
\cup
\left\{p_{(j)}\mid j>K,\;s_{(K)}-s_{(j)}\le\delta\right\}
$$

MAGIC에서 Boundary Top-3는 fixed Top-3가 잃은 13개 recoverable conflict query를 추가로 살렸고 반대 방향은 0개였다. 다만 이 값은 boundary rule을 앞선 실험 결과를 보고 도입한 뒤 얻은 탐색적 결과이므로 confirmatory result로 과도하게 해석하지 않는다.

---

## 14. WebQSP 실제 질의 연결에서 나타난 새로운 문제

ToG 공식 WebQSP 데이터의 실제 질문을 사용하고 `qid_topic_entity`를 통해 Wikidata entity statement를 탐색하는 소규모 연결 실험을 수행하였다.

첫 실행에서는 Wikidata 공개 API의 429 rate limit가 발생하였다. 이후 호출 간격과 후보 폭을 조절하여 `n=3` 연결 검증을 완료하였다.

3질의에서는 Top-3, Top-5 및 BADP의 search success가 모두 66.67%였고, BADP는 추가 정답을 복구하지 못하면서 폭과 확장량만 증가하였다.

이 결과는 성능 비교용 표본으로는 너무 작지만 중요한 방법론적 경고를 제공하였다.

> BADP 역시 모든 query에서 항상 켜면 불필요하게 탐색 폭을 증가시킬 수 있다.

따라서 현재 방법은 **항상 동작하는 BADP에서 조건부 BADP로 한 단계 더 변경**한다.

---

## 15. 현재 제안 방법: 조건부 BADP

### 15.1 경계 위험도

Top-K 경계의 즉시 margin을 다음과 같이 정의한다.

$$
\Delta_K=s_{(K)}-s_{(K+1)}
$$

`Delta_K`가 작다는 것은 scorer가 $K$번째와 $K+1$번째 후보를 명확하게 구분하지 못하고 있음을 의미한다.

### 15.2 조건부 발동

조건부 BADP는 다음과 같이 정의한다.

$$
P_{k+1}^{CBADP}
=
\begin{cases}
B_{K,\delta}(C_{k+1}), & \Delta_K\le\tau \\
T_K(C_{k+1}), & \Delta_K>\tau
\end{cases}
$$

여기서:

- $K$: 기본 Top-K 폭
- $\tau$: BADP를 발동할 경계 불확실성 임계값
- $\delta$: 발동 후 K번째 점수 아래로 추가 보존할 허용 범위

따라서 `tau`와 `delta`의 역할은 다르다.

```text
tau   = 지금 경계가 위험한가?
delta = 위험하다면 얼마나 더 보존할 것인가?
```

이 구조는 BADP가 항상 추가 비용을 쓰는 문제를 줄이고, **경계가 실제로 불확실한 query에만 선택적으로 예산을 사용하는 것**을 목표로 한다.

---

## 16. 현재 검증해야 할 핵심 가설

### H1. 고정 경계 손실

고정 Top-K에서는 pruning 이전에 viable path가 존재해도 rank cutoff 때문에 모두 제거되는 query가 존재한다.

### H2. branching sensitivity

candidate branching이 증가할수록 fixed Top-K의 pruning regret이 증가한다.

### H3. conditional boundary effect

경계 margin이 작은 경우에만 BADP를 적용하면 always-on BADP보다 적은 평균 비용으로 pruning regret을 줄일 수 있다.

이를 직접 검증해야 할 식은 다음이다.

$$
P(PR=1\mid \Delta_K\le\tau)
>
P(PR=1\mid \Delta_K>\tau)
$$

그리고 최종 비교는 다음 세 축으로 수행한다.

$$
\boxed{
\text{Preservation / Success}
\;\times\;
\text{Retained-set Validity}
\;\times\;
\text{Search Cost}
}
$$

---

## 17. 실험 결과를 문서에 반영하는 기준

본 연구에서는 실험 과정에서 구현 오류가 여러 차례 발견되었기 때문에 다음 원칙을 적용한다.

1. **수정 전 실행값은 최종 정확도로 사용하지 않는다.**
2. scorer input에 provenance/audit metadata가 포함된 자연어 MAGIC 결과는 폐기한다.
3. transport retry와 logical call accounting 수정 전 비용 비교는 폐기한다.
4. analyzer eligibility 오류 수정 전 compute-matched 통계는 최종 비교에 사용하지 않는다.
5. workflow output 자체의 표시 오류는 실험 산출물과 구분한다.
6. 외부 골드가 있는 경우 scorer와 독립적인 gold provenance를 우선 사용한다.
7. post-hoc로 선택한 epsilon/delta/tau의 p-value는 탐색적 결과로만 표기한다.
8. 최종 test에서는 development set에서 hyperparameter를 고정한 뒤 재평가한다.

따라서 과거 문서에 기록되었던 높은 숫자를 단순히 유지하지 않고, **어떤 코드와 프로토콜로 얻은 값인지가 검증된 결과만 논문 근거로 남긴다.**

---

## 18. 현재 연구의 핵심 결론

연구는 다음과 같이 변화하였다.

```text
초기:
Rashomon Worlds + Ontology + Tableau로 상충을 해결하자

문제 1:
실제 ontology에는 필요한 relation semantics가 빠져 있다

대응:
multi-hop relation candidate를 예측하고
semantic scorer + Tableau filter를 결합하자

문제 2:
좋은 후보가 있어도 scorer/ranking에서 선택이 어렵다

대응:
DeBERTa semantic scorer로 후보 구분을 개선하자

문제 3:
좋은 후보가 있어도 iterative pruning에서 먼저 사라진다

대응:
Preserve before Resolve,
pruning regret을 측정하자

문제 4:
전역적으로 많이 보존하면 비용과 noise가 커진다

대응:
실제 Top-K 경계만 대상으로 BADP를 적용하자

문제 5:
BADP를 모든 query에서 켜도 불필요한 비용이 생긴다

현재:
경계가 불확실한 경우에만 발동하는 Conditional BADP
```

현재 논문의 중심 주장은 다음과 같다.

> **다중 홉 추론에서 고정 Top-K의 문제는 단순히 K가 작다는 것이 아니라, scorer가 경계를 명확히 구분하지 못하는 상황에서도 동일하게 비가역적 제거를 수행한다는 데 있다. 따라서 경계 위험이 감지될 때에만 선택적으로 가지치기를 지연하는 것이 더 적절한 탐색 원칙이 될 수 있다.**
