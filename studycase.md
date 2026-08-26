# 선행 Study Cases: MAGIC와 DAFNA-EA Books/Authors

## 1. 문서 목적과 범위

이 문서는 현재 진행 중인 RCA/OpenRCA 연구의 실행 로그가 아니다. **현재 연구에 앞서 수행했던 두 개의 독립적인 선행 실험 사례(MAGIC, DAFNA-EA Books/Authors)를 외부 독자가 처음부터 이해할 수 있도록 정리한 Study Case 문서**다.

문서의 목적은 다음 세 가지다.

1. 어떤 데이터에서 어떤 문제가 있었는지 설명한다.
2. 왜 `Rashomon / Possible Worlds`, `Tableau`, provenance, reliability 같은 개념을 실험하게 되었는지 설명한다.
3. 실제 측정 결과를 통해 무엇이 가능했고 무엇이 병목이었는지를 구분한다.

이 문서에는 observability log, OpenRCA, 장애 원인 분석 파이프라인, 현재 논문의 실험 결과를 포함하지 않는다. 그 내용은 별도의 `paper.md`에서 다룬다.

---

# 2. 전체 연구 흐름

두 Study Case의 공통 문제는 **여러 개의 그럴듯한 설명이나 주장이 동시에 존재할 때 너무 일찍 하나를 선택하면 정답을 잃을 수 있다**는 것이었다.

초기 연구 질문은 다음과 같이 발전했다.

```text
상충하는 사실/경로가 존재한다
        ↓
하나를 즉시 선택하면 정답 후보를 버릴 수 있다
        ↓
여러 해석을 Possible Worlds로 보존한다
        ↓
논리적으로 불가능한 world는 Tableau로 제거한다
        ↓
남은 world를 provenance / source reliability로 비교한다
        ↓
"정답 후보를 만드는 문제"와
"그 후보 중 정답을 고르는 문제"를 분리해서 평가한다
```

이 관점을 한 문장으로 요약하면 다음과 같다.

> **Preserve before Resolve — 판정하기 전에 가능한 설명을 충분히 보존한다.**

두 데이터셋은 이 명제를 서로 다른 방향에서 검증했다.

| Study Case | 주된 질문 | 입력의 불확실성 | 핵심 평가 |
|---|---|---|---|
| MAGIC | 다중 홉 상충 설명을 올바르게 구성·지역화할 수 있는가? | 관계 의미와 경로 해석 | conflict recall, gold-world recall, localization |
| DAFNA-EA Books/Authors | 여러 출처의 상충 저자 주장 중 실제 truth를 선택할 수 있는가? | 출처 신뢰도와 다중 값 truth | gold-world coverage, exact truth accuracy, Author F1 |

즉 MAGIC은 주로 **설명 world의 생성과 보존**, DAFNA는 주로 **보존된 world의 선택과 truth adjudication**을 검증한 사례다.

---

# 3. Study Case 1 — MAGIC 다중 홉 상충 추론

## 3.1 MAGIC에서 다룬 문제

MAGIC 계열 데이터는 하나의 짧은 사실만 비교하는 것이 아니라, 여러 관계를 거쳐야 상충 여부를 이해할 수 있는 multi-hop conflict를 포함한다.

개념적으로 다음과 같은 구조를 생각할 수 있다.

```text
Original evidence
A --r1--> B --r2--> C

Perturbed / conflicting evidence
A --r3--> D --r4--> C
```

여기서 단순히 `A`와 `C`가 연결되어 있다는 사실만으로는 두 경로가 같은 의미인지, 반대 의미인지, 서로 독립적인지 알 수 없다.

따라서 다음 세 개념을 구분해야 했다.

\[
Graph\ Reachability
\neq
Semantic\ Relation
\neq
Logical\ Contradiction
\]

- **Graph Reachability**: 두 엔티티가 어떤 경로로 연결되는가?
- **Semantic Relation**: 그 경로가 의미적으로 무엇을 뜻하는가?
- **Logical Contradiction**: 두 해석을 동시에 참이라고 둘 수 없는가?

이 구분이 MAGIC 실험의 출발점이었다.

## 3.2 실제 사용한 structured MAGIC 데이터

검증된 possible-world 실험에서는 released structured multi-hop subset의 **588 rows, 1,056 query conflicts**를 사용했다.

각 row에는 원래 사실 경로와 perturbation으로 생성된 상충 경로가 존재하며, 구현에서는 `original_triplet[i]`와 대응하는 `perturb_triplet[i]`가 동일한 conflict pair를 구성한다고 보았다.

중요한 점은 현재 선행 실험의 입력이 **자연어 문단을 그대로 LLM에 넣은 공식 MAGIC natural-language protocol이 아니라 structured triplet 표현**이라는 것이다.

따라서 아래에 제시하는 `row conflict recall`, `query conflict recall`, `structured exact localization`은 공식 MAGIC ID/LOC와 동일한 점수가 아니다.

## 3.3 첫 접근 — hard ontology + Tableau

초기에는 관계의 inverse, symmetric, exclusive, disjoint 등 의미를 ontology에 정의하고, 두 경로를 하나의 논리 체계에 넣은 뒤 Tableau를 이용해 충돌 여부를 확인했다.

개념적으로는 다음과 같다.

\[
O \cup C \cup \{q, \neg q\}
\]

에 대해 Tableau가 branch를 모두 닫으면 contradiction으로 판단한다.

이 접근의 장점은 판정 근거가 명시적이라는 점이었다. 그러나 실제 multi-hop 데이터에서는 필요한 관계 합성 의미가 ontology에 모두 존재하지 않았다.

예를 들어

\[
r_1(A,B) \land r_2(B,C)
\]

가 관찰되어도 ontology에

\[
r_1 \circ r_2 \Rightarrow r_3
\]

가 정의되어 있지 않으면 Tableau는 `A`와 `C` 사이의 의미를 새로 만들어내지 못한다.

### 검증 결과

선행 bidirectional-Tableau 진단 실험은 다음과 같았다.

| 진단 지표 | 결과 |
|---|---:|
| Direct heuristic detection | 33.16% |
| Bidirectional candidate-path coverage | **68.03%** |
| Strict ontology/Tableau contradiction | **5.44%** |

이 세 숫자는 서로 다른 지표다. 특히 **68.03%는 정확도가 아니라 candidate path coverage**이며, 5.44%는 hard ontology로 실제 contradiction까지 닫을 수 있었던 row 수준 진단이다.

이 결과에서 가장 중요한 것은 68.03%와 5.44% 사이의 격차였다.

> 경로는 찾았지만, 그 경로가 의미적으로 무엇을 뜻하는지 hard ontology만으로는 닫지 못했다.

따라서 문제를 “더 많은 ontology rule을 손으로 넣자”로 해결하지 않고, **불확실한 관계 해석 자체를 후보 변수로 유지**하는 방향으로 바꾸었다.

---

# 4. MAGIC Possible Worlds — 하나의 해석을 강제로 고르지 않기

## 4.1 Possible World의 의미

한 경로에 대해 의미 해석이 하나로 확정되지 않는다면 다음처럼 여러 가설을 둘 수 있다.

\[
H_1: r_1 \circ r_2 \Rightarrow q
\]

\[
H_2: r_1 \circ r_2 \Rightarrow \neg q
\]

\[
H_3: unresolved
\]

각 선택을 하나의 possible world로 분리한다.

\[
W=(C,S,R,D)
\]

- `C`: 해당 world에서 채택한 claim 집합
- `S`: claim의 source/provenance
- `R`: 선택된 relation interpretation
- `D`: 해당 claim을 만든 derivation/proof

후보 world가 내부적으로 명백한 논리 충돌을 만들면 Tableau로 제거한다.

\[
Tableau(W)=SAT
\]

인 world만 다음 단계에 남긴다.

이 방식의 핵심은 uncertain relation을 hard ontology axiom으로 승격하지 않는 것이다. relation interpretation은 **defeasible hypothesis**이며, 다른 해석과 경쟁할 수 있다.

## 4.2 MAGIC에서 무엇을 따로 측정했는가

이 실험에서는 두 질문을 구분했다.

### 질문 A — 정답 설명을 후보 집합 안에 보존했는가?

이를 `Gold-world query recall`로 보았다.

### 질문 B — 보존한 후보 중 실제로 올바른 설명을 최종 선택했는가?

이를 row/query conflict recall과 structured exact localization으로 진단했다.

이 두 값을 분리해야 “후보 생성 실패”와 “후보 랭킹 실패”를 구별할 수 있다.

## 4.3 검증된 MAGIC 결과

검증 workflow: `32725453943`  
검증 artifact: `9519356207`

| Variant | Row conflict recall | Query conflict recall | Gold-world query recall | Structured row exact LOC |
|---|---:|---:|---:|---:|
| B1 Static Tableau | **5.44%** | 4.45% | — | — |
| B2 Early-commit single world | **29.93%** | 22.63% | — | — |
| B3 Possible-world retention | — | — | **39.39%** | **29.42%** |
| B4 Weakly weighted worlds | **22.79%** | 16.86% | — | **7.14%** |

평균적으로 query당 candidate path는 1.46개, retained world는 4.10개였고 row당 7.36개의 world가 유지되었다.

## 4.4 결과가 의미하는 것

가장 중요한 수치는 다음 두 값의 차이다.

\[
GoldWorldRecall=39.39\%
\]

\[
SelectedExactLocalization=7.14\%
\]

즉 possible-world 구조는 static Tableau보다 훨씬 많은 올바른 상충 설명을 **후보 안에 보존**했지만, 약한 lexical/relation prior로는 그중 올바른 world를 잘 **선택하지 못했다**.

이 결과는 다음을 보여줬다.

> Possible Worlds는 정답을 자동으로 맞히는 기법이 아니라, 정답 후보가 조기에 사라지는 것을 줄이는 representation이다.

따라서 이후 병목은 world generation 자체보다 world ranking으로 이동했다.

---

# 5. MAGIC Semantic Scoring 실험

## 5.1 왜 의미 scorer가 필요했는가

B4의 weak weighting은 relation 이름이나 얕은 lexical signal을 이용했기 때문에, 문맥상 더 그럴듯한 causal/contradictory interpretation을 충분히 구별하지 못했다.

동일한 candidate generation을 유지하고 scorer만 의미 기반 NLI로 교체하여 이 영향을 확인했다.

사용 모델:

`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`

이 단계에서 DeBERTa는 새로운 relation을 생성하는 모델이 아니라 **이미 생성된 candidate interpretation의 의미 적합도를 점수화하는 모듈**이었다.

## 5.2 측정 결과

| 지표 | Weak lexical | DeBERTa | 변화 |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71%p** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68%p** |
| Structured exact localization | 7.14% | **15.48%** | **+8.34%p** |

이 실험의 해석은 제한적이어야 한다.

- DeBERTa가 MAGIC 전체 문제를 해결했다는 뜻이 아니다.
- structured input에서 동일 후보들의 ranking이 lexical scorer보다 개선되었다는 뜻이다.
- 공식 natural-language MAGIC ID/LOC와 직접 비교할 수 없다.

### 구현 과정에서 확인한 주의점

초기 자연어 실험 일부에서는 scorer 입력에 proposition 자체가 아닌 provenance metadata가 섞인 문제가 있었다.

```text
[source=context1, sentence=...]
[source=context2, sentence=...]
```

이런 metadata는 NLI가 판단해야 할 의미가 아니라 audit 정보다. 이후 scorer 입력에서는 자연어 proposition/triple과 provenance metadata를 분리하였다.

따라서 해당 수정 전의 자연어 MAGIC 결과는 이 문서의 검증 성능으로 사용하지 않는다.

---

# 6. Study Case 2 — DAFNA-EA Books / AuthorsNamesList

## 6.1 MAGIC과 다른 문제

MAGIC이 “올바른 설명 경로를 만들고 보존할 수 있는가?”를 검증했다면, DAFNA-EA Books는 다음 질문을 검증하기 위해 사용했다.

> 같은 책에 대해 여러 출처가 서로 다른 저자 목록을 주장할 때, 가능한 truth 후보를 보존한 뒤 어떤 저자 집합이 실제 truth인지 선택할 수 있는가?

즉 DAFNA는 전형적인 **multi-source truth discovery** 문제다.

## 6.2 데이터 구조

검증 실험에서는 repository의 기존 direct comparison과 동일한 `AuthorsNamesList` **100-book gold subset**을 사용했다.

실험 데이터의 규모는 다음과 같다.

- Gold books: **100**
- Collapsed source-object claims: **1,999**
- Distinct sources: **227**
- 평가 시 person normalization: surname + first initial 기반의 공통 benchmark normalization

한 개의 book object에 대해 여러 source가 서로 다른 author set을 주장하는 형태다.

개념적인 예시는 다음과 같다.

```text
Book X
  Source A -> {Alice Smith, Bob Lee}
  Source B -> {Alice Smith}
  Source C -> {A. Smith, Robert Lee}
  Source D -> {Alice Smith, Carol Kim}
```

이때 단순 majority voting은 항상 적합하지 않다.

- 한 출처가 공동 저자 한 명을 누락할 수 있다.
- 이름 표기가 서로 다를 수 있다.
- 여러 출처가 같은 잘못된 값을 복제했을 수 있다.
- source마다 신뢰도가 다를 수 있다.
- truth 자체가 단일 값이 아니라 **저자 집합(set)** 이다.

따라서 `누가 더 많이 말했다`뿐 아니라 `어떤 저자 조합이 가능한 truth world인지`, `그 world를 지지하는 출처의 reliability가 어떤지`를 함께 보게 되었다.

---

# 7. DAFNA에서 Truth World를 만드는 방법

## 7.1 후보 world 생성

각 book에 대한 possible truth world는 gold를 보지 않고 다음 정보만으로 생성했다.

1. 실제 관찰된 author set 전체
2. source support가 높은 상위 12개 atomic author
3. 이 atomic author들의 bounded combination
4. 최대 cardinality는 관찰된 claim 중 가장 큰 author set 크기 이하
5. object당 최대 **256 candidate worlds**

예를 들어 관찰된 claim이 다음과 같다면

```text
{A, B}
{A}
{A, C}
```

candidate space에는 관찰 claim뿐 아니라 제한된 조합 조건을 만족하는

```text
{A}
{B}
{C}
{A,B}
{A,C}
{B,C}
...
```

같은 truth hypothesis가 포함될 수 있다.

Gold truth는 candidate generation이나 scoring에 사용하지 않고 마지막 evaluation에서만 사용했다.

## 7.2 왜 누락된 공동 저자를 바로 contradiction으로 보지 않았는가

출처가 `{A}`라고 주장하고 candidate world가 `{A,B}`라고 해서 Source가 반드시 `B는 저자가 아니다`라고 주장한 것은 아니다. 단순 누락일 수도 있다.

따라서 compatibility는 overlap을 보상하고 omitted co-author를 완전한 contradiction보다 약한 negative evidence로 처리했다.

기본 world evidence는 다음과 같이 두었다.

\[
Evidence(W)=0.8\cdot Compatibility(W)+0.2\cdot ExactSupport(W)
\]

이 점수를 softmax하여 world posterior를 구성했다.

---

# 8. Early Commit과 Delayed Commitment

DAFNA 실험의 핵심 ablation은 candidate 생성기가 아니라 **source reliability를 언제 업데이트하느냐**였다.

동일한 candidate world 집합에 대해 세 방식을 비교했다.

### Uniform

모든 source를 같은 reliability로 본다.

### Hard Commit

현재 가장 높은 MAP world 하나를 먼저 선택하고, 해당 world와 source claim의 일치 여부를 기준으로 source reliability를 업데이트한다.

```text
candidate worlds
    ↓
현재 1등 world 선택
    ↓
그 world를 기준으로 source reliability 갱신
```

문제는 초기 1등 world가 틀리면 reliability까지 그 오류를 따라갈 수 있다는 점이다.

### Marginal Reliability

하나의 world에 먼저 고정하지 않고 posterior 전체에 대한 기대 compatibility로 source reliability를 업데이트한다.

\[
Rel(s) \leftarrow E_{W\sim P(W)}[Compat(c_s,W)]
\]

즉 여러 plausible truth를 유지한 상태에서 source가 전체 후보 분포와 얼마나 일관적인지를 본다.

이것이 DAFNA Study Case에서의 **delayed commitment** 실험이다.

---

# 9. DAFNA 결과

검증 workflow: `32726434311`  
검증 artifact: `9519739380`

## 9.1 Candidate generation

- Gold-world coverage: **93.00%**
- 평균 candidate worlds/book: **27.94**
- object당 최대 worlds: **256**

즉 100개의 gold book 중 93개는 정답 author set이 candidate space 안에 존재했다.

이 값은 최종 정확도와 다르다. `93% coverage`는 **정답을 고를 기회가 있었다**는 뜻이다.

## 9.2 Truth selection

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds — Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds — Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds — Uniform | 58.00% | 80.38% |
| TruthFinder (official DAFNA-EA implementation) | 57.00% | 66.85% |
| AccuSim (official DAFNA-EA implementation) | 57.00% | 66.18% |
| 2-Estimates | 54.00% | 65.28% |
| 3-Estimates | 53.00% | 65.45% |
| Accu | 53.00% | 65.45% |

동일 candidate generation을 사용하는 Hard Commit과 Marginal Reliability만 비교하면:

- Exact Truth Accuracy: **61% → 62% (+1.00%p)**
- Author F1: **84.04% → 84.13% (+0.09%p)**

Prior Atomic 대비 Marginal Reliability는:

- Exact: **+1.00%p**
- Author F1: **+1.25%p**

Official TruthFinder/AccuSim 대비 exact accuracy는 해당 100-book 동일 평가에서 **+5.00%p**였다.

이 결과를 전체 DAFNA에 대한 SOTA 주장으로 해석하지 않는다. 검증된 주장은 이 100-book AuthorsNamesList subset에 한정된다.

---

# 10. DAFNA에서 가장 중요한 관찰

DAFNA의 핵심은 최고 정확도 62% 자체보다 다음 격차였다.

\[
GoldWorldCoverage=93\%
\]

\[
ExactTruthSelection=62\%
\]

즉 candidate generator는 93%의 object에서 gold truth를 포함했지만, 실제 ranking/scoring은 그중 상당수를 최종 정답으로 선택하지 못했다.

따라서 실패 원인을 다음처럼 분해할 수 있었다.

```text
Case A: Gold world가 candidate에 없음
        -> generation 문제

Case B: Gold world가 candidate에 있음
        but 다른 world가 더 높은 점수
        -> ranking / calibration 문제
```

이 분해는 이후 연구 설계에서 매우 중요해졌다. 최종 정확도 하나만 보면 **왜 틀렸는지 알 수 없기 때문**이다.

---

# 11. MAGIC과 DAFNA를 함께 보면 무엇을 배웠는가

두 Study Case의 결과는 같은 패턴을 보여줬다.

## 11.1 MAGIC

\[
39.39\%\ GoldWorldRecall
\rightarrow
7.14\%\ WeakWeightedExactLOC
\]

정답 설명을 후보에 보존하는 능력과 최종 선택 능력 사이에 큰 차이가 있었다.

## 11.2 DAFNA

\[
93\%\ GoldWorldCoverage
\rightarrow
62\%\ ExactTruthAccuracy
\]

마찬가지로 정답 truth를 후보에 포함하는 능력과 선택하는 능력이 달랐다.

## 11.3 공통 결론

따라서 다음 관계를 명확히 구분하게 되었다.

\[
Candidate\ Generation
\neq
Candidate\ Preservation
\neq
Candidate\ Ranking
\neq
Final\ Decision
\]

그리고 possible-world/Rashomon 관점의 가장 중요한 역할은 **많이 생성하는 것** 자체가 아니라 다음이었다.

> **서로 경쟁 가능한 합리적 후보가 존재할 때, 충분한 근거 없이 하나를 너무 일찍 제거하지 않는다.**

---

# 12. Tableau의 역할을 어떻게 이해하게 되었는가

선행 실험 초기에 Tableau를 contradiction detector의 중심으로 보았지만, MAGIC 결과를 통해 역할의 한계가 분명해졌다.

Tableau가 잘하는 일:

- 주어진 logical axiom 하에서 consistency/SAT 검사
- 명시적 contradiction이 있는 world 제거
- proof provenance를 설명 가능한 형태로 유지

Tableau가 하지 못하는 일:

- ontology에 없는 relation semantics 생성
- noisy evidence를 확률적으로 calibration
- source reliability 추정
- 여러 plausible world 중 가장 현실적인 world 자동 선택

즉 Tableau는 **candidate generator나 ranker가 아니라 hard logical validator**로 이해하는 것이 적절했다.

---

# 13. Rashomon / Possible Worlds의 역할

이 선행 연구에서 Rashomon이라는 표현은 “정답이 무조건 여러 개다”라는 뜻이 아니다.

관측된 evidence만으로 여러 설명이 비슷하게 plausible하다면

\[
\mathcal{W}_{\epsilon}
=
\{W_i \mid Score(W_i) \ge Score(W^*)-\epsilon\}
\]

와 같이 near-optimal explanation set을 유지하자는 원칙에 가깝다.

이때 최종 시스템은 여전히 하나의 truth나 explanation을 선택할 수 있다. 다만 그 선택 전에 alternative가 어떤 것이었고 왜 탈락했는지를 추적할 수 있다.

따라서 Possible Worlds를 사용한 이유는 단순 ensemble 효과가 아니라 **premature commitment를 줄이고 uncertainty/provenance를 보존하기 위해서**였다.

---

# 14. 두 Study Case의 성과와 한계

| 항목 | MAGIC | DAFNA-EA Books/Authors |
|---|---|---|
| 데이터 성격 | multi-hop conflict | multi-source truth discovery |
| 주된 불확실성 | relation/path interpretation | source reliability + multi-valued truth |
| 정답 후보 보존 | Gold-world query recall 39.39% | Gold-world coverage 93% |
| 최종 선택 | weak weighted exact LOC 7.14%; semantic scorer에서 개선 | marginal exact truth 62% |
| 핵심 병목 | world relation ranking | truth-world ranking/calibration |
| 논리 검증 역할 | Tableau SAT filtering | candidate truth consistency 보조 |
| 가장 중요한 교훈 | path 존재와 semantic contradiction은 다름 | candidate coverage와 final accuracy는 다름 |

공통적으로 확인한 것은 다음이다.

1. hard rule만으로 모든 실제 의미를 표현하기 어렵다.
2. 정답 후보가 존재한다고 최종 정답을 맞히는 것은 아니다.
3. candidate generation과 ranking은 반드시 별도 지표로 평가해야 한다.
4. 여러 후보를 유지할 때 provenance와 source/evidence quality가 중요하다.
5. 논리 일관성과 현실적 plausibility는 서로 다른 신호다.

---

# 15. 수치 해석 시 주의사항

이 문서의 결과를 읽을 때 다음 경계를 유지해야 한다.

### MAGIC

- 588-row / 1,056-query structured experiment다.
- `Structured row exact LOC`는 공식 자연어 MAGIC LOC와 동일하지 않다.
- 자연어 LLM peer의 ID/LOC와 이 structured 결과를 직접 leaderboard처럼 비교하면 안 된다.
- 수정 이전 scorer/provenance 오류가 포함된 자연어 실행 값은 최종 성능 근거에서 제외한다.

### DAFNA

- `AuthorsNamesList` 100-book gold subset 결과다.
- 1,999 source-object claims와 227 sources를 공통 normalization으로 평가했다.
- official DAFNA-EA Java baseline을 같은 normalized gold comparison으로 재평가한 결과다.
- 62% exact를 전체 DAFNA나 모든 truth-discovery 데이터에 대한 SOTA로 주장하지 않는다.

---

# 16. Study Case 요약

MAGIC에서는 **정답 conflict explanation을 후보 world로 보존하는 문제**를 주로 다뤘다. Static Tableau가 strict contradiction으로 닫은 범위는 제한적이었고, Possible Worlds는 더 많은 gold explanation을 보존했다. 그러나 weak ranking에서 그 이점이 최종 선택으로 이어지지 않아 semantic/world ranking이 별도 문제임을 확인했다.

DAFNA-EA Books/Authors에서는 **정답 truth world를 만들어 놓은 뒤 실제로 올바른 world를 선택할 수 있는가**를 다뤘다. 93% gold-world coverage에도 exact truth는 62%였으며, marginal reliability가 hard early commitment보다 작지만 일관된 개선을 보였다.

두 실험을 통해 얻은 가장 중요한 선행 결론은 다음이다.

> **설명 또는 truth의 후보를 생성하는 단계와, 그 후보를 보존하는 단계, 점수화하는 단계, 최종 판정하는 단계는 서로 다른 문제이며 반드시 분리해서 평가해야 한다.**

이 문서는 여기서 종료한다. 이후의 observability/RCA/OpenRCA 연구는 이 Study Case의 범위에 포함하지 않는다.