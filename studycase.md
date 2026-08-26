# 선행 실험과 연구 문제의 발전 과정

## 0. 이 문서를 처음 읽는 사람을 위한 요약

이 연구는 처음부터 `BADP`라는 가지치기 방법을 만들기 위해 시작한 것이 아니다.

처음에는 **서로 충돌하는 여러 설명을 하나로 너무 빨리 결정하지 않고, 여러 가능한 해석을 보존한 뒤 논리적으로 검증하는 방법**을 연구했다. 이 과정에서 실제 온톨로지는 필요한 관계 의미를 모두 포함하지 않는다는 문제가 드러났고, 다중 홉 경로에서 누락 관계를 예측하는 방법을 검토했다. 이후에는 관계 후보를 잘 만들어도 점수화와 가지치기 단계에서 좋은 후보가 먼저 사라질 수 있다는 문제가 더 중요하다는 것을 확인했다.

연구 문제는 다음 순서로 발전했다.

```text
상충하는 여러 설명을 보존하고 싶다
        ↓
Possible Worlds + Tableau
        ↓
실제 Ontology의 관계 의미가 불완전하다
        ↓
Multi-hop Relation Prediction
        ↓
Semantic Scorer로 후보 순위를 개선한다
        ↓
좋은 후보도 검색 중 Pruning에서 사라질 수 있다
        ↓
Pruning Regret를 측정한다
        ↓
전역적으로 후보를 넓게 보존해 본다
        ↓
반복 탐색에서는 비용과 점수 스케일 문제가 발생한다
        ↓
실제 Top-K 경계만 보는 BADP를 제안한다
        ↓
항상 BADP를 켜면 불필요한 비용이 발생한다
        ↓
Conditional BADP를 제안한다
        ↓
단순한 점수 차이만으로는 발동 시점을 충분히 구분하지 못한다
        ↓
현재: Boundary Risk를 더 정확히 추정하는 방향
```

현재 연구의 핵심 질문은 다음과 같다.

> **다중 홉 추론에서 정답 또는 중요한 증거로 이어질 수 있는 경로가 Top-K 가지치기로 너무 일찍 제거되는 문제를 어떻게 줄일 것인가?**

---

# 1. 핵심 용어

이 절은 이후 문서에서 반복해서 사용하는 용어를 먼저 설명한다.

| 용어 | 뜻 | 이 연구에서의 역할 |
|---|---|---|
| Knowledge Graph, KG | 개체(Entity)를 관계(Relation)로 연결한 그래프 | 다중 홉 추론의 검색 공간 |
| Entity | 사람, 장소, 개념, WordNet synset 등의 노드 | 경로의 시작점·중간점·목표점 |
| Relation | 두 개체 사이의 관계 | 경로를 구성하는 edge의 의미 |
| Multi-hop path | 두 개 이상의 relation을 연속해서 따라가는 경로 | 직접 연결되지 않은 답·증거 탐색 |
| Candidate path | 현재 단계에서 탐색 가능한 경로 후보 | pruning 대상 |
| Scorer | 후보가 질의와 얼마나 관련 있는지 점수화하는 모델 | 본 실험에서는 주로 DeBERTa 기반 의미 점수 사용 |
| Top-K | 점수가 높은 K개 후보만 남기는 방식 | 기본 가지치기 기준선 |
| Pruning | 다음 단계로 넘기지 않을 후보를 제거하는 과정 | 탐색 비용 제어 |
| Viable path | 남은 hop 수 안에 목표 또는 gold evidence에 도달 가능한 경로 | pruning이 보존해야 하는 경로 |
| Branching factor | 한 단계에서 경쟁하는 후보 수 | 값이 클수록 Top-K 경쟁이 심해짐 |
| Boundary | Top-K에서 K번째 후보와 K+1번째 후보 사이의 제거 경계 | BADP가 직접 보는 지점 |
| Boundary margin | K번째와 K+1번째 점수 차이 | 경계의 불확실성을 나타내는 후보 지표 |
| Possible World | 여러 해석 중 하나를 가정한 독립적인 상태 | 불확실한 관계·주장을 조기에 하나로 합치지 않기 위한 표현 |
| Rashomon set | 성능이나 점수가 비슷해 하나로 확정하기 어려운 후보 집합 | 여러 near-optimal 후보를 보존하는 초기 아이디어 |
| Ontology | 관계의 의미와 제약을 명시한 지식 체계 | 후보 관계의 의미·논리 제약 정의 |
| Tableau | 논리식의 일관성·모순을 확인하는 추론 방식 | 가능한 world가 논리적으로 가능한지 검증 |
| Provenance | 사실·경로가 어디에서 왔는지 나타내는 출처 정보 | scorer와 독립된 외부 gold 또는 설명 근거로 사용 |
| BADP | Boundary-Aware Delayed Pruning | Top-K 경계 바로 아래의 near-tie 후보만 추가 보존 |
| Conditional BADP | 경계가 위험하다고 판단될 때만 BADP를 켜는 방법 | 불필요한 추가 탐색 비용을 줄이기 위한 확장 |

## 1.1 Top-K를 간단한 예로 이해하기

후보 점수가 다음과 같다고 하자.

```text
1위  0.91
2위  0.84
3위  0.812   ← K=3의 마지막 보존 후보
4위  0.809   ← 제거되는 첫 후보
5위  0.62
```

Top-3는 1~3위만 남긴다. 그런데 3위와 4위의 차이는 0.003밖에 되지 않는다.

경계 점수 차이는 다음처럼 정의한다.

$$\Delta_K = s_{(K)} - s_{(K+1)}$$

위 예에서는 `ΔK = 0.003`이다.

BADP는 4위처럼 **실제 제거 경계에서 거의 동점인 후보를 바로 버리지 말자**는 아이디어다.

---

# 2. 사용한 데이터셋과 각 데이터셋의 역할

서로 다른 데이터셋을 사용한 이유는 하나의 데이터셋으로 모든 실패 원인을 구분하기 어렵기 때문이다.

| 데이터셋 | 데이터의 성격 | 사용 목적 | 현재 문서에서의 주의점 |
|---|---|---|---|
| Controlled Ontology | 직접 만든 논리 통제 사례 | Tableau와 관점 분리 로직 단위 검증 | 실제 자연어 일반화 성능이 아님 |
| MAGIC | 다중 홉 상충 관계 데이터 | 관계 해석, possible worlds, conflict evidence 보존 분석 | 여기서는 released structured triplet을 사용하므로 공식 자연어 MAGIC 점수와 다름 |
| DAFNA-EA Books | 여러 출처가 동일 책의 저자에 대해 상충 주장 | 후보 world 생성과 최종 truth 선택을 분리 분석 | 100개 gold book subset 사용 |
| WN18RR | WordNet 기반 관계 예측 benchmark | 통제된 KG에서 반복 pruning 메커니즘 분석 | 일반 QA 정확도가 아니라 2~4 hop 경로 탐색 stress test |
| WebQSP | 실제 자연어 KG 질의응답 benchmark | 실제 질문에서 pruning 정책의 외적 타당성 확인 | 본 실험은 Wikidata를 사용하므로 Freebase 기반 ToG 성능과 직접 비교 불가 |

## 2.1 Controlled Ontology

직접 구성한 80개 사례를 사용하였다.

4개 class가 각각 20개씩 존재한다.

- consistent: 모순 없음
- divergence: 관점이 다르지만 논리적 모순은 아님
- intra-contradiction: 같은 관점 내부의 모순
- inter-contradiction: 서로 다른 관점 사이의 충돌

별도의 explanation 실험은 20개 사례이며, 각 사례에 2개의 최소 contradiction explanation을 만들었다.

이 데이터는 **논리 추론기가 의도한 대로 작동하는지 확인하는 단위 검증용**이다.

## 2.2 MAGIC

MAGIC은 다중 홉 경로에서 상충하는 정보를 다루는 benchmark이다.

본 연구의 검증된 실험은 자연어 문단을 직접 평가한 공식 MAGIC protocol이 아니라, 공개된 다음 구조 정보를 사용하였다.

- `subgraph`
- `original_triplet`
- `perturb_triplet`

검증된 structured multi-hop 범위는 다음과 같다.

- 588 rows
- 1,056 query conflicts

`perturb_triplet`은 이후 pruning 실험에서 scorer와 독립적인 **외부 gold conflict path**로 활용하였다.

따라서 본 문서의 `row conflict recall`, `query conflict recall`, `structured exact localization`은 MAGIC 논문의 자연어 ID/LOC 지표와 직접 비교하면 안 된다.

## 2.3 DAFNA-EA Books / AuthorsNamesList

DAFNA-EA Books는 여러 웹 출처가 같은 책의 저자에 대해 서로 다른 값을 주장하는 truth-discovery 데이터다.

사용 범위는 다음과 같다.

- gold books: 100
- source-object claims: 1,999
- sources: 227

예를 들어 한 책의 저자를 여러 출처가 다음처럼 다르게 주장할 수 있다.

```text
Source A → {Alice, Bob}
Source B → {Alice}
Source C → {Alice, Carol}
```

이 데이터에서는 **좋은 truth 후보를 만드는 것**과 **그 후보 중 실제 정답을 선택하는 것**을 분리해서 분석할 수 있다.

## 2.4 WN18RR

WN18RR은 WordNet의 synset 관계로 구성된 지식그래프 benchmark이다.

대표 relation은 다음과 같다.

- hypernym
- instance hypernym
- member meronym
- has part
- similar to
- derivationally related form

본 연구는 원래 WN18RR의 일반적인 link-prediction 성능을 보고하는 것이 아니라, train graph에서 2~4 hop 경로가 존재하도록 별도의 deterministic benchmark를 만들었다.

두 종류의 실험을 구분해야 한다.

### Frozen candidate 진단

후보 relation 집합을 한 번 점수화하고, 어느 후보가 살아남는지 본다.

이 실험은 pruning operator의 단순 성질을 보기 쉽지만 실제 다중 홉 검색과 동일하지 않다.

### Iterative search

한 단계에서 남긴 후보만 다음 단계에서 확장한다.

```text
Expand → Score → Prune → Expand → Score → Prune → ...
```

따라서 앞 단계의 잘못된 pruning이 이후 검색에 누적된다. 현재 논문의 핵심 메커니즘 검증은 이 iterative search가 더 중요하다.

## 2.5 WebQSP

WebQSP는 실제 자연어 질문과 KG answer를 포함하는 질의응답 benchmark이다.

예:

```text
Where does the Columbia River start?
```

본 실험에서는 ToG가 공개한 WebQSP 질문 파일과 `qid_topic_entity`를 사용하고, topic entity에서 Wikidata의 entity-valued outgoing statements를 확장하였다.

중요한 제한은 다음과 같다.

- ToG의 원래 Freebase backend와 다름
- outgoing relation만 탐색
- node당 edge 수를 lexical prefilter로 제한
- 최종 LLM answer generator를 사용하지 않음

따라서 여기서 측정한 값은 **end-to-end QA 정확도라기보다 retrieval/search 성능**이다.

---

# 3. 평가 지표를 먼저 정확히 정의하기

이 연구에서는 서로 다른 실험의 지표를 같은 의미의 “정확도”로 부르지 않는다.

## 3.1 Accuracy와 Macro F1

Controlled Ontology처럼 명확한 class label이 있는 실험에서 사용한다.

Accuracy는 전체 사례 중 정답 class를 맞힌 비율이다.

Macro F1은 각 class의 F1을 동일한 가중치로 평균한 값이다.

## 3.2 Explanation Coverage

gold minimal explanation 중 방법이 실제로 반환한 explanation의 비율이다.

$$Coverage = \frac{Returned\ Gold\ Explanations}{All\ Gold\ Explanations}$$

## 3.3 MAGIC structured conflict 지표

### Row conflict recall

row 단위로 conflict를 검출한 비율이다.

### Query conflict recall

하나의 row에 여러 query conflict가 있을 수 있기 때문에 query 단위로 계산한다.

### Structured exact localization

한 row에서 요구되는 paired perturb evidence를 모두 정확하게 지역화했는지 보는 더 엄격한 지표다.

이 세 지표는 **공식 자연어 MAGIC ID/LOC가 아니다.**

## 3.4 Gold-world coverage

possible-world candidate를 만들었을 때 실제 gold truth를 포함하는 world가 후보 집합 안에 하나라도 존재하는 비율이다.

이 지표가 높아도 최종 선택 정확도가 높다는 뜻은 아니다.

## 3.5 Exact-set accuracy와 Author F1

DAFNA에서 사용한다.

Exact-set accuracy는 예측한 저자 집합 전체가 gold 저자 집합과 정확히 같은 비율이다.

Author F1은 저자 단위 precision과 recall의 조화 평균이다.

## 3.6 Gold Path Survival

pruning 전 candidate에 존재했던 외부 gold path가 pruning 후에도 하나 이상 남았는지 보는 지표다.

$$Survival = \frac{Gold\ Path\ Survived\ Queries}{Recoverable\ Queries}$$

MAGIC external-gold 실험에서 사용한다.

## 3.7 Retained Gold Precision / Recall / F1

많이 남기는 정책이 무조건 좋아 보이지 않도록, 남긴 path 중 실제 gold가 얼마나 되는지도 측정한다.

$$Precision = \frac{Retained\ Gold\ Paths}{All\ Retained\ Paths}$$

$$Recall = \frac{Retained\ Gold\ Paths}{Available\ Gold\ Paths}$$

$$F1 = \frac{2PR}{P+R}$$

## 3.8 Search Success

WN18RR iterative search에서 제한 hop 안에 목표 evidence까지 실제로 도달한 query의 비율이다.

## 3.9 Viable Path

현재 partial path에서 남은 hop budget 안에 target까지 이어질 수 있으면 viable하다고 정의한다.

예를 들어 최대 4 hop 탐색의 depth 2에서 현재 경로가 target까지 2 hop 이하로 연결될 수 있다면 viable path다.

## 3.10 Pruning Regret

pruning 직전에는 viable path가 존재했지만 pruning 이후 viable path가 하나도 남지 않은 사건이다.

질의 `i`, depth `k`에서 다음 두 조건을 모두 만족하면 regret event로 계산한다.

```text
1. pruning 전 candidate 중 viable path가 하나 이상 존재한다.
2. pruning 후 retained path에는 viable path가 하나도 없다.
```

간단히 쓰면:

$$PR_{i,k}=1\;\;\text{if viable-before = true and viable-after = false}$$

Query Pruning Regret는 한 query에서 한 번이라도 이런 사건이 발생했는지를 본다.

$$QPR = \frac{Queries\ With\ Any\ Pruning\ Regret}{All\ Queries}$$

**낮을수록 좋다.**

## 3.11 Average Active Width

각 pruning 단계 이후 평균적으로 몇 개의 path를 유지했는지 나타낸다.

## 3.12 Average Expanded Candidates

한 query를 처리하는 동안 실제로 확장·검토한 후보 수의 평균이다.

탐색 비용을 비교하는 핵심 지표다.

## 3.13 WebQSP retrieval 지표

### Search Success

gold answer entity가 탐색 결과에 하나 이상 포함되면 성공이다.

### Answer Hit@1

최상위 결과가 gold answer와 일치하는 비율이다.

### Macro Retrieval F1

질의별 retrieval precision/recall의 F1을 계산한 뒤 평균한다.

### Answer Recall

gold answer 집합 중 얼마나 회수했는지 본다.

### Answer-level Pruning Regret

한 depth의 pruning 직전에는 gold answer endpoint가 존재했는데 pruning 후에는 모두 사라진 query의 비율이다.

---

# 4. 코드 오류 및 지표 교정 원칙

연구 과정에서 구현 오류와 후처리 오류가 여러 번 발견되었기 때문에 아래 원칙을 적용한다.

1. scorer 입력 오류가 있었던 자연어 MAGIC 결과는 폐기한다.
2. provenance metadata가 proposition과 함께 NLI 입력에 들어갔던 실행은 성능 근거로 사용하지 않는다.
3. retry 횟수와 logical call 횟수가 섞였던 실행은 비용 비교에서 제외한다.
4. analyzer eligibility가 잘못 계산된 실행은 compute-matched 결과에서 제외한다.
5. workflow의 **결과 출력 단계만 실패**하고 실제 평가 JSON 생성은 성공한 경우에는 평가 오류와 구분한다.
6. 가능한 경우 GitHub Actions artifact의 JSON을 최종 숫자의 기준으로 사용한다.
7. 서로 다른 지표를 같은 “정확도 개선”으로 비교하지 않는다.

## 4.1 이번 문서에서 교정한 항목

| 항목 | 기존 문서에서의 문제 | 교정 |
|---|---|---|
| WN18RR Frozen n=50 | `Top-3 32%, Top-5 40%, Global .10 58%`를 해당 run의 검증 결과처럼 서술 | 해당 run artifact의 실제 출력으로 교체: Top-1 accuracy 16%, Rashomon ε=.05 gold coverage 42%, 평균 Rashomon size 3.82, Tableau gold retention 42%, 최종 Top-1 accuracy 16% |
| MAGIC Possible Worlds 평균 world 수 | 반올림값이 혼재 | weak-world run 기준 row당 7.335→**7.34**, query당 4.084→**4.08**, candidate path/query 1.454→**1.45** |
| DeBERTa 개선폭 | 반올림된 입력값끼리 뺀 +14.67%p, +8.34%p 표기가 존재 | artifact 원시값 차이 기준 **+18.71%p / +14.68%p / +8.33%p** |
| MAGIC Boundary 정책 | δ 값이 생략되어 어떤 정책인지 불명확 | **Boundary Top-3 δ=.01**, **Boundary Top-5 δ=.01**로 명시 |
| WN18RR n=50 | success만 있고 regret 지표가 빠짐 | Top-3 58%→Boundary .005 52%, Top-5 42%→Boundary .010 38%를 함께 표기 |
| WN18RR n=50 workflow | 이전 run이 마지막 summary 단계의 `KeyError: summary` 때문에 failure로 표시 | 평가 단계는 성공했으나 artifact가 스킵된 후처리 오류였음. 수정 재실행 `32852520635`는 평가·artifact·summary 모두 성공 |
| WebQSP Conditional | success만 비교하면 손실 양상이 불충분 | F1, answer recall, pruning regret, width, expansion, activation rate를 함께 표기 |

### 중요한 구분: WN18RR Frozen의 16%와 42%

`Top-1 accuracy 16%`와 `Rashomon gold coverage 42%`는 **같은 지표가 아니다.**

- 16%: 최상위 relation 하나가 gold relation인지
- 42%: ε=.05 후보 집합 안에 gold relation이 포함되는지

따라서 `16% → 42% 정확도 향상`이라고 쓰면 안 된다.

정확한 해석은 다음이다.

> **최상위 단일 선택의 정답률은 16%였지만, 평균 3.82개의 near-optimal 후보를 보존하면 gold relation을 후보 집합 안에 포함하는 비율은 42%였다. 그러나 Tableau filtering 후 최상위 선택 정확도는 여전히 16%였다.**

즉 이 실험은 최종 정확도 향상이 아니라 **좋은 후보는 더 많이 보존되지만 ranking/resolution이 병목**임을 보여준다.

---

# 5. 연구 단계 1: 관점이 다른 사실을 너무 빨리 병합하지 않기

## 5.1 초기 문제

서로 다른 출처나 관점에서 나온 사실을 하나의 전역 ABox에 바로 합치면 다음 두 상황을 혼동할 수 있다.

```text
A. 같은 관점 내부에서 실제 모순 발생
B. 서로 다른 관점이 각기 다른 사실을 보고 있음
```

따라서 fact를 perspective별로 분리한 뒤 Tableau를 적용하였다.

## 5.2 Controlled Ontology 결과

| 방법 | Accuracy | Macro F1 |
|---|---:|---:|
| Vanilla merged Tableau | 75.00% | 66.67% |
| Perspective Tableau | **100.00%** | **100.00%** |
| Rashomon Tableau | **100.00%** | **100.00%** |

Perspective Tableau는 Vanilla 대비:

- Accuracy: **+25.00%p**
- Macro F1: **+33.33%p**

개선되었다.

단, 이 결과는 직접 만든 통제 논리 사례에서의 reasoner correctness이다.

Rashomon Tableau는 Perspective Tableau보다 class accuracy를 추가로 올리지는 않았다.

## 5.3 Explanation Coverage

20개 사례, 총 40개의 gold minimal explanation에서:

| 방법 | Explanation Coverage |
|---|---:|
| Single-path | 50.00% |
| Rashomon enumeration | **100.00%** |

즉 Rashomon의 초기 가치는 class accuracy보다 **복수의 타당한 설명을 모두 남기는 것**에서 더 명확하게 나타났다.

---

# 6. 연구 단계 2: 실제 Ontology는 필요한 관계 의미를 모두 알지 못한다

## 6.1 세 가지를 구분해야 한다

다중 홉 경로가 존재한다는 사실만으로 그 경로가 의미하는 관계나 논리적 모순을 알 수는 없다.

$$Graph\ Reachability \neq Semantic\ Relation \neq Logical\ Contradiction$$

예를 들어:

```text
h --r1--> e1 --r2--> e2 --r3--> t
```

라는 경로가 있어도 우리가 알고 싶은 직접 관계가 `(h, ?, t)`라면 ontology가 `?`를 자동으로 만들어 주지는 않는다.

## 6.2 MAGIC에서 확인한 차이

검증된 structured multi-hop 결과:

| 지표 | 결과 |
|---|---:|
| Multi-hop legacy direct detection | 33.16% |
| Multi-hop bidirectional candidate-path coverage | **68.03%** |
| Multi-hop ontology/Tableau conflict detection | **5.44%** |

여기서 68.03%는 **candidate path coverage**이며 conflict accuracy가 아니다.

핵심은 경로를 찾는 능력과 그 경로를 논리적으로 해석하는 능력 사이에 큰 차이가 있었다는 점이다.

---

# 7. 연구 단계 3: 누락 관계를 후보로 예측하기

온톨로지가 직접 관계를 모른다고 추론을 끝내는 대신 관계 후보를 생성하는 구조를 검토했다.

미지 관계를 다음처럼 둔다.

$$(h, ?, t)$$

후보 관계 집합:

$$R(h,t)=\{r_1,r_2,...,r_m\}$$

경로 `p`와 relation `r`의 의미 적합도를 scorer가 계산한다.

$$s(p,r) \in [0,1]$$

각 관계 후보를 별도의 possible world로 만들고 ontology/Tableau는 **관계를 생성하는 역할이 아니라 논리적으로 불가능한 후보를 제거하는 역할**로 재정의하였다.

이 단계에서 중요한 문제가 다시 생겼다.

```text
좋은 relation 후보를 만들었다
        ≠
그 후보를 최종적으로 잘 고른다
        ≠
그 후보가 검색 과정 끝까지 살아남는다
```

이 구분이 이후 pruning 연구로 연결된다.

---

# 8. 연구 단계 4: MAGIC Possible Worlds — 후보 보존과 선택을 분리

## 8.1 Possible World란 무엇인가

하나의 경로에 여러 해석이 가능하면 각각을 독립된 world로 유지한다.

예:

```text
World 1: 경로가 q를 지지한다
World 2: 경로가 not-q를 지지한다
World 3: 아직 해석 불충분
```

각 world는 claim, source/provenance, relation interpretation, derivation을 가진다.

논리적으로 불가능한 world는 Tableau로 제거한다.

## 8.2 검증된 결과

588 rows, 1,056 query conflicts 기준:

| 방법 | Row conflict recall | Query conflict recall | Gold-world query recall | Structured exact LOC |
|---|---:|---:|---:|---:|
| Static Tableau | 5.44% | 4.45% | — | — |
| Early-commit single world | 29.93% | 22.63% | — | — |
| Possible-world retention | — | — | **39.39%** | **29.42%** |
| Weakly weighted worlds | 22.79% | 16.86% | — | 7.14% |

Weakly weighted possible-world run의 평균 후보 규모는:

- worlds / row: **7.34**
- worlds / query: **4.08**
- candidate paths / query: **1.45**

였다.

## 8.3 해석

`Gold-world query recall 39.39%`와 `Weakly weighted exact LOC 7.14%`의 차이는 다음을 보여준다.

> **좋은 world를 후보에 포함하는 것과, 그 world를 최종 선택하는 것은 서로 다른 문제다.**

---

# 9. 연구 단계 5: Semantic Scorer로 후보 순위 개선

Weak lexical weighting 대신 다음 DeBERTa NLI 모델을 사용하였다.

`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`

DeBERTa는 새로운 relation을 생성하는 모델이 아니라 **이미 만들어진 후보의 의미 적합도를 점수화하는 scorer**로 사용하였다.

## 9.1 검증된 structured MAGIC 결과

| 지표 | Weak lexical | DeBERTa | 변화 |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71%p** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68%p** |
| Structured exact localization | 7.14% | **15.48%** | **+8.33%p** |
| Query gold-path selection | — | **22.06%** | 참고 지표 |

이 값은 released structured triplet에 대한 진단 결과다.

## 9.2 코드 오류로 제외한 자연어 MAGIC 실행

초기 자연어 실험 일부에서는 다음 provenance metadata가 proposition과 같이 scorer 입력에 포함되었다.

```text
[source=context1, sentence=...]
[source=context2, sentence=...]
```

이 정보는 의미 판단 대상이 아니라 audit metadata이다.

따라서 **해당 수정 전 자연어 MAGIC 정확도는 전부 최종 성능 근거에서 제외한다.**

위 표의 41.50%, 31.53%, 15.48%는 이 자연어 오류 결과가 아니라 **structured triplet world-ranking diagnostic** 결과다.

---

# 10. 연구 단계 6: DAFNA — 후보가 있어도 최종 선택은 어렵다

## 10.1 후보 생성 결과

100개 gold book에서 possible-world candidate generation의 gold-world coverage는 **93%**였다.

평균 candidate worlds는 27.94개, 최대 256개였다.

## 10.2 최종 truth 선택 결과

| 방법 | Exact-set Accuracy | Author F1 |
|---|---:|---:|
| Possible-world uniform | 58% | 80.38% |
| Hard-commit reliability | 61% | 84.04% |
| Possible-world marginal reliability | **62%** | **84.13%** |
| Prior atomic resolution | 61% | 82.88% |
| TruthFinder | 57% | 66.85% |
| AccuSim | 57% | 66.18% |
| 2-Estimates | 54% | 65.28% |
| 3-Estimates | 53% | 65.45% |

Prior atomic resolution 대비 possible-world marginal은:

- Exact-set Accuracy: **61% → 62%, +1%p**
- Author F1: **82.88% → 84.13%, +1.25%p**

였다.

하지만 더 중요한 것은:

```text
Gold-world coverage = 93%
Best exact selection = 62%
```

라는 차이다.

즉 candidate generation보다 ranking/calibration이 더 큰 병목이었다.

---

# 11. 연구 단계 7: 검색 중 좋은 후보가 사라지는 문제

Semantic scorer를 개선해도 candidate가 중간 pruning에서 제거되면 후속 reasoner는 해당 정보를 사용할 수 없다.

따라서 연구 질문이 다음과 같이 이동하였다.

```text
이전 질문:
어떤 relation/world가 가장 맞는가?

새 질문:
맞는 relation/world가 후보에 있었는데
검색 중간에 먼저 제거되는 것은 아닌가?
```

이 문제를 직접 측정하기 위해 `Pruning Regret`를 도입하였다.

---

# 12. WN18RR Frozen n=50 — 후보 보존 진단

이 절은 이번 교정에서 가장 중요하다.

검증 run은 50개 2~4 hop 예제, 11개 candidate relation, `epsilon=.05` 조건이다.

실제 artifact 결과:

| 지표 | 결과 |
|---|---:|
| Top-1 relation accuracy | **16%** |
| Rashomon ε=.05 gold relation coverage | **42%** |
| Tableau 후 gold relation retention | **42%** |
| Rashomon+Tableau 최종 Top-1 accuracy | **16%** |
| 평균 Rashomon 후보 수 | **3.82** |
| 평균 Tableau rejected worlds | **0.00** |

이 결과를 `16% → 42% 정확도 향상`으로 해석하면 안 된다.

정확한 의미는 다음과 같다.

> **단일 최고점은 gold relation을 16%만 선택했지만, 평균 3.82개의 near-optimal 후보를 유지하면 42%의 사례에서 gold relation이 후보 집합 안에는 존재했다. 그러나 현재 ontology/Tableau는 추가 후보를 제거하거나 ranking을 개선하지 못했기 때문에 최종 Top-1 정확도는 16%로 그대로였다.**

이 실험은 이후 연구 초점을 final resolution보다 **candidate survival**로 이동시키는 근거가 되었다.

---

# 13. WN18RR Iterative n=10 — 전역 score band의 실패와 Relative-loss

Frozen candidate에서 후보 보존 가능성을 본 뒤 실제 iterative search로 이동하였다.

## 13.1 Global additive band

| 정책 | Search Success | Query Pruning Regret | Avg Width |
|---|---:|---:|---:|
| Top-3 | **60%** | 40% | 2.67 |
| Top-5 | **60%** | 40% | 3.88 |
| Global ε=.05 | 40% | 60% | 2.65 |
| Global ε=.10 | 40% | 60% | 3.62 |

전역 additive band는 iterative search에서 오히려 Top-K보다 나빴다.

따라서 다음 가설은 폐기하였다.

> `최고점 주변 near-optimal 후보를 항상 보존하면 Top-K보다 일반적으로 좋다.`

## 13.2 Relative-loss

점수의 절대 차이 대신 `1-score`의 상대 손실을 사용하였다.

| 정책 | Search Success | Query Pruning Regret | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 | 21.30 |
| Top-5 | 60% | 40% | 3.88 | 28.30 |
| Relative-loss .25 | 50% | 50% | 4.09 | 31.40 |
| Relative-loss .50 | **70%** | **30%** | **5.97** | 31.40 |

Relative-loss .50은 success를 +10%p 높였지만 폭도 크게 증가하였다.

이 시점부터 평가 기준을 다음 세 축으로 고정하였다.

```text
1. Search / Evidence Preservation
2. Retained-set Validity
3. Search Cost
```

---

# 14. MAGIC External Gold — pruning이 실제 증거를 잃는지 확인

DeBERTa scorer 자체를 gold로 사용하면 순환 평가가 될 수 있으므로 `perturb_triplet` provenance를 외부 gold path로 사용하였다.

전체 1,056 query 중:

- candidate path가 존재한 query: 618
- pruning 전에 gold conflict path가 존재한 recoverable query: **420**

## 14.1 Recoverable query 420개

| 정책 | Gold Path Survival | Gold Precision | Gold Recall | Gold F1 | Avg Width |
|---|---:|---:|---:|---:|---:|
| Top-1 | 80.71% | **80.71%** | 80.52% | **80.62%** | 1.00 |
| Top-3 | 94.76% | 59.38% | 94.77% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 98.10% | 70.54% | 1.79 |
| Global ε=.10 | 97.14% | 50.18% | 97.15% | 66.18% | 1.94 |
| Relative-loss .25 | 83.81% | 74.26% | 83.61% | 78.66% | 1.13 |
| **Boundary Top-3 δ=.01** | **97.86%** | 55.30% | **97.86%** | 70.67% | 1.77 |
| **Boundary Top-5 δ=.01** | **98.81%** | 52.93% | **98.81%** | 68.93% | 1.87 |
| No pruning | 100% | 46.67% | 100% | 63.64% | 2.15 |

Top-3 대비 Boundary Top-3 δ=.01의 survival은:

- 94.76% → 97.86%
- **+3.10%p**

이다.

그러나 Gold F1은 73.01% → 70.67%로 낮아졌다.

즉 **더 많은 gold path를 살렸지만 non-gold path도 함께 증가했다.**

## 14.2 고분기 구간: 후보 path 5개 이상

recoverable query 32개에서:

| 정책 | Gold Path Survival | Gold Precision | Gold F1 | Avg Width |
|---|---:|---:|---:|---:|
| Top-3 | 37.50% | 12.50% | 18.75% | 3.00 |
| Top-5 | 75.00% | **15.00%** | 25.00% | 5.00 |
| Boundary Top-3 δ=.01 | **78.13%** | 14.97% | **25.13%** | 5.22 |
| Boundary Top-5 δ=.01 | **84.38%** | 13.78% | 23.68% | 6.13 |
| Global ε=.10 | 96.88% | 11.52% | 20.60% | 8.41 |
| No pruning | 100% | 10.26% | 18.60% | 9.75 |

Top-3 survival은 37.50%에서 78.13%로 **+40.63%p** 증가하였다.

Top-5 survival은 75.00%에서 84.38%로 **+9.38%p** 증가하였다.

이 결과에서 가장 강한 구조적 관찰은 다음이다.

> **후보 수가 많아질수록 고정 Top-K가 중요한 path를 잃는 위험이 커졌다.**

---

# 15. BADP — 실제 제거 경계만 추가 보존하기

후보 점수를 높은 순서대로 `s(1), s(2), ...`라고 하자.

Top-K는 K번째 이후를 모두 제거한다.

BADP는 K번째 점수보다 `δ`만큼 이내에 있는 후보만 추가로 남긴다.

$$B_{K,\delta}=TopK \cup \{p_j : j>K,\;s_{(K)}-s_{(j)}\le\delta\}$$

핵심은 최고점 주변 전체를 보존하는 것이 아니라 **실제로 잘리는 cutoff 주변만 지연**한다는 것이다.

---

# 16. WN18RR Iterative n=20 — BADP 첫 반복 탐색 결과

검증 artifact의 정확한 결과는 다음과 같다.

| 정책 | Search Success | Query Pruning Regret | Viability Precision | Viability Recall | Viability F1 | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|---:|---:|---:|
| Top-3 | 50% | 50% | 24.46% | 53.57% | **33.58%** | 2.71 | 24.80 |
| Boundary Top-3 δ=.005 | **55%** | **45%** | 22.32% | 56.82% | 32.05% | 3.34 | 27.15 |
| Top-5 | 55% | 45% | 20.22% | 57.89% | 29.97% | 4.06 | 32.35 |
| Boundary Top-5 δ=.010 | **60%** | **40%** | 18.18% | 61.86% | 28.10% | 5.00 | 35.10 |
| Boundary Top-5 δ=.050 | **65%** | **35%** | 16.24% | 67.74% | 26.20% | 6.16 | 38.25 |

성공률과 regret는 개선되었지만 Viability Precision/F1과 비용이 악화되었다.

따라서 이 결과는 `BADP가 공짜로 우월하다`가 아니라 다음 trade-off를 보여준다.

> **경계 보존량을 늘리면 목표 경로 survival은 개선될 수 있지만 noise와 search cost도 증가한다.**

### 엄격한 width 근접 비교

Top-3와 가장 폭이 가까운 Boundary Top-3 δ=.001은 success 50%로 Top-3와 동일했다.

Top-5와 가장 폭이 가까운 Boundary Top-5 δ=.001도 success 55%로 Top-5와 동일했다.

따라서 n=20에서는 **strict same-budget superiority는 확인되지 않았다.**

---

# 17. WN18RR Iterative n=50 — 더 큰 표본에서 재검증

수정 재실행 `32852520635`가 평가, artifact, summary까지 모두 성공하였다.

2~4 hop 분포:

- 2 hop: 19
- 3 hop: 23
- 4 hop: 8

## 17.1 주요 결과

| 정책 | Search Success | Query Pruning Regret ↓ | Viability Precision | Viability Recall | Viability F1 | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|---:|---:|---:|
| Top-3 | 40% | 58% | 25.00% | 54.93% | **34.36%** | 2.69 | 24.38 |
| Boundary Top-3 δ=.001 | 42% | 56% | 24.59% | 55.00% | 33.99% | 2.86 | 25.08 |
| Boundary Top-3 δ=.005 | **46%** | **52%** | 23.98% | 57.59% | 33.86% | 3.16 | 25.42 |
| Top-5 | 56% | 42% | 23.60% | 63.07% | **34.35%** | 3.95 | 29.00 |
| Boundary Top-5 δ=.001 | 58% | 40% | 22.78% | 63.64% | 33.55% | 4.17 | 29.50 |
| Boundary Top-5 δ=.010 | **60%** | **38%** | 21.42% | 66.26% | 32.37% | 4.73 | 31.08 |

## 17.2 같은 결과를 성공/비용 관점에서 보기

Top-3 → Boundary Top-3 δ=.005:

- Search Success: **40% → 46%, +6%p**
- Query Pruning Regret: **58% → 52%, -6%p**
- Avg Expanded: **24.38 → 25.42, +1.04**

Top-5 → Boundary Top-5 δ=.010:

- Search Success: **56% → 60%, +4%p**
- Query Pruning Regret: **42% → 38%, -4%p**
- Avg Expanded: **29.00 → 31.08, +2.08**

### 더 작은 비용 증가 구간

Boundary δ=.001에서는:

- Top-3: success **40% → 42%**, expanded **+0.70**
- Top-5: success **56% → 58%**, expanded **+0.50**

이었다.

다만 Viability F1은 Top-K보다 소폭 낮아졌다.

즉 n=50에서도 핵심 trade-off는 그대로다.

```text
Success / Recall ↑
Pruning Regret ↓
하지만 Precision / F1 ↓
Search Cost ↑
```

---

# 18. Conditional BADP — BADP를 항상 켜지 않기

Always-on BADP는 경계가 충분히 명확한 상황에서도 추가 후보를 남길 수 있다.

그래서 경계 margin `ΔK`가 작은 경우에만 BADP를 켜는 Conditional BADP를 만들었다.

규칙은 단순하다.

```text
if ΔK <= τ:
    BADP(K, δ) 사용
else:
    Top-K 사용
```

여기서:

- `τ`: BADP를 켤지 판단하는 경계 위험 임계값
- `δ`: BADP가 켜졌을 때 추가로 보존할 점수 범위

## 18.1 WN18RR n=50 Conditional 결과

| 정책 | Success | Pruning Regret | Avg Width | Avg Expanded | Activation Rate |
|---|---:|---:|---:|---:|---:|
| Conditional Top-3 τ=.005, δ=.005 | **46%** | **52%** | 3.16 | 25.42 | **28.32%** |
| Conditional Top-3 τ=.010, δ=.005 | **46%** | **52%** | 3.16 | 25.42 | 43.36% |
| Conditional Top-3 τ=.020, δ=.010 | 46% | 52% | 3.38 | 26.38 | 62.28% |
| Conditional Top-5 τ=.010, δ=.010 | **60%** | **38%** | 4.73 | 31.08 | **61.80%** |
| Conditional Top-5 τ=.020, δ=.010 | **60%** | **38%** | 4.73 | 31.08 | 73.03% |
| Conditional Top-5 τ=.050, δ=.020 | 60% | 38% | 5.11 | 33.22 | 94.38% |

중요한 점은 Conditional Top-3 τ=.005가 전체 boundary check의 28.32%에서만 활성화되었음에도 always-on Boundary Top-3 δ=.005와 동일한 46% success를 보였다는 것이다.

그러나 이 결과만으로 Conditional이 일반적으로 더 좋다고 확정할 수는 없다. WebQSP에서는 다른 패턴이 나타났다.

---

# 19. WebQSP n=20 — 실제 질문에서는 단순 margin gate가 충분하지 않았다

## 19.1 기본 결과

| 정책 | Search Success | Hit@1 | Retrieval F1 | Answer Recall | Answer Pruning Regret ↓ | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|---:|---:|---:|
| Top-3 | **35%** | 20% | **10.42%** | 27.08% | **15%** | **3.00** | **33.05** |
| Top-5 | 35% | 20% | 7.14% | 27.08% | 20% | 5.00 | 46.35 |
| Relative-loss .50 | **45%** | 20% | 7.25% | 32.42% | 20% | 8.90 | 68.80 |
| Always BADP Top-3 δ=.005 | 35% | 20% | 8.18% | 27.08% | 20% | 4.25 | 45.65 |
| Always BADP Top-5 δ=.050 | **45%** | 20% | 5.95% | **34.08%** | 20% | 9.38 | 77.20 |

더 많은 후보를 유지하면 search success가 45%까지 올라가는 정책도 있었지만 비용이 매우 크게 증가했고 Retrieval F1은 Top-3보다 낮았다.

따라서 WebQSP에서는 Top-3가 비용과 F1 측면에서 여전히 강한 기준선이었다.

## 19.2 Conditional BADP 결과

| 정책 | Search Success | Retrieval F1 | Pruning Regret | Avg Width | Avg Expanded | Activation Rate |
|---|---:|---:|---:|---:|---:|---:|
| Top-3 | **35%** | **10.42%** | **15%** | **3.00** | **33.05** | — |
| Conditional Top-3 τ=.005, δ=.005 | 35% | 8.18% | 20% | 4.25 | 45.65 | 60.0% |
| Conditional Top-3 τ=.010, δ=.005 | 35% | 8.18% | 20% | 4.25 | 45.65 | 72.5% |
| Conditional Top-3 τ=.020, δ=.010 | 35% | 6.94% | 20% | 5.18 | 54.55 | 87.5% |
| Conditional Top-5 τ=.010, δ=.010 | 35% | 5.49% | 20% | 7.38 | 64.45 | 92.5% |
| Conditional Top-5 τ=.020, δ=.010 | 35% | 5.49% | 20% | 7.38 | 64.45 | 97.5% |

Conditional BADP는 이 n=20 WebQSP 설정에서 Top-3보다 search success를 높이지 못했고 비용과 Retrieval F1이 악화되었다.

또한 activation rate가 지나치게 높았다.

따라서 다음 두 문제를 분리해야 한다.

```text
문제 A: 경계 주변 후보를 추가 보존하면 도움이 되는가?
문제 B: 어떤 경계에서 추가 보존을 켜야 하는가?
```

WN18RR에서는 A에 긍정적인 신호가 있었지만 WebQSP에서는 단순한 `ΔK <= τ` 규칙이 B를 충분히 해결하지 못했다.

---

# 20. 코드 오류를 제외하고 실제로 확인된 성능 개선

아래 표는 **같은 지표 기준으로 baseline 대비 실제 증가가 확인된 결과**만 모은 것이다.

| 실험 | 기준선 | 개선 방법 | 같은 지표의 변화 | 주의점 |
|---|---|---|---|---|
| Controlled n=80 | Accuracy 75%, Macro F1 66.67% | Perspective Tableau | **100%, 100%** | 통제 논리 사례 |
| Explanation n=20 | Coverage 50% | Rashomon enumeration | **100%** | 설명 보존 지표 |
| MAGIC structured | Row recall 22.79% | DeBERTa scorer | **41.50%, +18.71%p** | 공식 자연어 MAGIC 점수 아님 |
| MAGIC structured | Query recall 16.86% | DeBERTa scorer | **31.53%, +14.68%p** | structured 진단 |
| MAGIC structured | Exact LOC 7.14% | DeBERTa scorer | **15.48%, +8.33%p** | structured 진단 |
| DAFNA n=100 | Exact 61% | PW marginal | **62%, +1%p** | truth selection |
| DAFNA n=100 | Author F1 82.88% | PW marginal | **84.13%, +1.25%p** | truth selection |
| WN18RR iterative n=10 | Success 60% | Relative-loss .50 | **70%, +10%p** | width 5.97로 증가 |
| MAGIC recoverable n=420 | Top-3 survival 94.76% | Boundary Top-3 δ=.01 | **97.86%, +3.10%p** | Gold F1은 감소 |
| MAGIC high-branching n=32 | Top-3 survival 37.50% | Boundary Top-3 δ=.01 | **78.13%, +40.63%p** | width 증가 |
| MAGIC high-branching n=32 | Top-5 survival 75.00% | Boundary Top-5 δ=.01 | **84.38%, +9.38%p** | width 증가 |
| WN18RR iterative n=20 | Top-3 success 50% | Boundary Top-3 δ=.005 | **55%, +5%p** | strict same-budget에서는 동률 |
| WN18RR iterative n=20 | Top-5 success 55% | Boundary Top-5 δ=.010 | **60%, +5%p** | 비용 증가 |
| WN18RR iterative n=20 | Top-5 success 55% | Boundary Top-5 δ=.050 | **65%, +10%p** | 비용·noise 크게 증가 |
| WN18RR iterative n=50 | Top-3 success 40% | Boundary Top-3 δ=.005 | **46%, +6%p** | Viability F1 소폭 감소 |
| WN18RR iterative n=50 | Top-3 regret 58% | Boundary Top-3 δ=.005 | **52%, -6%p** | 낮을수록 좋음 |
| WN18RR iterative n=50 | Top-5 success 56% | Boundary Top-5 δ=.010 | **60%, +4%p** | 비용 증가 |
| WN18RR iterative n=50 | Top-5 regret 42% | Boundary Top-5 δ=.010 | **38%, -4%p** | 낮을수록 좋음 |

WN18RR Frozen의 `Top-1 16%`와 `Rashomon coverage 42%`는 서로 다른 지표이므로 이 성능 개선표에는 넣지 않았다.

WebQSP Conditional BADP도 Top-3 대비 같은 search-success 지표가 개선되지 않았으므로 이 표에서 제외한다.

---

# 21. 현재까지 기각되거나 제한된 주장

연구에서는 성능이 오른 사례뿐 아니라 실패한 가설도 중요하다.

## 21.1 Possible Worlds가 자동으로 최종 정답을 해결한다

기각 또는 제한된다.

DAFNA에서 gold world coverage는 93%였지만 best exact selection은 62%였다.

Possible Worlds는 **후보 보존 구조**이지 자동 정답 선택기가 아니다.

## 21.2 Ontology/Tableau만으로 실제 다중 홉 관계 의미를 모두 해결할 수 있다

기각된다.

MAGIC multi-hop에서 path coverage는 68.03%였지만 ontology/Tableau conflict detection은 5.44%였다.

## 21.3 전역 Rashomon score band가 항상 Top-K보다 우수하다

기각된다.

Iterative WN18RR n=10에서 Global .05/.10은 Top-K 60%보다 낮은 40% success였다.

## 21.4 후보를 많이 남길수록 항상 좋다

기각된다.

MAGIC no-pruning은 survival 100%였지만 Gold F1은 63.64%로 낮았다.

## 21.5 BADP가 같은 비용에서 항상 Top-K보다 우수하다

아직 지지되지 않는다.

WN18RR n=20 strict nearest-width 비교에서는 success gain이 없었다.

## 21.6 Boundary margin 하나면 위험한 경계를 충분히 찾을 수 있다

현재로서는 지지되지 않는다.

WebQSP에서 activation rate가 최대 97.5%까지 올라가 Conditional BADP가 거의 always-on처럼 동작하였다.

---

# 22. 현재 연구에서 가장 강한 관찰

현재까지 가장 일관된 관찰은 세 가지다.

### 22.1 Branching이 큰 구간에서 fixed Top-K가 특히 취약하다

MAGIC high-branching subset에서 Top-3 gold-path survival은 37.50%까지 하락했다.

### 22.2 실제 Top-K 경계 주변을 제한적으로 보존하면 일부 환경에서 success/regret가 개선된다

WN18RR iterative n=20과 n=50에서 같은 방향이 반복되었다.

### 22.3 그러나 보존량을 늘릴수록 precision과 비용이 악화될 수 있다

따라서 최종 목적은 최대 survival이 아니다.

```text
좋은 정책 = 경로 보존 + 보존 집합의 유효성 + 탐색 비용
```

---

# 23. 현재 다음 가설: Boundary Risk

단순 boundary margin만 사용하는 대신 여러 위험 신호를 함께 보는 방향이 자연스럽다.

예를 들어 현재 고려 중인 변수는 다음과 같다.

- `ΔK`: K번째와 K+1번째 score margin
- `B`: branching factor
- score entropy: 후보 점수가 얼마나 퍼져 있는지
- boundary density: cutoff 주변에 후보가 얼마나 몰려 있는지
- depth: 현재 검색 깊이와 남은 hop budget

개념적으로 위험도를 다음처럼 둘 수 있다.

$$Risk_k=f(\Delta_K,B_k,Entropy_k,Density_k,Depth_k)$$

그 뒤:

```text
Risk가 높음  → BADP를 잠시 활성화
Risk가 낮음  → 기존 Top-K 유지
```

이 방향의 핵심은 단순 adaptive beam width가 아니다.

> **실제로 Pruning Regret가 발생할 가능성이 높은 비가역적 경계를 찾고, 그 순간에만 추가 탐색 비용을 쓰는 것**이 목적이다.

---

# 24. 재현 가능한 검증 실행

아래 run/artifact는 본 문서의 주요 숫자를 대조하는 기준이다.

| 실험 | GitHub Actions Run | Artifact |
|---|---:|---:|
| MAGIC Possible Worlds | 32725453943 | 9519356207 |
| MAGIC DeBERTa structured scoring 및 controlled/DAFNA 결과 묶음 | 32730398659 | 9521415589 |
| DAFNA Possible Worlds | 32726434311 | 9519739380 |
| WN18RR Frozen n=50 | 32799621678 | 9546119681 |
| WN18RR Relative-loss n=10 | 32813194834 | 9550550657 |
| MAGIC External Gold pruning | 32817516186 | 9551919328 |
| WN18RR Iterative budgeted n=20 | 32819877566 | 9553138233 |
| WebQSP Conditional BADP n=20 | 32829786375 | 9556981080 |
| WN18RR Conditional BADP n=50 수정 재실행 | **32852520635** | **9566776300** |

---

# 25. 최종 정리

처음부터 현재까지의 연구 발전을 가장 단순하게 표현하면 다음과 같다.

```text
1. 여러 설명을 너무 빨리 하나로 합치지 않는다.
2. Ontology가 모르는 관계는 후보로 예측한다.
3. Semantic scorer로 후보의 의미 적합도를 구분한다.
4. 후보 생성과 후보 선택은 별개 문제로 평가한다.
5. 좋은 후보가 검색 중 사라지는 Pruning Regret를 측정한다.
6. 모든 near-optimal 후보를 보존하는 것은 비용과 noise가 크다.
7. 실제 Top-K cutoff 주변만 보존하는 BADP를 사용한다.
8. BADP도 항상 켜지 않고 위험한 경계에서만 켜고 싶다.
9. 단순 margin 하나는 WebQSP에서 충분한 risk detector가 아니었다.
10. 다음 단계는 branching과 score distribution까지 포함한 Boundary Risk 추정이다.
```

현재 논문에서 가장 안전하게 주장할 수 있는 문장은 다음과 같다.

> **고정 Top-K는 다중 홉 검색의 비용을 안정적으로 제한하지만, 후보 경쟁이 큰 구간에서는 이후 정답 또는 증거로 이어질 수 있는 경로를 비가역적으로 제거할 수 있다. MAGIC과 WN18RR 실험에서는 Top-K 경계 주변 후보를 제한적으로 추가 보존했을 때 경로 생존 또는 search success가 개선되는 신호가 반복적으로 관찰되었다. 그러나 추가 보존은 precision과 비용을 악화시킬 수 있고 WebQSP에서는 단순 margin 기반 Conditional BADP가 개선되지 않았으므로, 현재 핵심 과제는 BADP를 언제 활성화할지를 더 정확하게 추정하는 것이다.**
