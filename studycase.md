# 선행 실험과 연구 문제의 발전 과정

## 1. 문서 목적

본 문서는 현재 제안 중인 **조건부 경계 인식 지연 가지치기(Conditional BADP)**가 어떤 연구적 문제와 실험 결과를 거쳐 도출되었는지를 정리한다. 단순 실행 로그나 개발 이력의 나열이 아니라, 각 단계에서 다음 네 가지를 분리해 기록한다.

1. 어떤 문제를 해결하려 했는가?
2. 어떤 가설과 방법을 사용했는가?
3. 실제 실험에서 무엇이 개선되거나 실패했는가?
4. 그 결과 때문에 다음 연구 질문이 어떻게 바뀌었는가?

연구의 전체 흐름은 다음과 같다.

```text
상충하는 주장과 복수 설명을 해결하고 싶었다
        ↓
Possible Worlds + Tableau로 여러 해석을 보존·검증
        ↓
실제 온톨로지는 필요한 관계 의미를 모두 갖고 있지 않았다
        ↓
다중 홉 경로로 누락 관계 후보를 예측
        ↓
Semantic scorer로 관계·경로 후보를 점수화
        ↓
좋은 후보가 있어도 ranking/pruning에서 먼저 제거되는 문제 발견
        ↓
Pruning Regret 정의
        ↓
Global Rashomon / Relative-loss 보존 실험
        ↓
실제 Top-K 경계를 보는 BADP
        ↓
항상 BADP를 켜면 불필요한 비용이 발생
        ↓
Conditional BADP
```

이 흐름을 한 문장으로 요약하면 다음과 같다.

> **좋은 추론기는 정답을 잘 고르는 것뿐 아니라, 정답이 될 수 있는 경로를 너무 일찍 버리지 않아야 한다.**

---

# 2. 실험 결과 채택 기준

연구 과정에서 scorer 입력, workflow 출력, API transport accounting, analyzer eligibility 등에 구현 오류가 발견된 적이 있기 때문에 모든 수치를 동일하게 취급하지 않는다.

본 문서에서는 다음 기준을 적용한다.

1. 코드 오류가 확인된 실행은 최종 성능 근거에서 제외한다.
2. provenance용 metadata가 semantic scorer 입력에 섞인 자연어 MAGIC 실행은 제외한다.
3. transport retry와 logical-call accounting 수정 전 비용 수치는 최종 비교에서 제외한다.
4. analyzer eligibility 수정 전 compute-matched 결과는 최종 통계로 사용하지 않는다.
5. workflow의 후처리 출력 오류와 실제 평가 계산 오류를 구분한다.
6. 외부 골드가 있는 경우 scorer와 독립적인 gold provenance를 우선 사용한다.
7. post-hoc으로 선택한 파라미터의 결과는 탐색적 결과로 표시한다.
8. 최종 confirmatory 실험에서는 development set에서 파라미터를 고정한 뒤 test에서 변경하지 않는다.

따라서 본 문서의 **검증된 성능 개선** 표에는 코드 오류가 없는 실행만 포함한다.

---

# 3. 출발점: 상충하는 설명을 하나로 너무 빨리 합치지 않기

## 3.1 초기 연구 질문

초기 연구 질문은 다음과 같았다.

> 다중 홉 경로에서 서로 다른 설명이나 주장이 동시에 존재할 때, 하나의 설명을 즉시 선택하지 않고 여러 가능한 설명을 유지한 뒤 논리적으로 불가능한 설명만 제거할 수 있는가?

초기 구조는 다음과 같았다.

```text
질의 / 주장
   ↓
다중 홉 경로 탐색
   ↓
복수 설명 후보
   ↓
Rashomon / Possible Worlds
   ↓
Ontology constraints
   ↓
Tableau consistency checking
   ↓
일관된 world 유지
```

핵심 원칙은 다음이었다.

> **Preserve before Resolve — 판정하기 전에 가능한 설명을 충분히 보존한다.**

---

# 4. 통제된 Ontology / Tableau 실험

## 4.1 왜 먼저 통제 실험을 했는가

자연어 데이터와 실제 지식그래프를 바로 사용하면 다음 실패 원인을 구분하기 어렵다.

- 논리 규칙 자체가 틀렸는가?
- ontology가 불완전한가?
- candidate path가 잘못 생성되었는가?
- scorer가 잘못 ranking했는가?

따라서 먼저 논리 규칙이 명확한 통제 ontology에서 reasoner 동작을 확인하였다.

## 4.2 검증된 결과

80개 통제 사례에서 다음 결과가 확인되었다.

| 방법 | Accuracy | Macro F1 |
|---|---:|---:|
| Vanilla merged Tableau | 75.00% | 66.67% |
| Perspective Tableau | **100.00%** | **100.00%** |
| Rashomon Tableau | **100.00%** | **100.00%** |

즉 perspective를 분리하지 않고 모든 사실을 하나의 ABox로 병합한 방식보다, 출처·관점별 명제를 분리한 Tableau가 더 안정적으로 contradiction scope를 구분했다.

정확도 변화는 다음과 같다.

$$
75.00\% \rightarrow 100.00\%
$$

Macro F1은

$$
66.67\% \rightarrow 100.00\%
$$

으로 개선되었다.

다만 이 결과는 **통제된 ontology rule에 대한 reasoner correctness**를 확인한 것이며 자연어 일반화 성능으로 해석하지 않는다.

## 4.3 설명 coverage 실험

20개 사례에서 각 사례에 2개의 최소 contradiction explanation이 존재하도록 구성했을 때:

| 방법 | 최소 contradiction 설명 coverage |
|---|---:|
| Single-path | 50% |
| Rashomon enumeration | **100%** |

즉 하나의 설명만 고르는 방식은 가능한 설명의 절반만 보존했지만, 여러 후보를 유지한 방식은 두 explanation을 모두 보존했다.

이 결과에서 얻은 첫 번째 중요한 결론은 다음이다.

> Rashomon의 가치가 반드시 최종 class accuracy에 있는 것은 아니며, **후속 설명과 검증에 필요한 대안을 보존하는 데 있을 수 있다.**

---

# 5. 첫 번째 실제 한계: 온톨로지는 완전하지 않다

## 5.1 Graph Reachability와 Semantic Relation은 다르다

실제 KG나 자연어 기반 지식에서는 필요한 relation semantics가 모두 ontology에 정의되어 있지 않다.

예를 들어 다음 경로가 관찰되었다고 하자.

$$
h \xrightarrow{r_1} e_1
\xrightarrow{r_2} e_2
\xrightarrow{r_3} t
$$

그래프 관점에서는 $h$와 $t$가 연결되어 있다. 그러나 실제로 필요한 것이

$$
(h, ?, t)
$$

의 `?`에 해당하는 직접 관계라면, ontology가 이를 자동으로 생성해 주지는 않는다.

따라서 다음 세 개념을 분리해야 했다.

$$
\text{Graph Reachability}
\neq
\text{Semantic Relation}
\neq
\text{Logical Contradiction}
$$

즉:

- 경로가 존재한다는 사실
- 그 경로가 의미하는 관계
- 두 관계가 논리적으로 상충한다는 사실

은 서로 다른 문제이다.

## 5.2 MAGIC에서 확인된 격차

MAGIC의 multi-hop structured 데이터에서 bidirectional candidate path는 상당 부분 발견되었지만 strict ontology/Tableau conflict detection은 매우 낮았다.

| 지표 | 결과 |
|---|---:|
| Multi-hop candidate path coverage | **68.03%** |
| Strict ontology/Tableau contradiction detection | **5.44%** |

이 결과의 의미는 다음과 같다.

> **경로는 찾았지만 그 경로가 의미적으로 무엇을 뜻하는지 ontology만으로는 해석하지 못했다.**

따라서 문제를 단순히 ontology rule을 더 많이 손으로 작성하는 방향으로 해결하지 않고, **누락된 관계 자체를 후보로 예측**하는 방향으로 전환하였다.

---

# 6. 불완전한 온톨로지를 보완하기 위한 Relation Prediction

## 6.1 연구 질문의 변화

새로운 연구 질문은 다음과 같았다.

> 온톨로지에 직접 관계가 정의되어 있지 않다면 다중 홉 경로에서 관계 후보를 여러 개 생성하고, semantic scorer와 ontology constraint를 이용해 후보를 검증할 수 있는가?

관계가 미정인 triple을 다음과 같이 둔다.

$$
(h, ?, t)
$$

가능한 관계 후보 집합을

$$
\mathcal{R}(h,t)
=
\{r_1,r_2,\ldots,r_m\}
$$

으로 생성한다.

각 다중 홉 경로 $p$와 relation candidate $r$에 대해 의미 적합도를 계산한다.

$$
s_\theta(p,r)\in[0,1]
$$

그리고 각 후보를 possible world로 구성한다.

$$
W_{p,r}
=
G_{obs}\cup\{(h,r,t)\}
$$

마지막으로 ontology $O$와 결합하여 논리적으로 가능한지를 확인한다.

$$
SAT(O\cup W_{p,r})
$$

## 6.2 온톨로지의 역할 재정의

이 단계에서 ontology의 역할을 다음과 같이 바꾸었다.

```text
기존 생각
Ontology → 관계 의미를 모두 알고 있음

변경
다중 홉 경로 → 관계 후보 생성
Semantic scorer → 후보 plausibility 계산
Ontology / Tableau → 논리적으로 불가능한 후보 제거
```

즉 ontology를 **관계 생성기(generator)**가 아니라 **논리 제약 검증기(constraint verifier)**로 사용하였다.

이 구조는 `multihop_completion.py`의 relation candidate / relation world 구조로 구현되었다.

## 6.3 이 단계에서 새롭게 발견된 문제

관계 후보를 잘 만들어도 다음 문제가 있었다.

$$
\text{좋은 후보 생성}
\not\Rightarrow
\text{좋은 후보 최종 선택}
$$

그리고 더 근본적으로:

$$
\text{좋은 후보 생성}
\not\Rightarrow
\text{검색 과정에서 끝까지 생존}
$$

즉 이후 연구는 relation prediction 자체보다 **ranking과 pruning에서 좋은 후보가 어떻게 사라지는가**로 이동하기 시작했다.

---

# 7. MAGIC Possible Worlds: 후보 보존과 후보 선택의 분리

## 7.1 데이터

검증된 structured MAGIC 실험에서는:

- 588 rows
- 1,056 query conflicts

를 사용하였다.

이 실험은 자연어 MAGIC 공식 평가가 아니라 structured triplet 기반 진단 실험이다.

## 7.2 Possible Worlds 구성

하나의 경로에 대해 여러 의미 해석이 가능하다면 다음과 같이 여러 hypothesis를 둔다.

$$
H_1:r_1\circ r_2\Rightarrow q
$$

$$
H_2:r_1\circ r_2\Rightarrow\neg q
$$

$$
H_3:\text{unresolved}
$$

각 해석을 별도 world로 유지한다.

$$
W=(C,S,R,D)
$$

여기서:

- $C$: claim 집합
- $S$: source/provenance
- $R$: relation interpretation
- $D$: derivation/proof

## 7.3 검증 결과

| Variant | Row conflict recall | Query conflict recall | Gold-world query recall | Structured exact LOC |
|---|---:|---:|---:|---:|
| Static Tableau | 5.44% | 4.45% | — | — |
| Early-commit single world | 29.93% | 22.63% | — | — |
| Possible-world retention | — | — | **39.39%** | **29.42%** |
| Weakly weighted worlds | 22.79% | 16.86% | — | 7.14% |

평균적으로:

- query당 candidate paths: 1.46
- query당 worlds: 4.10
- row당 worlds: 7.36

였다.

## 7.4 핵심 해석

다음 두 수치의 차이가 중요했다.

$$
GoldWorldRecall=39.39\%
$$

$$
WeakWeightedExactLOC=7.14\%
$$

즉 **정답 가능성이 있는 world를 후보 안에 넣는 것**과 **그중 정답 world를 올바르게 선택하는 것**은 다른 문제였다.

이 결과 때문에 이후 scorer를 독립 실험 변수로 분리하였다.

---

# 8. Semantic Scorer: 후보 ranking의 개선

## 8.1 DeBERTa 도입

weak lexical score 대신 다음 NLI 모델을 semantic scorer로 사용하였다.

`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`

중요한 점은 DeBERTa가 relation을 새로 생성하는 것이 아니라 **동일한 candidate interpretation 중 의미적으로 더 적합한 후보를 점수화하는 역할**을 했다는 것이다.

## 8.2 검증된 structured 결과

| 지표 | Weak lexical | DeBERTa | 개선 |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71%p** |
| Query conflict recall | 16.86% | **31.53%** | **+14.67%p** |
| Structured exact localization | 7.14% | **15.48%** | **+8.34%p** |

이 결과는 동일 candidate generation에서 semantic scorer가 lexical scorer보다 의미적으로 유용한 후보를 더 잘 ranking할 수 있음을 보여준다.

다만 이 수치는 structured MAGIC 진단이며 공식 natural-language MAGIC 성능과 동일하지 않다.

## 8.3 제외한 자연어 실행

초기 natural-language scorer 입력 중 다음 metadata가 proposition과 함께 입력된 실행이 있었다.

```text
[source=context1, sentence=...]
[source=context2, sentence=...]
```

이 정보는 semantic proposition이 아니라 audit metadata이다. 이후 이를 scorer input에서 분리하였다.

따라서 **이 수정 이전 자연어 MAGIC 정확도는 최종 성능 근거에서 제외한다.**

---

# 9. DAFNA-EA Books: 후보가 존재하는 것과 truth를 선택하는 것

## 9.1 연구 질문

MAGIC이 multi-hop relation interpretation을 다뤘다면 DAFNA-EA Books는 다음 문제를 다뤘다.

> 여러 출처가 동일 책의 저자에 대해 서로 다른 주장을 할 때, 가능한 truth world를 보존한 뒤 가장 타당한 truth를 선택할 수 있는가?

100개 gold books subset에서:

- 1,999 claims
- 227 sources

를 사용하였다.

## 9.2 Gold world coverage

possible-world candidate generation에서 실제 gold truth를 포함하는 world가 존재한 비율은:

$$
93\%
$$

였다.

그러나 최종 exact truth selection은 그보다 훨씬 낮았다.

## 9.3 주요 결과

| 방법 | Exact-set accuracy | Author F1 |
|---|---:|---:|
| Possible-world uniform | 58% | 80.38% |
| Hard commit reliability | 61% | 84.04% |
| Possible-world marginal | **62%** | **84.13%** |
| Prior atomic resolution | 61% | 82.88% |
| TruthFinder | 57% | 66.85% |
| AccuSim | 57% | 66.18% |

Prior atomic 방식과 비교하면 possible-world marginal은:

$$
61\%\rightarrow62\%
$$

으로 exact-set accuracy가 **+1%p** 개선되었고,

$$
82.88\%\rightarrow84.13\%
$$

으로 Author F1이 **+1.25%p** 개선되었다.

## 9.4 핵심 해석

가장 중요한 차이는 다음이다.

$$
Gold\ Candidate\ Coverage=93\%
$$

인데도

$$
Best\ Exact\ Selection=62\%
$$

였다.

즉 좋은 world가 후보 안에 존재해도 ranking/calibration이 충분하지 않으면 최종 truth selection은 실패한다.

이 결과는 이후 연구에서 **candidate generation, scoring, pruning, final resolution을 분리해서 평가해야 한다**는 원칙으로 이어졌다.

---

# 10. 연구 초점의 이동: 좋은 후보가 pruning에서 먼저 사라질 수 있다

Semantic scorer를 개선한 이후에도 모든 문제가 해결되지는 않았다.

여기서 연구 질문이 다음처럼 바뀌었다.

```text
기존:
어떤 world / relation이 맞는가?

변경:
맞는 world / relation이 후보에 있었는데
검색 중간 pruning에서 먼저 사라지는 것은 아닌가?
```

다중 홉 검색에서는 한번 제거된 경로를 다음 단계에서 다시 확장할 수 없다.

따라서 pruning은 단순한 효율화 연산이 아니라 **비가역적인 정보 손실 지점**이다.

---

# 11. Pruning Regret 정의

질의 $i$의 깊이 $k$에서 pruning 직전 후보 집합을 $C_{i,k}$, pruning 후 집합을 $P_{i,k}$라 한다.

부분 경로 $p$가 남은 hop budget 내에서 목표 또는 gold evidence에 도달 가능하면:

$$
v_k(p)=1
$$

로 정의한다.

Pruning 직전에는 viable path가 존재했지만 pruning 이후 하나도 남지 않으면 다음과 같이 정의한다.

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

질의 수준에서는:

$$
QPR_i=\max_k PR_{i,k}
$$

데이터셋 전체에서는:

$$
QPR=\frac{1}{N}\sum_{i=1}^{N}QPR_i
$$

를 사용한다.

이 지표의 목적은 **최종 실패 중 pruning 자체가 유발한 실패만 분리해서 측정**하는 것이다.

---

# 12. WN18RR Frozen Candidate: near-optimal 보존 가능성 확인

## 12.1 실험 목적

먼저 candidate set과 scorer를 고정한 뒤 pruning operator만 변경하여 pruning 자체의 영향을 분리하였다.

50개 query에서 11개 relation candidate를 사용하였다.

## 12.2 검증된 결과

| 정책 | Gold relation survival | Pruning loss | 평균 보존 수 |
|---|---:|---:|---:|
| Top-1 | 16% | 84% | 1.00 |
| Top-3 | 32% | 68% | 3.00 |
| Top-5 | 40% | 60% | 5.00 |
| Global band $\epsilon=.05$ | 42% | 58% | 3.82 |
| Global band $\epsilon=.10$ | **58%** | **42%** | **5.08** |
| No pruning | 100% | 0% | 11.00 |

가장 눈에 띄는 결과는 Top-5와 global $\epsilon=.10$ 비교였다.

$$
40\%\rightarrow58\%
$$

즉 survival이 **+18%p** 개선되었는데 평균 보존 수는:

$$
5.00\rightarrow5.08
$$

에 불과했다.

이 결과만 보면 near-optimal candidate preservation이 매우 유망해 보였다.

하지만 이 실험은 후보를 한 번만 잘라내는 **frozen diagnostic**이었다.

---

# 13. Iterative Search: 전역 Rashomon band의 실패

실제 다중 홉 검색에서는 다음 단계 후보가 이전 pruning 결과에 의존한다.

따라서 같은 방법을 iterative 2–4 hop search에 적용하였다.

10-query pilot 결과:

| 정책 | Search Success | Query Pruning Regret | 평균 활성 폭 |
|---|---:|---:|---:|
| Top-3 | **60%** | 40% | 2.67 |
| Top-5 | **60%** | 40% | 3.88 |
| Global $\epsilon=.05$ | 40% | 60% | 2.65 |
| Global $\epsilon=.10$ | 40% | 60% | 3.62 |

즉 frozen 실험에서 유망했던 global band가 실제 iterative search에서는 Top-K보다 낮아졌다.

이 결과로 다음 가설은 폐기하였다.

> **Global Rashomon score band가 일반적으로 Top-K보다 우수하다.**

문제는 최고 점수 $s^*$와의 절대 차이가 scorer scale에 민감하다는 점이었다.

---

# 14. Relative-loss: score scale 문제 완화

절대 점수차 대신 loss 비율을 사용하였다.

$$
L(p,q)=1-s_\theta(p,q)
$$

최소 loss를 $L^*$라 하면:

$$
R_{\epsilon}^{loss}(C)
=
\left\{
p\mid L(p,q)\le(1+\epsilon)L^*
\right\}
$$

10-query pilot에서 relative-loss $\epsilon=.50$은:

$$
60\%\rightarrow70\%
$$

으로 Top-3/Top-5 대비 search success가 **+10%p** 개선되었다.

그러나 평균 활성 폭은 약 5.97까지 증가했다.

즉 성능이 개선되었지만 비용도 증가하였다.

이 결과로 평가 기준을 다음처럼 변경하였다.

$$
\boxed{
\text{Success / Preservation}
\times
\text{Retained-set Validity}
\times
\text{Search Cost}
}
$$

---

# 15. MAGIC External Gold: branching이 fixed Top-K의 핵심 위험 요인

## 15.1 scorer와 독립적인 gold 사용

MAGIC에서는 `perturb_triplet` provenance를 external gold로 사용하였다.

전체:

- 1,056 queries
- candidate path가 존재: 618
- pruning 전에 gold conflict path가 존재하는 recoverable queries: 420

## 15.2 전체 recoverable query

| 정책 | Conflict path survival | Gold Precision | Gold F1 | 평균 폭 |
|---|---:|---:|---:|---:|
| Top-1 | 80.71% | **80.71%** | **80.62%** | 1.00 |
| Top-3 | 94.76% | 59.38% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 70.54% | 1.79 |
| Global $\epsilon=.10$ | 97.14% | 50.18% | 66.18% | 1.94 |
| Relative-loss $\epsilon=.25$ | 83.81% | 74.26% | 78.66% | 1.13 |
| Boundary Top-3 | **97.86%** | 55.30% | 70.67% | 1.77 |
| No pruning | 100% | 46.67% | 63.64% | 2.15 |

Boundary Top-3는 Top-3 대비 survival을:

$$
94.76\%\rightarrow97.86\%
$$

으로 **+3.10%p** 개선하였다.

평균 폭은:

$$
1.60\rightarrow1.77
$$

이었다.

## 15.3 고분기 query

후보 경로가 5개 이상인 recoverable query 32개에서는 fixed Top-K의 약점이 훨씬 크게 나타났다.

| 정책 | Conflict path survival |
|---|---:|
| Top-3 | 37.50% |
| Top-5 | 75.00% |
| Boundary Top-3 | **78.13%** |
| Boundary Top-5 | **84.38%** |
| Global $\epsilon=.10$ | 96.88% |
| No pruning | 100% |

Top-3 대비 Boundary Top-3는:

$$
37.50\%\rightarrow78.13\%
$$

으로 **+40.63%p** 개선되었다.

Top-5 대비 Boundary Top-5는:

$$
75.00\%\rightarrow84.38\%
$$

으로 **+9.38%p** 개선되었다.

이 결과에서 현재까지 가장 강한 구조적 관찰은 다음이다.

> **후보 branching이 커질수록 fixed Top-K가 viable/gold path를 잃을 위험이 커진다.**

---

# 16. BADP: 최고점이 아니라 실제 Top-K 경계를 본다

Global band는 최고점 $s_{(1)}$ 주변을 기준으로 후보를 보존한다.

그러나 실제로 제거가 일어나는 지점은 $K$번째와 $K+1$번째 사이이다.

후보 점수를 정렬하면:

$$
s_{(1)}\ge s_{(2)}\ge\cdots\ge s_{(|C|)}
$$

BADP는 다음과 같이 정의하였다.

$$
B_{K,\delta}(C)
=
T_K(C)
\cup
\left\{
p_{(j)}\mid j>K,
\;s_{(K)}-s_{(j)}\le\delta
\right\}
$$

즉 Top-K는 유지하되 **실제 cutoff 바로 아래의 near-tie 후보만 추가 보존**한다.

---

# 17. WN18RR Iterative n=20: BADP의 첫 반복 탐색 개선

20-query budgeted iterative 실험에서:

| 정책 | Search Success | Pruning Regret | Viability F1 | 평균 폭 | Expanded |
|---|---:|---:|---:|---:|---:|
| Top-3 | 50% | 50% | **33.58%** | 2.71 | 24.80 |
| BADP Top-3 $\delta=.005$ | **55%** | **45%** | 32.05% | 3.34 | 27.15 |
| Top-5 | 55% | 45% | 29.97% | 4.06 | 32.35 |
| BADP Top-5 $\delta=.010$ | **60%** | **40%** | 28.10% | 5.00 | 35.10 |
| BADP Top-5 $\delta=.050$ | **65%** | **35%** | 26.20% | 6.16 | 38.25 |

개선 폭은:

Top-3:

$$
50\%\rightarrow55\%
$$

즉 **+5%p**.

Top-5, $\delta=.010$:

$$
55\%\rightarrow60\%
$$

즉 **+5%p**.

Top-5, $\delta=.050$:

$$
55\%\rightarrow65\%
$$

즉 **+10%p**였다.

하지만 폭을 많이 늘릴수록 viability precision/F1이 낮아졌다.

따라서 이 결과는 **BADP가 비용 없이 우월하다**는 증거가 아니라, **추가 예산을 실제 Top-K 경계에 쓰면 success-regret trade-off를 개선할 가능성이 있다**는 증거로 해석하였다.

---

# 18. WN18RR Iterative n=50: 더 큰 표본에서 재확인

50개의 deterministic 2–4 hop query로 확대하였다.

## 18.1 Top-3 계열

| 정책 | Search Success | Avg Expanded |
|---|---:|---:|
| Top-3 | 40% | 24.38 |
| Boundary Top-3 $\delta=.001$ | 42% | 25.08 |
| Boundary Top-3 $\delta=.005$ | **46%** | 25.42 |

Top-3 대비 Boundary Top-3 $\delta=.005$는:

$$
40\%\rightarrow46\%
$$

으로 **+6%p** 개선되었다.

Expanded candidate는:

$$
24.38\rightarrow25.42
$$

으로 약 4.3% 증가하였다.

더 작은 $\delta=.001$에서도:

$$
40\%\rightarrow42\%
$$

으로 **+2%p** 개선되었고 expanded candidate는 24.38에서 25.08로만 증가하였다.

## 18.2 Top-5 계열

| 정책 | Search Success | Avg Expanded |
|---|---:|---:|
| Top-5 | 56% | 29.00 |
| Boundary Top-5 $\delta=.001$ | 58% | 29.50 |
| Boundary Top-5 $\delta=.010$ | **60%** | 31.08 |

Top-5 대비 Boundary Top-5 $\delta=.010$은:

$$
56\%\rightarrow60\%
$$

으로 **+4%p** 개선되었다.

작은 $\delta=.001$에서도:

$$
56\%\rightarrow58\%
$$

으로 **+2%p** 개선되었고 expanded candidate는 29.00에서 29.50으로 증가하였다.

## 18.3 중요한 해석

n=20과 n=50에서 방향이 동일했다.

> **실제 Top-K 경계 주변 후보를 소량 추가 보존하면 iterative multi-hop search success가 반복적으로 증가하는 신호가 나타났다.**

특히 작은 $\delta$에서 +2%p 정도의 개선을 매우 적은 expansion 증가로 얻었다는 점은 비용 측면에서 중요하다.

다만 아직 development/test 분리 없이 탐색한 parameter 결과이므로 최종 confirmatory superiority로 해석하지 않는다.

---

# 19. Conditional BADP: 항상 보존하지 않고 필요할 때만 발동하기

## 19.1 왜 Conditional이 필요했는가

Always-on BADP는 모든 pruning step에서 경계 후보를 추가로 남길 수 있다.

따라서 경계가 이미 명확한 경우에도 불필요한 비용이 발생할 수 있다.

경계 margin을 다음과 같이 정의한다.

$$
\Delta_K
=
s_{(K)}-s_{(K+1)}
$$

Conditional BADP는:

$$
P_{k+1}^{CBADP}
=
\begin{cases}
B_{K,\delta}(C_{k+1}), & \Delta_K\le\tau \\
T_K(C_{k+1}), & \Delta_K>\tau
\end{cases}
$$

로 정의한다.

파라미터 역할은 다음과 같다.

```text
tau   = 경계가 위험한가?
delta = 위험하다면 얼마나 더 보존할 것인가?
```

---

# 20. WebQSP n=20: Conditional BADP가 일반화되지 않은 결과

실제 KGQA 질문에서 방법이 동일하게 작동하는지 확인하기 위해 ToG 공개 WebQSP 질문을 사용하였다.

이 실험은:

- WebQSP 질문 사용
- `qid_topic_entity` 이용
- Wikidata entity statements 탐색
- 동일 DeBERTa scorer
- pruning operator만 비교

한 in-framework validation이다.

Freebase를 사용하는 ToG 공식 성능과 직접 비교하지 않는다.

## 20.1 주요 결과

Top-3 기준:

| 정책 | Search Success | Retrieval F1 | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|
| Top-3 | **35%** | **10.42%** | **3.00** | **33.05** |
| Conditional BADP Top-3 | 35% | 8.18% | 4.25 | 45.65 |

즉:

$$
35\%\rightarrow35\%
$$

으로 **성능 개선이 없었다.**

오히려 width와 expansion만 증가하였다.

## 20.2 Activation rate 문제

현재 margin threshold는 지나치게 자주 BADP를 활성화하였다.

| 정책 | Activation rate |
|---|---:|
| Top3 $\tau=.005$ | 60.0% |
| Top3 $\tau=.010$ | 72.5% |
| Top3 $\tau=.020$ | 87.5% |
| Top5 $\tau=.010$ | 92.5% |
| Top5 $\tau=.020$ | 97.5% |

즉 현재 조건부 방법은 실제로는 상당수 step에서 always-on BADP처럼 동작하였다.

따라서 WebQSP 결과는 다음을 보여준다.

> **Boundary-local preservation 자체와, BADP를 언제 발동할지를 판단하는 risk detector는 별도의 문제이다.**

---

# 21. 현재까지 코드 오류를 제외하고 실제로 개선된 결과만 요약

아래 표는 코드 오류가 없는 실행 중 baseline 대비 실제 성능 향상이 관찰된 결과만 모은 것이다.

| 실험 | 기준선 | 개선 방법 | 성능 변화 | 핵심 의미 |
|---|---|---|---|---|
| Controlled Tableau n=80 | Accuracy 75%, Macro F1 66.67% | Perspective Tableau | **100% / 100%** | 관점 분리의 논리적 유효성 |
| Explanation n=20 | Coverage 50% | Rashomon enumeration | **100%** | 복수 설명 보존 |
| DAFNA n=100 | Exact 61%, F1 82.88% | Possible-world marginal | **62% / 84.13%** | truth candidate marginal의 소폭 개선 |
| WN18RR Frozen n=50 | Top-5 survival 40% | Global $\epsilon=.10$ | **58%** | **+18%p**, width 5.00→5.08 |
| WN18RR Iterative n=10 | Top-K success 60% | Relative-loss .50 | **70%** | **+10%p**, 비용 증가 |
| MAGIC external gold n=420 | Top-3 survival 94.76% | Boundary Top-3 | **97.86%** | **+3.10%p** |
| MAGIC high branching n=32 | Top-3 survival 37.50% | Boundary Top-3 | **78.13%** | **+40.63%p** |
| MAGIC high branching n=32 | Top-5 survival 75.00% | Boundary Top-5 | **84.38%** | **+9.38%p** |
| WN18RR Iterative n=20 | Top-3 success 50% | BADP Top-3 .005 | **55%** | **+5%p** |
| WN18RR Iterative n=20 | Top-5 success 55% | BADP Top-5 .010 | **60%** | **+5%p** |
| WN18RR Iterative n=20 | Top-5 success 55% | BADP Top-5 .050 | **65%** | **+10%p** |
| WN18RR Iterative n=50 | Top-3 success 40% | Boundary Top-3 .005 | **46%** | **+6%p** |
| WN18RR Iterative n=50 | Top-5 success 56% | Boundary Top-5 .010 | **60%** | **+4%p** |

이 표에서 현재 논문의 메인 결과로 가장 직접적으로 연결되는 것은 **MAGIC external-gold boundary analysis와 WN18RR iterative n=20/n=50**이다.

---

# 22. 실패하거나 기각된 가설

연구 결과를 성능 향상 사례만으로 설명하면 방법 선택의 근거가 왜곡된다. 다음 결과도 현재 연구 방향을 결정하는 데 중요했다.

## 22.1 Global additive band는 iterative search에서 실패

Frozen candidate에서는 유망했지만 실제 iterative search에서는 Top-K보다 낮았다.

따라서:

> Global Rashomon band가 항상 Top-K보다 우수하다.

라는 가설은 폐기하였다.

## 22.2 No pruning이 최적은 아니다

MAGIC에서 no pruning은 gold survival 100%였지만 Gold F1은 63.64%로 떨어졌다.

즉:

$$
\text{More Preservation}
\not\Rightarrow
\text{Better Retained Set}
$$

이다.

## 22.3 WebQSP n=20에서 Conditional BADP는 개선되지 않음

Top-3와 동일한 35% success를 기록하면서 비용만 증가하였다.

따라서 현재 Conditional BADP를 일반적 우월 방법으로 주장할 수 없다.

---

# 23. 현재 핵심 연구 가설

현재까지 결과를 종합하면 두 가지는 비교적 강하게 관찰되었다.

### 관찰 1. Branching이 증가하면 fixed Top-K 손실이 커진다

MAGIC high-branching subset에서 Top-3 survival이 37.50%까지 하락했다.

### 관찰 2. Boundary-local preservation은 일부 환경에서 성능을 개선한다

WN18RR n=20과 n=50 모두 BADP/Boundary 방식이 Top-K보다 높은 success를 보였다.

반면 아직 충분히 검증되지 않은 것은 다음이다.

> 작은 boundary margin 자체가 pruning regret의 독립적인 원인인가?

따라서 다음 핵심 식을 직접 검증해야 한다.

$$
P(PR=1\mid\Delta_K\le\tau)
>
P(PR=1\mid\Delta_K>\tau)
$$

그러나 margin과 branching이 같이 움직일 수 있기 때문에 실제 분석은 다음과 같이 확장되어야 한다.

$$
P(PR=1\mid\Delta_K,\;B_k)
$$

여기서 $B_k$는 해당 step의 branching factor이다.

---

# 24. 다음 단계: Boundary Risk Score

WebQSP에서 단순 margin threshold가 너무 자주 발동한 결과를 고려하면, Conditional BADP의 gating을 boundary margin 하나에만 의존시키는 것은 충분하지 않을 가능성이 높다.

다음 후보는 다음 특성을 결합한 위험도이다.

$$
Risk_k
=
f(
\Delta_K,
B_k,
H(S_k),
C_k
)
$$

예를 들어:

- $\Delta_K$: K/K+1 boundary margin
- $B_k$: branching factor
- $H(S_k)$: 후보 점수 분포 entropy
- $C_k$: boundary 주변 후보 밀도

를 사용할 수 있다.

이때 Conditional BADP는:

$$
P_{k+1}
=
\begin{cases}
B_{K,\delta}(C_{k+1}), & Risk_k\ge\tau_r \\
T_K(C_{k+1}), & Risk_k<\tau_r
\end{cases}
$$

로 확장할 수 있다.

이 방향의 핵심은 단순히 beam width를 adaptive하게 만드는 것이 아니다.

> **실제로 Pruning Regret가 발생할 가능성이 높은 경계를 식별하고, 그 순간에만 추가 탐색 예산을 사용하는 것**이 목적이다.

---

# 25. 연구 발전 과정의 최종 정리

```text
1. 상충하는 설명을 하나로 너무 빨리 합치지 말자
        ↓
2. Possible Worlds + Tableau로 여러 해석을 보존하자
        ↓
3. 그런데 실제 Ontology는 relation semantics가 불완전하다
        ↓
4. Multi-hop path에서 relation 후보를 예측하자
        ↓
5. Semantic scorer로 candidate ranking을 개선하자
        ↓
6. 그런데 좋은 candidate가 pruning에서 먼저 사라질 수 있다
        ↓
7. Pruning Regret를 직접 측정하자
        ↓
8. Global Rashomon band는 iterative search에서 불안정하다
        ↓
9. 실제 Top-K cutoff를 대상으로 BADP를 적용하자
        ↓
10. MAGIC/WN18RR에서 boundary-local preservation 개선 확인
        ↓
11. 그러나 always-on widening은 비용과 noise를 증가시킨다
        ↓
12. Conditional BADP를 도입하자
        ↓
13. WebQSP에서는 단순 margin gate가 너무 자주 발동해 개선되지 않았다
        ↓
14. 다음은 margin + branching + score distribution을 이용한 Boundary Risk 추정
```

현재 연구의 가장 정확한 핵심 문장은 다음과 같다.

> **고정 Top-K의 문제는 단순히 K가 작다는 데 있지 않다. scorer가 K번째와 K+1번째 후보를 충분히 구분하지 못하거나 후보 경쟁이 큰 상황에서도 동일하게 비가역적인 제거를 수행한다는 점이 문제다. 따라서 목표는 항상 더 많은 경로를 보존하는 것이 아니라, Pruning Regret 위험이 높은 경계에서만 선택적으로 결정을 지연하는 것이다.**

---

# 26. 현재 결론

현재까지 검증된 결과만 놓고 보면 다음과 같이 정리할 수 있다.

1. **복수 설명 보존은 설명 coverage를 개선하였다.**
2. **불완전한 ontology는 multi-hop semantic relation을 직접 생성하지 못했다.**
3. **relation 후보를 semantic scorer로 ranking하면 weak lexical scoring보다 structured MAGIC 성능이 개선되었다.**
4. **candidate generation 성공과 final selection 성공은 다른 문제였다.**
5. **fixed Top-K는 특히 고분기 구간에서 gold/viable path를 크게 잃었다.**
6. **boundary-local preservation은 MAGIC과 WN18RR에서 반복적으로 성능 개선 신호를 보였다.**
7. **그러나 더 많이 보존할수록 precision과 비용이 악화될 수 있다.**
8. **단순 boundary margin만 사용하는 Conditional BADP는 WebQSP에서 충분히 선택적으로 동작하지 않았다.**
9. 따라서 다음 연구 단계는 **Pruning Regret를 예측하는 Boundary Risk 모델**을 설계하는 것이다.

최종 평가 기준은 계속 다음 세 축을 유지한다.

$$
\boxed{
\text{Search / Evidence Preservation}
\times
\text{Retained-set Validity}
\times
\text{Search Cost}
}
$$
