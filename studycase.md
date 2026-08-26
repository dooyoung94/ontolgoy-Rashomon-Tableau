# 연구 아이디어와 실험의 발전 기록

## 0. 문서 목적

이 문서는 특정 최종 방법을 정당화하기 위한 문서가 아니라, **연구가 어떤 문제의식에서 시작했고, 어떤 실험을 통해 가설이 강화·수정·폐기되었는지**를 시간 순서와 문제 구조에 따라 정리한 연구 기록이다.

현재까지의 연구는 크게 다음 질문을 따라 발전했다.

```text
서로 상충하지만 각각은 그럴듯한 여러 설명이 있을 때
왜 하나를 너무 일찍 선택해야 하는가?
        ↓
여러 설명을 동시에 보존할 수 있는가?
        ↓
논리적으로 불가능한 설명은 제거할 수 있는가?
        ↓
좋은 설명이 후보 안에 있어도 최종 선택이 틀리는 이유는 무엇인가?
        ↓
좋은 후보가 ranking 또는 pruning에서 사라지는가?
        ↓
어떤 scorer / selection rule / search policy가 실제 병목인가?
```

중요한 점은 **Rashomon Worlds, Tableau, BADP 중 어느 하나를 최종 방법으로 미리 고정하지 않는 것**이다.

현재까지 가장 일관되게 남은 연구 문제는 다음과 같다.

> **불완전하고 상충하는 multi-hop evidence 환경에서 유효한 대안 설명을 너무 일찍 제거하지 않으면서, 최종적으로는 올바른 설명 또는 상충 근거를 선택하는 방법은 무엇인가?**

Possible Worlds는 이 문제를 구현하는 하나의 표현 방식이고, Tableau는 논리 제약을 적용하는 하나의 verifier이며, BADP는 탐색 중 후보 손실을 줄이기 위해 검토한 pruning 정책이다. 연구의 핵심은 이 개별 기법의 이름보다 **delayed commitment, alternative preservation, logical consistency, evidence-aware adjudication**에 있다.

---

# 1. 초기 연구 문제

## 1.1 출발점: 상충을 하나로 합치면 정보가 사라진다

초기 문제의식은 단순했다.

두 출처 또는 두 관점이 서로 다른 사실을 말할 때 이를 처음부터 하나의 사실 집합으로 합쳐버리면 다음 문제가 발생한다.

```text
Perspective A: p
Perspective B: not p
```

이를 하나의 merged state로만 보면 즉시 contradiction으로 처리할 수 있지만, 실제로는 다음 가능성이 남아 있을 수 있다.

```text
A만 신뢰 가능한 world
B만 신뢰 가능한 world
A와 B가 서로 다른 scope를 말하는 world
relation mapping이 다른 world
추가 evidence가 들어오기 전에는 결정할 수 없는 world
```

따라서 초기 연구 질문은 다음과 같았다.

> **서로 경쟁하는 해석을 하나로 조기 확정하지 않고, 각각의 일관된 설명을 유지한 뒤 나중에 판별하면 더 많은 유효 설명과 상충 근거를 보존할 수 있는가?**

이 질문에서 Rashomon set과 Possible Worlds 아이디어가 등장했다.

## 1.2 초기 연구 가설

초기 연구 방향은 세 가지 가설로 정리할 수 있다.

### H1. Alternative Preservation

여러 가능한 해석을 유지하면 single-world 또는 merged reasoning보다 **유효한 설명의 coverage**가 높아질 것이다.

### H2. Delayed Commitment

초기 단계에서 하나의 해석만 선택하는 early commitment보다, 추가 evidence가 들어올 때까지 결정을 늦추는 것이 **viable explanation loss**를 줄일 것이다.

### H3. Evidence-aware Adjudication

후보를 많이 보존하는 것만으로는 충분하지 않으며, 같은 candidate space에서도 **scorer / ranking / adjudication 방식**에 따라 최종 성능이 크게 달라질 것이다.

이 세 가설은 이후 실험의 대부분을 관통한다.

---

# 2. 초기 구조: Rashomon + Tableau

초기 구현 아이디어는 다음과 같았다.

```text
Natural-language / structured evidence
        ↓
Atomic claims
        ↓
Source / perspective separation
        ↓
Multiple candidate interpretations
        ↓
Possible Worlds
        ↓
Tableau SAT / UNSAT validation
        ↓
Valid worlds only
        ↓
Evidence / provenance based ranking
        ↓
Conflict / truth / localization
```

여기서 역할은 명확히 분리하였다.

| 모듈 | 역할 |
|---|---|
| Claim extraction | 자연어를 atomic relation으로 변환 |
| Possible Worlds | 경쟁하는 여러 설명을 동시에 표현 |
| Tableau | 논리적으로 공존할 수 없는 world 제거 |
| Provenance | 어떤 source / sentence / path에서 나온 설명인지 기록 |
| Scorer | 남은 candidate의 의미적 적합도 판단 |
| Adjudication | 최종 conflict / truth / localization 결정 |

초기에는 Possible Worlds와 Tableau 자체가 핵심일 것이라 생각했지만, 이후 실험에서 **candidate construction보다 ranking과 scoring이 더 큰 병목일 수 있음**이 반복적으로 나타났다.

---

# 3. 첫 번째 검증: 논리 구조 자체가 동작하는가

자연어 benchmark를 바로 사용하면 실패 원인이 extraction인지 reasoner인지 구분하기 어렵다. 그래서 먼저 입력 relation과 contradiction scope를 완전히 통제하는 synthetic 실험을 사용하였다.

## 3.1 Synthetic Controlled Scope n=80

네 종류의 상황을 만들었다.

```text
consistent
perspective divergence
intra-perspective contradiction
inter-perspective contradiction
```

결과는 다음과 같다.

| 방법 | Accuracy | Macro F1 |
|---|---:|---:|
| Vanilla merged Tableau | 75.00% | 66.67% |
| Perspective Tableau | **100.00%** | **100.00%** |
| Rashomon Tableau | **100.00%** | **100.00%** |

이 결과에서 확인된 것은 자연어 일반화 성능이 아니라 다음 한 가지다.

> **관점이 분리된 상태에서 contradiction scope를 구분하는 논리 구조는 merged reasoning보다 정확하게 동작한다.**

Rashomon 방식은 이 class accuracy에서는 Perspective Tableau보다 추가 개선을 만들지 않았다.

## 3.2 Explanation Coverage n=20

한 사례에 복수의 최소 contradiction explanation이 존재하도록 만든 통제 실험에서는 다음 결과가 나왔다.

| 방법 | Explanation Coverage |
|---|---:|
| Single-path | 50% |
| Multi-explanation / Rashomon enumeration | **100%** |

이 결과는 초기 H1과 직접 연결된다.

> **여러 설명을 동시에 유지하는 구조의 첫 번째 장점은 최종 class accuracy보다 explanation coverage였다.**

---

# 4. CONAN은 어디에 위치하는가

CONAN은 초기 연구에서 perspective와 secret/inferred relation이 실제 narrative에서도 중요한 문제라는 점을 확인하는 데 사용하였다.

그러나 현재 저장소의 `100%` 결과는 공식 CONAN natural-language benchmark 성능이 아니다.

정확한 구분은 다음과 같다.

| 항목 | 실제 의미 |
|---|---|
| CONAN-derived controlled verification 100% | CONAN gold relation을 재료로 우리가 만든 reasoner 단위검증 |
| Synthetic 75% → 100% | 완전 합성 contradiction-scope 실험 |
| 공식 CONAN end-to-end 성능 | 현재 우리 방법의 검증 artifact 없음 |

따라서 CONAN은 현재 연구에서 **주요 성능 benchmark가 아니라 초기 문제 설정과 relation inventory를 제공한 참고 데이터**로만 취급한다.

이 문서에서는 이후 CONAN을 성능 근거로 사용하지 않는다.

---

# 5. 첫 번째 실제 한계: Graph path가 있어도 의미를 모른다

실제 multi-hop 데이터로 넘어가면서 초기 구조의 첫 번째 한계가 드러났다.

```text
Graph Reachability
≠ Semantic Relation
≠ Logical Contradiction
```

예를 들어 다음 path가 존재한다고 하자.

```text
h --r1--> e1 --r2--> e2 --r3--> t
```

그래프는 `h`에서 `t`까지 연결된다는 사실만 알려준다. 하지만 이 전체 path가 어떤 직접 relation을 의미하는지, query를 support하는지 contradiction하는지는 별도 semantic inference가 필요하다.

Structured MAGIC의 초기 진단에서 다음 차이가 관찰되었다.

| 지표 | 결과 |
|---|---:|
| Legacy multi-hop direct detection | 33.16% |
| Bidirectional candidate-path coverage | **68.03%** |
| Static Ontology/Tableau conflict detection | **5.44%** |

핵심은 다음과 같다.

> **경로를 찾는 것과 경로의 의미를 해석하는 것은 다른 문제였다.**

이 시점부터 Ontology/Tableau는 relation을 생성하는 주체가 아니라 **constraint verifier**로 역할이 축소되기 시작했다.

---

# 6. 두 번째 연구 단계: Candidate Construction과 Selection 분리

이후 구조를 다음 세 문제로 나누었다.

```text
1. Candidate Construction
   좋은 설명 / relation / path / world를 후보 안에 넣었는가?

2. Candidate Validation
   논리적으로 불가능한 후보를 제거했는가?

3. Candidate Selection
   살아남은 후보 중 올바른 것을 선택했는가?
```

이 분리는 이후 가장 중요한 연구 설계가 되었다.

특히 다음 두 값을 혼동하지 않도록 하였다.

```text
Candidate Coverage ≠ Final Accuracy
```

좋은 후보가 후보 집합 안에 존재하는 것과, 그 후보를 최종적으로 선택하는 것은 전혀 다른 문제다.

---

# 7. Structured MAGIC: Possible Worlds의 실제 역할

Structured MAGIC에서 588 rows, 1,056 query conflicts를 대상으로 candidate construction과 final selection을 분리해서 보았다.

이 수치는 공식 natural-language MAGIC ID/LOC가 아니라 **structured triplet diagnostic**이다.

## 7.1 주요 결과

| 방법 | Row conflict recall | Query conflict recall | Gold-world retention / coverage | Structured exact LOC |
|---|---:|---:|---:|---:|
| Static Tableau | 5.44% | 4.45% | — | — |
| Early-commit | 29.93% | 22.63% | — | — |
| Possible-world retention | — | — | Query 39.39% / Row exact 29.42% | — |
| Weak lexical weighted worlds | 22.79% | 16.86% | — | 7.14% |

평균 candidate 규모는 대략 다음이었다.

```text
candidate paths / query ≈ 1.45
worlds / query          ≈ 4.10
```

이 실험에서 중요한 것은 Possible Worlds라는 이름이 아니라 다음 관찰이다.

> **좋은 설명을 여러 개 보존하면 candidate coverage는 올라갈 수 있지만, weak scorer를 사용하면 최종 선택 성능은 오히려 낮을 수 있다.**

즉 H1은 일부 지지되었지만 H3가 더 중요한 문제로 떠올랐다.

---

# 8. Semantic Scoring: 같은 후보라도 scorer가 바뀌면 결과가 달라진다

Weak lexical weighting 대신 `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`를 discriminative NLI scorer로 사용하였다.

DeBERTa는 LLM generator가 아니라 **candidate evidence와 query 사이의 support / contradiction / unresolved를 판별하는 scorer**다.

## 8.1 Structured MAGIC 결과

| 지표 | Weak lexical | DeBERTa | 변화 |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.70%p** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68%p** |
| Structured exact LOC | 7.14% | **15.48%** | **+8.33%p** |
| Query gold-path selection | — | 22.06% | 참고 |

이 결과는 candidate construction을 바꾸지 않고 scorer를 바꿨을 때 얻은 변화라는 점이 중요하다.

따라서 현재까지 가장 강한 초기 결론 중 하나는 다음이다.

> **Multi-hop conflict reasoning의 주요 병목 중 하나는 candidate generation 자체보다 candidate ranking / scoring일 수 있다.**

---

# 9. DAFNA: 후보 coverage가 높아도 최종 truth selection은 어렵다

DAFNA-EA Books 100 gold-book subset에서 다음을 확인하였다.

```text
gold books = 100
claims     = 1,999
sources    = 227
```

Candidate truth-world coverage는 **93%**였다.

그러나 최종 결과는:

| 방법 | Exact-set Accuracy | Author F1 |
|---|---:|---:|
| Uniform worlds | 58% | 80.38% |
| Hard commit | 61% | 84.04% |
| Marginal reliability | **62%** | **84.13%** |
| Prior atomic | 61% | 82.88% |
| TruthFinder | 57% | 66.85% |
| AccuSim | 57% | 66.18% |

이었다.

가장 중요한 차이는:

```text
Candidate coverage = 93%
Best final exact   = 62%
```

이다.

즉 MAGIC과 DAFNA 모두 같은 방향을 가리켰다.

> **좋은 후보를 만드는 문제와 좋은 후보를 고르는 문제는 분리해야 한다.**

---

# 10. 세 번째 연구 분기: 좋은 후보가 pruning에서 사라지는가

Candidate selection을 살펴보는 과정에서 별도의 질문이 생겼다.

```text
좋은 후보가 애초에 생성되지 않았는가?
        vs
좋은 후보가 생성되었지만 중간 pruning에서 제거되었는가?
```

이 문제를 보기 위해 WN18RR과 MAGIC external gold를 사용해 **Pruning Regret**를 정의하였다.

```text
Pruning Regret =
pruning 전에는 viable / gold path가 존재했지만
pruning 후에는 모두 사라진 사건
```

이 시기의 목적은 Rashomon Worlds를 검증하는 것이 아니라 **delayed commitment가 search 단계에서도 필요한가**를 확인하는 것이었다.

---

# 11. Near-optimal Preservation 실험

## 11.1 WN18RR Frozen n=50

단일 Top-1 relation accuracy는 **16%**였지만, near-optimal candidate set 안에 gold relation이 포함되는 coverage는 **42%**였다.

```text
Top-1 accuracy       = 16%
Candidate coverage   = 42%
```

이 두 값은 같은 metric이 아니다.

이 실험은 다음 가능성을 보여주었다.

> **단일 선택은 틀렸더라도 gold candidate가 근처에 살아 있는 경우가 존재한다.**

그러나 Tableau filtering 후 최종 Top-1은 그대로 16%였기 때문에, 단순 보존만으로 final selection 문제는 해결되지 않았다.

## 11.2 WN18RR Iterative

Global additive near-optimal band는 iterative search에서 Top-K보다 오히려 나빴다.

따라서 다음 가설은 폐기하였다.

> 최고점 주변 후보를 전역적으로 많이 보존하면 일반적으로 Top-K보다 좋다.

Relative-loss .50은 n=10에서 success 60% → 70%를 보였지만 width와 expansion 비용이 증가하였다.

이 시점부터 **보존량 자체가 아니라 어디서 delayed pruning을 해야 하는가**가 중요해졌다.

---

# 12. BADP: Boundary-Aware Delayed Pruning

BADP는 이 문제를 해결하기 위해 검토한 하나의 search policy다.

기본 아이디어는 다음과 같다.

```text
Top-K 자체는 유지
+
K번째와 K+1번째가 거의 동점일 때만
cutoff 바로 아래 후보를 추가 보존
```

즉 global near-optimal set이 아니라 실제 제거가 일어나는 **Top-K boundary**를 본다.

## 12.1 MAGIC external gold

Recoverable query n=420에서:

| 정책 | Gold Path Survival | Gold F1 | Avg Width |
|---|---:|---:|---:|
| Top-3 | 94.76% | **73.01%** | 1.60 |
| Boundary Top-3 δ=.01 | **97.86%** | 70.67% | 1.77 |
| Top-5 | 98.10% | **70.54%** | 1.79 |
| Boundary Top-5 δ=.01 | **98.81%** | 68.93% | 1.87 |
| No pruning | 100% | 63.64% | 2.15 |

High-branching subset n=32에서는 Top-3 gold-path survival이 37.50%까지 떨어졌고 Boundary Top-3는 78.13%였다.

이 결과가 보여준 것은 다음이다.

> **branching이 큰 구간에서 fixed Top-K가 중요한 evidence path를 비가역적으로 제거할 가능성이 커진다.**

하지만 더 많이 살린다고 F1이 좋아지는 것은 아니었다.

## 12.2 WN18RR iterative n=50

| 정책 | Success | Pruning Regret ↓ | Avg Expanded |
|---|---:|---:|---:|
| Top-3 | 40% | 58% | 24.38 |
| Boundary Top-3 δ=.005 | **46%** | **52%** | 25.42 |
| Top-5 | 56% | 42% | 29.00 |
| Boundary Top-5 δ=.010 | **60%** | **38%** | 31.08 |

방향은 긍정적이었지만 비용 증가와 retained-set precision 감소가 있었다.

따라서 BADP는 **유망한 pruning ablation**이지 현재 연구 전체의 최종 방법은 아니다.

---

# 13. Conditional BADP와 Boundary Risk: 한계 확인

BADP를 항상 켜는 비용을 줄이기 위해 단순 K/K+1 margin으로 activation을 결정하는 Conditional BADP를 검토하였다.

WN18RR에서는 일부 설정에서 always-on BADP와 같은 success를 더 낮은 activation rate로 재현했다.

그러나 WebQSP n=20에서는 activation rate가 60~97.5%까지 올라갔고 Top-3보다 search success가 개선되지 않았다.

따라서 다음 가설은 현재 지지되지 않는다.

> **단순 boundary margin 하나만으로 위험한 pruning boundary를 충분히 식별할 수 있다.**

여기서 얻은 연구적 교훈은 BADP 자체보다 다음 구분이다.

```text
Preservation operator:
무엇을 추가로 남길 것인가?

Risk detector:
언제 추가 보존이 필요한가?
```

Boundary Risk는 이 문제를 탐색하기 위한 후속 아이디어였지만, 아직 최종 연구 주제로 고정할 단계는 아니다.

---

# 14. 최근 연구 방향: 방법 이름보다 same-candidate-space 비교

최근에는 연구 질문을 다시 더 근본적으로 좁혔다.

> **같은 base model과 같은 candidate space를 사용할 때, alternative-preserving reasoning과 scorer 선택이 실제 conflict identification에 어떤 영향을 주는가?**

이를 위해 natural-language MAGIC에서 다음 네 조건을 비교하는 구조를 만들었다.

```text
D   = Direct
DC  = Fixed two-stage call-matched Direct
RA  = Alternative-preserving pipeline + same LLM scorer
RD  = Alternative-preserving pipeline + DeBERTa scorer
```

여기서 RA/RD는 현재 코드상 Possible Worlds를 사용하지만, 최종 연구가 반드시 Rashomon Worlds라는 이름을 유지해야 한다는 전제는 두지 않는다.

핵심 통제는 다음이다.

```text
RA와 RD는
동일 claim extraction
동일 candidate paths
동일 possible-world construction
을 공유한다.

차이는 scorer뿐이다.
```

---

# 15. HF 20-row natural-language MAGIC pilot

실험 run:

```text
GitHub Actions Run 32747389414
Artifact 9528788562
attempts = 1
limit    = 20 conflict rows
retries  = 0
```

모델은:

```text
Cohere Command A 111B
GPT-OSS 120B
Qwen3 235B A22B Instruct 2507
```

을 사용하였다.

한 row당 logical provider call은 다음과 같이 고정하였다.

```text
Direct                         1
Two-stage Direct               2
Shared claim extraction        1
Same-LLM batch world scoring   1
DeBERTa scoring                local inference
---------------------------------
총 provider calls              5 / row
```

## 15.1 결과

| 모델 | n | Direct conflict recall | Two-stage Direct | Alternative + LLM scorer | Alternative + DeBERTa |
|---|---:|---:|---:|---:|---:|
| Command A 111B | 20 | 80% | 100% | 30% | **80%** |
| GPT-OSS 120B | 실패 | — | — | — | — |
| Qwen3 235B | 20 | 55% | 100% | 20% | **75%** |

GPT-OSS는 첫 complete row가 기록되기 전에 HF provider의 `HTTP 504 Gateway Time-out`으로 중단되었다. 따라서 GPT-OSS 값은 성능 비교에 사용하지 않는다.

Command A와 Qwen은 각각 20 rows를 완주했고 physical provider call은 정확히 100/100이었다.

## 15.2 가장 중요한 20-row 관찰

같은 candidate space에서 scorer만 바꾸었을 때:

```text
Command A
LLM scorer      30%
DeBERTa scorer  80%
Δ               +50%p

Qwen3
LLM scorer      20%
DeBERTa scorer  75%
Δ               +55%p
```

paired diagnostic에서도 같은 방향이 나왔다.

| 모델 | 비교 | Δ | 95% bootstrap CI | exact McNemar p |
|---|---|---:|---:|---:|
| Command A | DeBERTa vs LLM scorer | **+50%p** | +30 ~ +70 | 0.00195 |
| Qwen3 | DeBERTa vs LLM scorer | **+55%p** | +35 ~ +75 | 0.00098 |

20 rows는 최종 통계 표본으로 충분하지 않지만, **scorer bottleneck을 찾는 pilot**으로는 강한 신호다.

## 15.3 이 결과가 의미하지 않는 것

이번 20개는 모두 conflict-only MAGIC rows다.

따라서:

```text
ID = accuracy가 아니라 conflict recall diagnostic
```

이다.

Two-stage Direct의 100%를 전체 MAGIC accuracy 100%로 해석하면 안 된다. 항상 conflict라고 예측하는 시스템도 이 subset에서는 recall 100%가 될 수 있다.

또한 이 결과만으로 Possible Worlds가 Direct보다 우수하다고 주장할 수도 없다.

오히려 현재 결과는 다음을 보여준다.

> **Alternative-preserving construction은 candidate space를 만들지만, final conflict decision은 scorer에 매우 민감하다.**

---

# 16. 현재까지 연구 가설의 상태

## 16.1 H1 Alternative Preservation

**부분 지지.**

근거:

- Synthetic explanation coverage 50% → 100%
- Structured MAGIC에서 early single selection보다 더 높은 gold-world candidate retention
- WN18RR에서 Top-1 16%보다 candidate coverage 42%

하지만 candidate coverage 증가가 final accuracy 증가를 보장하지 않는다.

## 16.2 H2 Delayed Commitment

**부분 지지.**

근거:

- Early-commit보다 alternative set에서 더 많은 viable explanation을 보존
- MAGIC high-branching과 WN18RR에서 aggressive Top-K pruning이 viable/gold path를 제거하는 현상 관찰

그러나 항상 더 많은 후보를 유지하는 것은 precision과 비용을 악화시킨다.

## 16.3 H3 Evidence-aware Adjudication

**현재 가장 강하게 지지되는 가설.**

근거:

- Structured MAGIC: weak lexical → DeBERTa에서 row +18.70%p
- Structured exact LOC +8.33%p
- 20-row natural-language pilot: 동일 candidate space에서 DeBERTa가 same-LLM scorer보다 +50~55%p
- DAFNA: 93% candidate coverage 대비 62% final exact selection

현재 여러 데이터셋에서 가장 반복적으로 나타나는 병목은 **construction보다 ranking / adjudication**이다.

## 16.4 Rashomon Worlds 자체가 반드시 필요한가

**아직 결론 없음.**

Possible Worlds는 alternative preservation을 표현하는 유용한 구현이지만, 현재 결과만으로 다음을 주장할 수 없다.

> Rashomon Worlds라는 특정 표현 방식이 다른 모든 alternative-preserving 방법보다 우수하다.

따라서 최종 논문은 특정 이름을 고집하기보다 **alternative-preserving / delayed-commitment reasoning**을 상위 개념으로 두고, Possible Worlds를 한 구현으로 평가하는 방향도 열어둔다.

## 16.5 Tableau가 최종 성능의 핵심인가

**제한적으로만 지지.**

Synthetic contradiction scope에서는 논리 검증이 명확히 유효했다.

하지만 WN18RR frozen 실험에서는 Tableau filtering이 최종 Top-1 ranking을 개선하지 못했다. 실제 ontology가 불완전하면 Tableau가 reject할 수 있는 후보 자체가 적을 수 있다.

따라서 Tableau 역시 최종 논문의 필수 중심 모듈인지 재검토 가능하다.

## 16.6 BADP / Boundary Risk가 최종 연구인가

**아직 아님.**

BADP는 pruning regret라는 실제 현상을 보여준 유용한 연구 분기다. 하지만 WebQSP에서 simple conditional policy가 실패했고, strict same-budget superiority도 아직 확립되지 않았다.

따라서 현재는 메인 결론이 아니라 **delayed commitment를 search 단계에서 구현한 ablation / 후속 연구 후보**로 보는 것이 안전하다.

---

# 17. 현재까지 가장 강한 연구 관찰

### 관찰 1. 좋은 candidate가 존재하는 것과 최종 정답을 선택하는 것은 다르다

MAGIC과 DAFNA에서 반복적으로 확인되었다.

```text
Candidate Coverage ↑
≠
Final Selection Accuracy ↑
```

### 관찰 2. Same candidate space에서도 scorer에 따라 결과가 크게 달라진다

20-row natural-language pilot에서 가장 직접적으로 확인되었다.

```text
Same construction
Same paths
Same extracted claims
Different scorer
→ +50~55%p difference
```

### 관찰 3. 여러 설명을 보존하는 것은 coverage에 도움이 될 수 있다

Synthetic explanation, structured MAGIC, WN18RR에서 공통적으로 나타났다.

### 관찰 4. 많이 보존하는 것이 항상 좋은 것은 아니다

No-pruning과 wide-band 방식은 survival은 높지만 precision/F1과 비용이 악화될 수 있었다.

### 관찰 5. pruning은 실제 별도 병목이 될 수 있다

특히 high-branching environment에서 fixed Top-K의 viable/gold path loss가 크게 증가했다.

### 관찰 6. 논리 verifier만으로는 semantic uncertainty를 해결할 수 없다

Static Tableau의 낮은 MAGIC detection과 WN18RR의 낮은 filtering 효과가 이를 보여준다.

---

# 18. 폐기하거나 약화된 가설

다음 주장은 현재 그대로 유지하지 않는다.

### 18.1 CONAN에서 우리 방법이 100%를 달성했다

폐기. Controlled verification 결과였다.

### 18.2 Possible Worlds를 만들면 자동으로 final accuracy가 오른다

폐기. Weak scorer에서는 final selection이 나빠질 수 있다.

### 18.3 Tableau가 알아서 누락 relation semantics를 복원한다

폐기. Tableau는 constraint verifier이지 semantic relation generator가 아니다.

### 18.4 후보를 많이 남기면 항상 성능이 좋아진다

폐기. Precision/F1과 비용이 악화될 수 있다.

### 18.5 Global near-optimal band가 Top-K보다 일반적으로 좋다

폐기. WN18RR iterative에서 실패했다.

### 18.6 Boundary margin 하나면 위험한 pruning point를 찾을 수 있다

현재 지지되지 않음. WebQSP에서 activation이 과도했다.

### 18.7 Rashomon Worlds를 최종 논문에서 반드시 유지해야 한다

미확정. 현재 연구의 핵심은 특정 이름보다 delayed commitment와 evidence-aware adjudication이다.

---

# 19. 다음 재실험에서 확인할 것

20-row pilot은 최종 결론보다 **어디를 고쳐야 하는지 찾기 위한 pilot**으로 사용한다.

다음 재실험 전에 수정할 항목은 네 가지다.

## 19.1 GPT-OSS 504를 infrastructure failure로 분리

현재는 한 row의 provider 504가 전체 model run을 중단시킨다.

수정 방향:

```text
row-level error isolation
provider / infrastructure error 별도 기록
completed rows와 failed rows 분리
성능 metric에는 completed paired rows만 사용
```

## 19.2 Analyzer의 fixed two-stage baseline 버그 수정

기존 analyzer가 과거 `budget_reached` 필드를 요구하기 때문에 새로운 fixed two-stage Direct 비교가 `null`로 나온다.

새 구조에서는 fixed call이므로 해당 filter를 제거하거나 protocol-version에 따라 분기해야 한다.

## 19.3 Actual HTTP request logging

현재 logical calls는 알 수 있지만 실패한 request까지 정확하게 집계하지 못한다.

최종 실험에서는 다음을 기록한다.

```text
actual HTTP requests
logical task calls
input tokens
output tokens
latency
HTTP / contract failures
```

## 19.4 Same-LLM batch scorer의 contradiction under-scoring 분석

현재 가장 중요한 기술적 질문이다.

동일 candidate space에서 LLM scorer가 DeBERTa보다 크게 낮은 이유를 분해한다.

검토 항목:

```text
batch prompt에서 여러 world가 섞여 calibration이 약해지는가?
contradiction 정의가 모델에게 충분히 명확한가?
unresolved 쪽으로 과도하게 점수를 주는가?
path direction / negation 표현이 LLM에 불리한가?
각 world의 score 분포가 지나치게 평평한가?
DeBERTa와 disagreement하는 candidate 유형은 무엇인가?
```

이 분석 결과에 따라 Possible Worlds를 유지할지, path-level evidence aggregation으로 단순화할지, scorer를 별도 discriminative model로 고정할지 결정한다.

---

# 20. 연구 방향 재정비 기준

다음 20-row 재실험 이후에는 특정 기존 방법을 살리는 것이 아니라 결과에 따라 구조를 선택한다.

### 경우 A. DeBERTa 기반 alternative-preserving pipeline이 반복적으로 Direct보다 개선

연구 중심:

> **Alternative Preservation + Evidence-aware Adjudication**

Possible Worlds는 구현 중 하나로 유지 가능하다.

### 경우 B. Possible Worlds 없이 path/evidence aggregation만으로 동일 성능

연구 중심을 더 compact하게 바꾼다.

> **Delayed Evidence Commitment / Multi-hop Evidence Adjudication**

Possible Worlds는 ablation으로 이동할 수 있다.

### 경우 C. Direct 또는 two-stage Direct가 전체 benchmark에서도 계속 우수

현재 구조가 과도하다는 의미이므로 candidate construction과 final decision을 다시 설계한다.

### 경우 D. Pruning regret가 최종 성능의 주 원인으로 확인

BADP / Boundary Risk 계열을 별도 메인 연구로 승격할 수 있다.

현재는 어느 경우도 미리 확정하지 않는다.

---

# 21. 실험 결과 요약

아래는 현재까지 서로 다른 실험이 어떤 연구 질문을 지지했는지를 압축한 표다.

| 실험 | 주요 결과 | 연구적 의미 |
|---|---|---|
| Synthetic Scope n=80 | 75% → 100% | perspective separation 논리 검증 |
| Synthetic Explanation n=20 | 50% → 100% coverage | alternative preservation 가능성 |
| Structured MAGIC Static | row 5.44% | hard ontology/Tableau만으로 부족 |
| Structured MAGIC Early Commit | row 29.93% | semantic candidate reasoning 필요 |
| Structured MAGIC PW retention | query gold-world 39.39% | viable explanation 보존 |
| Structured MAGIC weak scorer | row 22.79%, LOC 7.14% | ranking 병목 |
| Structured MAGIC DeBERTa | row 41.50%, LOC 15.48% | semantic scorer 효과 |
| DAFNA n=100 | coverage 93%, exact 62% | construction-selection gap |
| WN18RR Frozen | Top-1 16%, coverage 42% | single selection loss |
| MAGIC high-branching | Top-3 survival 37.50% | pruning regret 증가 |
| WN18RR BADP n=50 | success 40→46%, 56→60% | boundary-local preservation 신호 |
| WebQSP Conditional | Top-3 개선 실패 | simple risk gate 한계 |
| HF MAGIC 20-row Command A | LLM scorer 30%, DeBERTa 80% | same-space scorer gap +50%p |
| HF MAGIC 20-row Qwen3 | LLM scorer 20%, DeBERTa 75% | same-space scorer gap +55%p |
| HF MAGIC 20-row GPT-OSS | HTTP 504 | infrastructure failure, 성능값 없음 |

---

# 22. 재현 가능한 주요 실행

| 실험 | Run / Commit | Artifact / 결과 |
|---|---|---|
| CONAN-derived controlled verification | commit `98b8d475...` | controlled verification, 공식 CONAN 성능 아님 |
| Synthetic Controlled Scope | commit `457a6ebf...` | `ablation_metrics.json` |
| MAGIC Possible Worlds | Run `32725453943` | Artifact `9519356207` |
| MAGIC DeBERTa structured scoring | Run `32730398659` | Artifact `9521415589` |
| DAFNA Possible Worlds | Run `32726434311` | Artifact `9519739380` |
| WN18RR Frozen n=50 | Run `32799621678` | Artifact `9546119681` |
| WN18RR Relative-loss n=10 | Run `32813194834` | Artifact `9550550657` |
| MAGIC External Gold pruning | Run `32817516186` | Artifact `9551919328` |
| WN18RR Iterative n=20 | Run `32819877566` | Artifact `9553138233` |
| WebQSP Conditional BADP n=20 | Run `32829786375` | Artifact `9556981080` |
| WN18RR BADP n=50 | Run `32852520635` | Artifact `9566776300` |
| HF natural-language MAGIC fixed-call pilot n=20 | Run `32747389414` | Artifact `9528788562` |

---

# 23. 현재 잠정 결론

현재까지 연구를 특정 방법 이름 없이 가장 안전하게 정리하면 다음과 같다.

1. **상충하는 multi-hop evidence를 하나의 state로 너무 일찍 합치는 것은 유효한 대안 설명을 잃을 수 있다.**
2. Perspective separation과 multiple-explanation preservation은 controlled setting에서 실제 coverage 이점을 보였다.
3. 그러나 candidate를 많이 만드는 것만으로 final accuracy가 좋아지지는 않는다.
4. Hard ontology와 Tableau만으로는 실제 multi-hop relation semantics를 충분히 복원할 수 없다.
5. MAGIC과 DAFNA에서는 candidate construction과 final selection 사이에 큰 gap이 반복적으로 나타났다.
6. Structured MAGIC과 최근 natural-language pilot 모두 **scorer / adjudication이 주요 병목**이라는 강한 신호를 보였다.
7. 특히 최근 20-row pilot에서는 동일 candidate space에서 DeBERTa scorer가 same-LLM scorer보다 +50~55%p 높은 conflict recall을 보였다.
8. 한편 high-branching search에서는 pruning 자체도 viable evidence를 잃게 만드는 별도 병목이 될 수 있다.
9. BADP는 이 pruning regret를 일부 줄였지만 비용과 precision trade-off가 있어 최종 방법으로 확정되지 않았다.
10. 현재 연구는 Rashomon Worlds, Tableau, BADP 중 하나를 고집하기보다 **Alternative Preservation → Consistency Check → Evidence-aware Adjudication**이라는 더 일반적인 구조를 검증하는 단계다.

현재 연구 질문을 한 문장으로 다시 쓰면 다음과 같다.

> **불완전하고 상충하는 multi-hop evidence에서 여러 유효한 설명을 필요한 만큼 보존하고, 논리·의미적 근거를 이용해 그중 올바른 설명과 상충 근거를 안정적으로 선택할 수 있는가?**

이 질문을 중심으로 다음 20-row 재실험에서 scorer bottleneck과 provider failure를 먼저 정리한 뒤, 결과가 안정되면 100-row 및 전체 benchmark로 확대한다.
