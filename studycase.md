# 선행 실험과 연구 문제의 발전 과정

## 0. 문서 목적

이 문서는 현재 연구가 **Possible Worlds와 Tableau 기반 상충 추론**에서 출발하여, **불완전한 온톨로지의 관계 보완**, **의미 기반 후보 점수화**, **가지치기 손실 분석**, **BADP**, 그리고 **Conditional BADP / Boundary Risk**로 발전한 과정을 정리한다.

단순한 개발 기록이 아니라 다음 질문에 답하는 것이 목적이다.

1. 각 단계에서 어떤 문제를 해결하려 했는가?
2. 어떤 데이터셋과 지표를 사용했는가?
3. 실제로 개선된 것은 무엇이고, 실패하거나 폐기한 가설은 무엇인가?
4. 코드 오류 또는 평가 설계 때문에 잘못 해석된 값은 무엇인가?
5. 현재 논문의 핵심 주장은 어디까지 가능한가?

연구 흐름을 먼저 요약하면 다음과 같다.

```text
상충하는 여러 설명을 하나로 너무 빨리 합치지 말자
        ↓
Possible Worlds + Tableau
        ↓
실제 Ontology는 필요한 relation semantics를 모두 갖고 있지 않음
        ↓
Multi-hop Relation Candidate를 예측
        ↓
Semantic Scorer로 후보를 점수화
        ↓
좋은 후보가 존재해도 ranking / pruning에서 사라질 수 있음
        ↓
Pruning Regret 정의
        ↓
Global / Relative near-optimal preservation 실험
        ↓
실제 Top-K cutoff 주변만 보는 BADP
        ↓
Always-on BADP의 비용 증가 확인
        ↓
Conditional BADP
        ↓
단순 boundary margin만으로는 위험한 경계를 충분히 구분하지 못함
        ↓
현재: Boundary Risk 추정
```

현재 연구의 가장 직접적인 질문은 다음과 같다.

> **다중 홉 추론에서 정답 또는 중요한 증거로 이어질 수 있는 경로가 Top-K 가지치기로 너무 일찍 제거되는 문제를 어떻게 줄일 것인가?**

---

# 1. 먼저 알아야 할 핵심 용어

| 용어 | 의미 | 본 연구에서의 역할 |
|---|---|---|
| Knowledge Graph, KG | Entity를 Relation으로 연결한 그래프 | 다중 홉 탐색 공간 |
| Entity | 사람, 장소, 개념, WordNet synset 등의 노드 | 경로의 시작·중간·목표 노드 |
| Relation | 두 Entity 사이의 관계 | 그래프 edge의 의미 |
| Multi-hop path | 여러 relation을 연속해서 따라가는 경로 | 직접 연결되지 않은 정답·증거 탐색 |
| Candidate path | 현재 단계에서 확장 가능한 경로 후보 | pruning 대상 |
| Scorer | 후보와 질의의 의미 적합도를 점수화하는 모델 | 주로 DeBERTa NLI support 사용 |
| Top-K | 점수가 높은 K개 후보만 유지 | 기본 pruning 기준선 |
| Pruning | 다음 단계로 넘기지 않을 후보를 제거 | 탐색 비용 제어 |
| Viable path | 남은 hop budget 안에 target 또는 gold evidence까지 갈 수 있는 경로 | 제거되면 안 되는 유효 후보 |
| Branching factor | 한 단계에서 경쟁하는 후보 수 | 높을수록 Top-K 경쟁 심화 |
| Boundary | K번째와 K+1번째 후보 사이의 실제 제거 경계 | BADP가 직접 보는 지점 |
| Boundary margin | K번째와 K+1번째 점수 차이 | 경계 불확실성 후보 지표 |
| Possible World | 하나의 가능한 관계·사실 해석을 유지한 상태 | 조기 단일 결정을 피하기 위한 표현 |
| Rashomon set | 점수나 성능이 비슷해 하나로 확정하기 어려운 후보 집합 | 초기 near-optimal 보존 아이디어 |
| Ontology | relation 의미와 논리 제약을 명시한 지식 체계 | 후보의 의미 제약과 일관성 검증 |
| Tableau | 논리식이 동시에 참일 수 있는지 확인하는 추론 방법 | SAT/UNSAT 및 contradiction 검증 |
| Provenance | 사실이나 경로가 어디에서 왔는지 나타내는 정보 | 외부 gold 및 설명 근거 |
| Pruning Regret | pruning 전에는 viable path가 있었지만 pruning 후 모두 사라진 사건 | pruning 자체의 정보 손실 측정 |
| BADP | Boundary-Aware Delayed Pruning | Top-K cutoff 바로 아래 near-tie 후보를 추가 보존 |
| Conditional BADP | 경계가 위험하다고 판단될 때만 BADP를 활성화 | 불필요한 폭 증가 억제 |

## 1.1 Top-K와 BADP를 예로 이해하기

후보 점수가 다음과 같다고 하자.

```text
1위  0.910
2위  0.840
3위  0.812   ← K=3의 마지막 보존 후보
4위  0.809   ← Top-3에서는 제거
5위  0.620
```

Top-3는 1~3위만 유지한다. 그러나 3위와 4위 차이는 0.003밖에 되지 않는다.

수식은 GitHub 렌더링 오류를 피하기 위해 이 문서에서는 가능한 한 코드 블록으로 표기한다.

```text
BoundaryMargin(K) = score(K) - score(K+1)
                  = 0.812 - 0.809
                  = 0.003
```

BADP의 기본 아이디어는 **3위와 거의 동점인 4위를 바로 제거하지 말고 잠시 보존하자**는 것이다.

---

# 2. 데이터셋과 실험의 역할

본 연구에서는 서로 다른 데이터셋을 사용한다. 중요한 점은 **각 데이터셋의 지표를 모두 같은 의미의 정확도로 해석하면 안 된다는 것**이다.

| 데이터셋 / 실험 | 데이터 성격 | 사용 목적 | 해석 시 주의점 |
|---|---|---|---|
| CONAN 공식 benchmark | 탐정 서사의 인물 관계 그래프 | 관점·비밀 관계·다중 인물 relation extraction 문제 이해 | 현재 우리 방법의 공식 CONAN 성능 artifact는 없음 |
| CONAN-derived controlled verification | CONAN gold relation을 재료로 우리가 생성한 80개 통제 사례 | reasoner 구현 검증 | 100%는 CONAN benchmark 성능이 아님 |
| Synthetic Controlled Scope | 완전히 합성한 80개 contradiction-scope 사례 | merged vs perspective reasoning 비교 | relation 이름 일부만 CONAN ontology inventory에서 차용 |
| MAGIC | multi-hop 상충 relation 데이터 | relation 해석, possible worlds, conflict evidence 보존 | structured triplet 진단이며 공식 자연어 MAGIC 점수와 다름 |
| DAFNA-EA Books | 다수 출처의 상충 저자 주장 | 후보 world 생성과 truth selection 분리 | 100 gold books subset |
| WN18RR | WordNet 기반 KG benchmark | 통제된 2~4 hop pruning mechanics | 일반 KGC Accuracy나 QA 성능이 아님 |
| WebQSP | 자연어 KGQA benchmark | 실제 질문에서 pruning 정책 외적 검증 | 현재는 Wikidata 기반 retrieval이며 Freebase ToG 재현이 아님 |

---

# 3. CONAN 결과 교정: 가장 중요한 구분

## 3.1 공식 CONAN은 무엇을 평가하는가

CONAN은 Zhao et al., *Large Language Models Fall Short: Understanding Complex Relationships in Detective Narratives* (Findings of ACL 2024)에서 공개한 benchmark이다.

- 논문: https://aclanthology.org/2024.findings-acl.454/
- 공식 코드/데이터: https://github.com/BLPXSPG/Conan

CONAN의 핵심은 탐정 서사에서 **인물 관계 그래프를 추출하고 추론하는 것**이다. 데이터는 각 인물 관점의 narrative와 relation label을 제공하며 다음과 같은 관계를 다룬다.

- Public relation: 대부분의 인물이 알고 있는 관계
- Secret relation: 일부 인물만 알고 있는 비밀 관계
- Inferred relation: 여러 인물의 정보를 합쳐야 추론할 수 있는 관계
- Role-oriented / character-oriented perspective
- Hierarchical relation categories

공식 논문이 정의한 주요 task는 다음과 같다.

```text
1. Character Extraction
2. Entity Linking / Character-oriented Relation Recognition
3. Relation Deduction from all character narratives
```

즉 CONAN의 공식 gold label은 `consistent / divergence / intra-contradiction / inter-contradiction` 같은 본 연구의 contradiction-scope class가 아니다.

### 공식 논문의 관계추출 난이도

아래 값은 **우리 방법의 결과가 아니라 CONAN 논문에 공개된 GPT-4 baseline**이다.

| 입력 범위 | 전략 | GPT-4 Precision | Recall | F1 |
|---|---|---:|---:|---:|
| 단일 인물 관점 | AllTogether | 28.3% | 26.9% | **27.6%** |
| 단일 인물 관점 | DirRelation | 21.9% | 26.7% | 24.0% |
| 전체 인물 관점 | AllTogether | 26.7% | 8.2% | **12.5%** |
| 전체 인물 관점 | DirRelation | 20.2% | 7.5% | 11.0% |

따라서 과거 문서에서 보였던 `100%`를 CONAN 자연어 benchmark 성능으로 해석하면 명백히 잘못이다.

## 3.2 우리 저장소의 실제 CONAN 관련 코드

저장소에는 실제 CONAN 데이터를 읽기 위한 다음 코드가 존재한다.

```text
scripts/download_conan.py
src/rashomon_tableau/conan_loader.py
config/ontology_rules.yaml
```

`conan_loader.py`는 character perspective별 relation JSON을 읽고 relation label을 정규화한다. ontology rule은 CONAN relation label 중 inverse, hierarchy, symmetric relation 등을 논리 규칙으로 사용한다.

그러나 **현재 확인된 저장소 이력에는 우리 방법을 공식 자연어 CONAN benchmark 전체에 대해 end-to-end 평가하여 성능을 산출한 artifact가 없다.**

즉 현재 논문에서 다음 문장을 쓰면 안 된다.

> CONAN에서 Perspective Tableau가 100% 정확도를 달성하였다.

현재 가능한 정확한 표현은 다음이다.

> CONAN의 gold relation과 relation inventory를 이용해 reasoner 동작을 검증하는 controlled experiment를 구성하였다. 이 값은 공식 CONAN relation extraction 성능이 아니다.

## 3.3 CONAN-derived controlled verification의 실제 의미

커밋 `98b8d4756a98992fdf363d6c21f38c509b7dcc4c`의 `results/preliminary_controlled_metrics.json`은 다음 설정이다.

```text
평가 유형: preliminary_controlled_verification
데이터 재료: CONAN Gold relation propositions
사용 story: 655-The Mysterious Case of Zhangdong Town (6 people)
사용 perspectives: Xiting, Yang Minxi
n = 80
```

우리가 gold relation을 바탕으로 다음 통제 사례를 생성하였다.

```text
contradiction         40
consistent            20
divergence            20

explicit contradiction        20
implicit hierarchy            10
implicit inverse              10
same fact                     20
different nonconflicting      20
```

결과는:

| 지표 | 값 |
|---|---:|
| Accuracy | 100% |
| Macro F1 | 100% |
| Implicit contradiction recall | 100% |

였다.

하지만 이 값은 **reasoner correctness verification**이다. 이 평가의 label을 CONAN에서 직접 제공한 것이 아니라, 우리가 동일 ontology semantics를 이용해 생성하였다.

더구나 이 실행에서는 다음 baseline이 실행되지 않았다.

```text
Pairwise NLI       not executed
LLM direct judge   not executed
Vanilla Tableau    not separately executed
Perspective Tableau not separately executed
```

따라서 이 100%를 외부 benchmark 대비 성능 향상으로 사용할 수 없다.

## 3.4 Synthetic Controlled Scope 75% → 100%도 CONAN 결과가 아니다

`src/rashomon_tableau/ablation.py`의 `controlled_scope_ablation`은 더 명확한 합성 실험이다.

코드가 직접 다음 네 class의 사례를 만든다.

```text
consistent
perspective divergence
intra-perspective contradiction
inter-perspective contradiction
```

예를 들어 `father_of → parent_of` hierarchy와 `not parent_of`를 결합하여 contradiction을 의도적으로 생성한다.

이 실험은 relation predicate 이름 일부를 CONAN-normalized inventory에서 사용했지만, **CONAN narrative를 자연어에서 추출하여 평가한 실험이 아니다.**

검증 결과는:

| 방법 | Accuracy | Macro F1 |
|---|---:|---:|
| Vanilla merged Tableau | 75.00% | 66.67% |
| Perspective Tableau | **100.00%** | **100.00%** |
| Rashomon Tableau | **100.00%** | **100.00%** |

이다.

따라서 올바른 이름은:

> **Synthetic Controlled Scope Ablation n=80**

이며, `CONAN 75% → 100%`라고 표현하면 안 된다.

## 3.5 CONAN 관련 최종 교정

| 과거 오해 가능 표현 | 올바른 해석 |
|---|---|
| CONAN Accuracy 100% | CONAN gold relation을 재료로 생성한 controlled reasoner verification 100% |
| CONAN Perspective Tableau 100% | 완전 합성 controlled_scope_ablation의 Perspective Tableau 100% |
| CONAN에서 +25%p 개선 | Synthetic Controlled Scope에서 merged baseline 대비 +25%p |
| CONAN implicit contradiction recall 100% | 우리가 ontology semantics로 생성한 implicit contradiction case에 대한 단위검증 |
| CONAN이 Possible Worlds/BADP 성능을 입증 | 현재 공식 CONAN end-to-end 평가 artifact 없음 |

CONAN은 현재 연구에서 **관점과 비밀·추론 관계가 존재하는 실제 문제 설정의 외부 근거**로는 중요하다. 그러나 현재 성능 근거는 MAGIC, DAFNA, WN18RR, WebQSP와 별도로 취급한다.

---

# 4. Synthetic Controlled Scope: 관점 분리 논리의 단위 검증

## 4.1 왜 통제 실험을 했는가

자연어 데이터에서 실패하면 다음 원인을 분리하기 어렵다.

```text
자연어 추출 실패인가?
관계 mapping 오류인가?
ontology rule 오류인가?
Tableau 구현 오류인가?
ranking 오류인가?
```

그래서 먼저 입력 relation과 gold class를 우리가 완전히 통제하는 synthetic benchmark에서 reasoner 동작을 검증하였다.

## 4.2 결과

| 방법 | Accuracy | Macro F1 |
|---|---:|---:|
| Vanilla merged Tableau | 75.00% | 66.67% |
| Perspective Tableau | **100.00%** | **100.00%** |
| Rashomon Tableau | **100.00%** | **100.00%** |

개선 폭은:

```text
Accuracy: 75.00% → 100.00%   (+25.00%p)
Macro F1: 66.67% → 100.00%   (+33.33%p)
```

이 결과가 의미하는 것은 자연어 일반화가 아니라 다음이다.

> 관점 내부 contradiction과 관점 간 contradiction을 분리해 둔 통제 환경에서는, 하나의 merged ABox보다 perspective-indexed reasoning이 contradiction scope를 정확히 구분할 수 있었다.

Rashomon은 이 실험에서 Perspective Tableau보다 class accuracy를 추가로 올리지 않았다.

## 4.3 Explanation Coverage

별도 synthetic explanation 실험은 20개 사례, 사례당 2개의 minimal contradiction으로 총 40개의 gold explanation을 사용하였다.

| 방법 | Explanation Coverage |
|---|---:|
| Single-path | 50% |
| Rashomon enumeration | **100%** |

즉 Rashomon의 초기 장점은 class accuracy보다 **복수의 타당한 설명을 모두 보존하는 것**에서 나타났다.

---

# 5. 첫 번째 실제 한계: Ontology가 불완전하다

그래프에 경로가 있다고 해서 그 경로의 의미나 논리적 모순을 자동으로 알 수 있는 것은 아니다.

```text
Graph Reachability ≠ Semantic Relation ≠ Logical Contradiction
```

예를 들어:

```text
h --r1--> e1 --r2--> e2 --r3--> t
```

라는 path가 존재해도 우리가 알고 싶은 직접 relation이 `(h, ?, t)`라면, ontology가 `?`를 자동으로 생성하지 않는다.

MAGIC structured multi-hop 분석에서는 이 차이가 명확하게 나타났다.

| 지표 | 결과 |
|---|---:|
| Multi-hop legacy direct detection | 33.16% |
| Bidirectional candidate-path coverage | **68.03%** |
| Ontology/Tableau conflict detection | **5.44%** |

68.03%는 accuracy가 아니라 **candidate path coverage**다. 핵심은 다음이다.

> 경로는 찾았지만, hard ontology만으로는 그 경로가 의미하는 관계와 contradiction을 충분히 결정하지 못했다.

---

# 6. 누락 관계를 후보로 예측하는 구조

Ontology에 직접 relation이 없다고 추론을 끝내는 대신, 다중 홉 path에서 relation candidate를 생성하는 방향을 검토하였다.

```text
Unknown relation:
(h, ?, t)

Candidate relations:
R(h,t) = {r1, r2, ..., rm}

Semantic score:
score(path, relation) ∈ [0,1]
```

후보별로 possible world를 만들고, ontology/Tableau는 relation을 생성하는 역할이 아니라 **논리적으로 불가능한 후보를 제거하는 constraint verifier**로 사용하였다.

이 단계에서 문제를 세 단계로 분리하게 되었다.

```text
1. 좋은 candidate를 생성했는가?
2. candidate를 올바르게 ranking했는가?
3. 좋은 candidate가 pruning 후에도 살아남았는가?
```

이 구분이 현재 pruning 연구의 기반이다.

---

# 7. MAGIC Possible Worlds: 후보 보존과 후보 선택의 분리

## 7.1 데이터와 지표 범위

검증된 structured MAGIC 실험은:

```text
588 rows
1,056 query conflicts
```

를 사용한다.

이는 공식 natural-language MAGIC ID/LOC 평가와 다르며, released structured triplet을 이용한 진단이다.

## 7.2 결과

| 방법 | Row conflict recall | Query conflict recall | Gold-world query recall | Structured exact LOC |
|---|---:|---:|---:|---:|
| Static Tableau | 5.44% | 4.45% | — | — |
| Early-commit single world | 29.93% | 22.63% | — | — |
| Possible-world retention | — | — | **39.39%** | **29.42%** |
| Weakly weighted worlds | 22.79% | 16.86% | — | 7.14% |

Weakly weighted world run의 평균 후보 규모는:

```text
worlds / row          = 7.34
worlds / query        = 4.08
candidate paths/query = 1.45
```

이었다.

이 결과의 핵심은:

```text
Gold-world candidate coverage ≠ Final selected-world correctness
```

라는 점이다.

좋은 world가 후보 안에 존재해도 ranking이 나쁘면 최종 선택은 실패한다.

---

# 8. Semantic Scorer: 후보 ranking 개선

Weak lexical weighting 대신 `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`를 semantic scorer로 사용하였다.

DeBERTa는 relation을 생성하는 모델이 아니라 **동일 candidate 중 질의와 의미적으로 더 잘 맞는 후보를 점수화하는 모듈**이다.

## 8.1 검증된 structured MAGIC 결과

| 지표 | Weak lexical | DeBERTa | 변화 |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71%p** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68%p** |
| Structured exact localization | 7.14% | **15.48%** | **+8.33%p** |
| Query gold-path selection | — | 22.06% | 참고 |

### 반드시 제외해야 하는 자연어 MAGIC 결과

초기 natural-language 실험 일부에서는 다음 provenance metadata가 semantic proposition과 함께 scorer 입력에 들어갔다.

```text
[source=context1, sentence=...]
[source=context2, sentence=...]
```

이 정보는 의미 판단 대상이 아니라 audit metadata이다. 따라서 **해당 수정 이전 natural-language MAGIC 결과는 최종 성능 근거에서 전부 제외한다.**

위 표의 수치는 오류가 있었던 자연어 실행이 아니라 structured triplet world-ranking diagnostic 결과다.

---

# 9. DAFNA-EA Books: 좋은 후보와 좋은 최종 선택은 다르다

100개 gold book subset을 사용하였다.

```text
gold books = 100
claims     = 1,999
sources    = 227
```

Possible-world candidate generation의 gold-world coverage는 **93%**였다. 평균 candidate worlds는 27.94개, 최대 256개였다.

## 9.1 최종 truth selection

| 방법 | Exact-set Accuracy | Author F1 |
|---|---:|---:|
| Possible-world uniform | 58% | 80.38% |
| Hard-commit reliability | 61% | 84.04% |
| Possible-world marginal | **62%** | **84.13%** |
| Prior atomic resolution | 61% | 82.88% |
| TruthFinder | 57% | 66.85% |
| AccuSim | 57% | 66.18% |
| 2-Estimates | 54% | 65.28% |
| 3-Estimates | 53% | 65.45% |

Prior atomic resolution 대비:

```text
Exact-set Accuracy: 61% → 62%      (+1%p)
Author F1:          82.88% → 84.13% (+1.25%p)
```

하지만 더 중요한 관찰은 다음이다.

```text
Gold-world coverage = 93%
Best exact selection = 62%
```

즉 후보 생성보다 ranking/calibration이 더 큰 병목이었다.

---

# 10. 연구 초점 이동: 좋은 후보가 pruning에서 사라질 수 있다

Semantic scorer를 개선해도 candidate가 중간 pruning에서 제거되면 다음 단계에서 다시 확장할 수 없다.

따라서 연구 질문이 다음처럼 바뀌었다.

```text
이전:
어떤 relation/world가 가장 맞는가?

변경:
맞는 relation/world가 후보 안에 있었는데
pruning에서 먼저 사라지는 것은 아닌가?
```

---

# 11. Pruning Regret와 주요 평가 지표

## 11.1 Viable path

현재 partial path가 남은 hop budget 안에 target/gold evidence로 이어질 수 있으면 viable로 정의한다.

## 11.2 Pruning Regret

```text
PR(i,k) = 1
iff
pruning 전 viable path 수 > 0
AND
pruning 후 viable path 수 = 0
```

Query Pruning Regret는 한 query에서 이런 사건이 한 번이라도 발생한 비율이다. **낮을수록 좋다.**

## 11.3 Retained-set validity

후보를 많이 남기면 survival만 높아질 수 있으므로 precision/recall/F1도 함께 본다.

```text
Precision = viable retained paths / all retained paths
Recall    = viable retained paths / viable candidate paths
F1        = 2 × Precision × Recall / (Precision + Recall)
```

## 11.4 비용

```text
Average Active Width
Average Expanded Candidates
Scorer Calls
```

를 함께 측정한다.

따라서 최종 평가 축은:

```text
Search / Evidence Preservation
× Retained-set Validity
× Search Cost
```

이다.

---

# 12. WN18RR Frozen n=50: 후보 보존 진단

이 실험은 candidate relation 11개를 한 번 점수화한 frozen diagnostic이다.

검증 run의 실제 값은 다음과 같다.

| 지표 | 결과 |
|---|---:|
| Top-1 relation accuracy | **16%** |
| Rashomon ε=.05 gold relation coverage | **42%** |
| Tableau 후 gold relation retention | **42%** |
| Rashomon+Tableau 최종 Top-1 accuracy | **16%** |
| 평균 Rashomon 후보 수 | 3.82 |
| 평균 Tableau rejected worlds | 0.00 |

### 중요한 교정

`16%`와 `42%`는 같은 지표가 아니다.

```text
16% = 가장 높은 relation 하나가 gold인가?
42% = 여러 near-optimal 후보 안에 gold relation이 포함되는가?
```

따라서 `정확도가 16%에서 42%로 향상되었다`고 쓰면 안 된다.

정확한 해석은:

> 단일 선택의 Top-1 정확도는 16%였지만 평균 3.82개의 near-optimal 후보를 유지하면 42%의 사례에서 gold relation이 후보 집합 안에는 포함되었다. 그러나 현재 Tableau filtering은 ranking을 개선하지 못해 최종 Top-1 accuracy는 16%로 그대로였다.

이다.

---

# 13. WN18RR Iterative n=10: Global band의 실패와 Relative-loss

실제 iterative search에서는 이전 단계에서 남은 path만 다음 단계에서 확장된다.

```text
Expand → Score → Prune → Expand → Score → Prune
```

## 13.1 Global additive band

| 정책 | Search Success | Query Pruning Regret | Avg Width |
|---|---:|---:|---:|
| Top-3 | **60%** | 40% | 2.67 |
| Top-5 | **60%** | 40% | 3.88 |
| Global ε=.05 | 40% | 60% | 2.65 |
| Global ε=.10 | 40% | 60% | 3.62 |

Frozen candidate에서는 near-optimal preservation이 유망해 보였지만 iterative search에서 Global additive band는 오히려 Top-K보다 나빴다.

따라서 다음 가설을 폐기하였다.

> 최고점 주변 near-optimal 후보를 전역적으로 보존하면 일반적으로 Top-K보다 좋다.

## 13.2 Relative-loss

| 정책 | Search Success | Pruning Regret | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 | 21.30 |
| Top-5 | 60% | 40% | 3.88 | 28.30 |
| Relative-loss .25 | 50% | 50% | 4.09 | 31.40 |
| Relative-loss .50 | **70%** | **30%** | 5.97 | 31.40 |

Relative-loss .50은 success를 +10%p 높였지만 폭과 비용도 증가하였다.

---

# 14. MAGIC External Gold: 실제 증거 보존 분석

DeBERTa scorer 자체를 gold로 쓰면 순환 평가가 될 수 있으므로 `perturb_triplet` provenance를 scorer와 독립적인 external gold로 사용하였다.

```text
전체 query                    = 1,056
candidate path 존재           = 618
pruning 전 gold path 존재     = 420 (recoverable)
```

## 14.1 Recoverable n=420

| 정책 | Gold Path Survival | Gold Precision | Gold Recall | Gold F1 | Avg Width |
|---|---:|---:|---:|---:|---:|
| Top-1 | 80.71% | **80.71%** | 80.52% | **80.62%** | 1.00 |
| Top-3 | 94.76% | 59.38% | 94.77% | 73.01% | 1.60 |
| Top-5 | 98.10% | 55.07% | 98.10% | 70.54% | 1.79 |
| Global ε=.10 | 97.14% | 50.18% | 97.15% | 66.18% | 1.94 |
| Relative-loss .25 | 83.81% | 74.26% | 83.61% | 78.66% | 1.13 |
| Boundary Top-3 δ=.01 | **97.86%** | 55.30% | **97.86%** | 70.67% | 1.77 |
| Boundary Top-5 δ=.01 | **98.81%** | 52.93% | **98.81%** | 68.93% | 1.87 |
| No pruning | 100% | 46.67% | 100% | 63.64% | 2.15 |

Top-3 대비 Boundary Top-3의 survival은:

```text
94.76% → 97.86%  (+3.10%p)
```

로 증가하였다. 그러나 Gold F1은 73.01%에서 70.67%로 감소했다.

즉 **gold path를 더 살렸지만 non-gold path도 같이 늘었다.**

## 14.2 High-branching n=32

후보 path가 5개 이상인 recoverable query에서는 fixed Top-K의 약점이 훨씬 크게 나타났다.

| 정책 | Gold Path Survival | Gold Precision | Gold F1 | Avg Width |
|---|---:|---:|---:|---:|
| Top-3 | 37.50% | 12.50% | 18.75% | 3.00 |
| Top-5 | 75.00% | **15.00%** | 25.00% | 5.00 |
| Boundary Top-3 δ=.01 | **78.13%** | 14.97% | **25.13%** | 5.22 |
| Boundary Top-5 δ=.01 | **84.38%** | 13.78% | 23.68% | 6.13 |
| Global ε=.10 | 96.88% | 11.52% | 20.60% | 8.41 |
| No pruning | 100% | 10.26% | 18.60% | 9.75 |

개선 폭은:

```text
Top-3: 37.50% → 78.13%  (+40.63%p)
Top-5: 75.00% → 84.38%  (+9.38%p)
```

이다.

현재까지 가장 강한 구조적 관찰은:

> **후보 branching이 큰 구간에서 fixed Top-K가 중요한 evidence path를 잃는 위험이 크게 증가한다.**

이다.

---

# 15. BADP: 실제 Top-K cutoff를 대상으로 지연

후보를 점수 순서로 정렬했다고 하자.

```text
s1 ≥ s2 ≥ ... ≥ sK ≥ s(K+1) ≥ ...
```

BADP는 Top-K를 기본으로 유지하면서 K번째 점수 바로 아래의 후보만 δ 범위 내에서 추가 보존한다.

```text
BADP(K, δ)
= TopK
  + { candidate_j | j > K and score(K) - score(j) ≤ δ }
```

Global band와의 차이는 최고점 주변 전체가 아니라 **실제로 제거가 일어나는 K/K+1 boundary 주변만 본다**는 것이다.

---

# 16. WN18RR Iterative n=20: BADP 첫 반복 탐색

| 정책 | Success | Regret ↓ | Viability Precision | Viability Recall | Viability F1 | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|---:|---:|---:|
| Top-3 | 50% | 50% | 24.46% | 53.57% | **33.58%** | 2.71 | 24.80 |
| Boundary Top-3 δ=.005 | **55%** | **45%** | 22.32% | 56.82% | 32.05% | 3.34 | 27.15 |
| Top-5 | 55% | 45% | 20.22% | 57.89% | **29.97%** | 4.06 | 32.35 |
| Boundary Top-5 δ=.010 | **60%** | **40%** | 18.18% | 61.86% | 28.10% | 5.00 | 35.10 |
| Boundary Top-5 δ=.050 | **65%** | **35%** | 16.24% | 67.74% | 26.20% | 6.16 | 38.25 |

Success와 regret는 좋아졌지만 precision/F1과 비용이 나빠졌다.

```text
Success / Recall ↑
Pruning Regret ↓
Precision / F1 ↓
Search Cost ↑
```

또한 가장 width가 가까운 δ=.001 비교에서는 Top-K 대비 success gain이 없었다. 따라서 n=20에서 **strict same-budget superiority는 확인되지 않았다.**

---

# 17. WN18RR Iterative n=50: 확대 재검증

수정 재실행 `32852520635`는 평가, artifact, summary 모두 성공하였다.

```text
2-hop = 19
3-hop = 23
4-hop = 8
총 50 query
```

## 17.1 주요 결과

| 정책 | Success | Regret ↓ | Viability Precision | Viability Recall | Viability F1 | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|---:|---:|---:|
| Top-3 | 40% | 58% | 25.00% | 54.93% | **34.36%** | 2.69 | 24.38 |
| Boundary Top-3 δ=.001 | 42% | 56% | 24.59% | 55.00% | 33.99% | 2.86 | 25.08 |
| Boundary Top-3 δ=.005 | **46%** | **52%** | 23.98% | 57.59% | 33.86% | 3.16 | 25.42 |
| Top-5 | 56% | 42% | 23.60% | 63.07% | **34.35%** | 3.95 | 29.00 |
| Boundary Top-5 δ=.001 | 58% | 40% | 22.78% | 63.64% | 33.55% | 4.17 | 29.50 |
| Boundary Top-5 δ=.010 | **60%** | **38%** | 21.42% | 66.26% | 32.37% | 4.73 | 31.08 |

Top-3 → Boundary Top-3 δ=.005:

```text
Success: 40% → 46%     (+6%p)
Regret:  58% → 52%     (-6%p)
Expanded: 24.38 → 25.42 (+1.04)
```

Top-5 → Boundary Top-5 δ=.010:

```text
Success: 56% → 60%     (+4%p)
Regret:  42% → 38%     (-4%p)
Expanded: 29.00 → 31.08 (+2.08)
```

작은 δ=.001에서도:

```text
Top-3 success 40% → 42%, Expanded +0.70
Top-5 success 56% → 58%, Expanded +0.50
```

였다.

n=20과 n=50에서 boundary-local preservation의 방향은 반복되었지만, Viability F1은 Top-K보다 소폭 낮았다.

---

# 18. Conditional BADP: BADP를 항상 켜지 않기

Always-on BADP는 경계가 명확한 경우에도 추가 후보를 보존할 수 있다. 이를 줄이기 위해 K번째와 K+1번째 점수 차이를 이용하였다.

```text
ΔK = score(K) - score(K+1)

if ΔK ≤ τ:
    BADP(K, δ)
else:
    Top-K
```

- `τ`: BADP를 켤지 결정하는 boundary-risk threshold
- `δ`: BADP가 켜졌을 때 추가 보존 범위

## 18.1 WN18RR n=50 Conditional 결과

| 정책 | Success | Regret ↓ | Avg Width | Avg Expanded | Activation Rate |
|---|---:|---:|---:|---:|---:|
| Conditional Top-3 τ=.005, δ=.005 | **46%** | **52%** | 3.16 | 25.42 | **28.32%** |
| Conditional Top-3 τ=.010, δ=.005 | **46%** | **52%** | 3.16 | 25.42 | 43.36% |
| Conditional Top-3 τ=.020, δ=.010 | 46% | 52% | 3.38 | 26.38 | 62.28% |
| Conditional Top-5 τ=.010, δ=.010 | **60%** | **38%** | 4.73 | 31.08 | **61.80%** |
| Conditional Top-5 τ=.020, δ=.010 | **60%** | **38%** | 4.73 | 31.08 | 73.03% |
| Conditional Top-5 τ=.050, δ=.020 | 60% | 38% | 5.11 | 33.22 | 94.38% |

Top-3 τ=.005는 boundary check의 28.32%에서만 활성화되었는데 always-on Boundary Top-3 δ=.005와 동일한 46% success를 보였다.

그러나 이것만으로 Conditional BADP의 일반적 우월성을 주장할 수 없다. WebQSP에서 결과가 달랐다.

---

# 19. WebQSP n=20: 실제 질문에서는 단순 margin gate가 부족

현재 WebQSP 실험은:

```text
ToG 공개 WebQSP 질문 사용
qid_topic_entity 사용
Wikidata outgoing entity statements 탐색
lexical prefilter 적용
DeBERTa scorer 공유
최종 LLM answer generator 없음
```

인 retrieval/search validation이다.

따라서 Freebase 기반 ToG의 end-to-end QA 성능과 직접 비교하지 않는다.

## 19.1 주요 정책

| 정책 | Success | Hit@1 | Retrieval F1 | Answer Recall | Answer Pruning Regret ↓ | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|---:|---:|---:|
| Top-3 | **35%** | 20% | **10.42%** | 27.08% | **15%** | **3.00** | **33.05** |
| Top-5 | 35% | 20% | 7.14% | 27.08% | 20% | 5.00 | 46.35 |
| Relative-loss .50 | **45%** | 20% | 7.25% | 32.42% | 20% | 8.90 | 68.80 |
| Always BADP Top-3 δ=.005 | 35% | 20% | 8.18% | 27.08% | 20% | 4.25 | 45.65 |
| Always BADP Top-5 δ=.050 | **45%** | 20% | 5.95% | **34.08%** | 20% | 9.38 | 77.20 |

더 넓은 정책은 success가 45%까지 올라가기도 했지만 비용이 크게 증가하고 Retrieval F1은 Top-3보다 낮았다.

## 19.2 Conditional BADP

| 정책 | Success | Retrieval F1 | Regret ↓ | Avg Width | Avg Expanded | Activation Rate |
|---|---:|---:|---:|---:|---:|---:|
| Top-3 | **35%** | **10.42%** | **15%** | **3.00** | **33.05** | — |
| Cond. Top-3 τ=.005 δ=.005 | 35% | 8.18% | 20% | 4.25 | 45.65 | 60.0% |
| Cond. Top-3 τ=.010 δ=.005 | 35% | 8.18% | 20% | 4.25 | 45.65 | 72.5% |
| Cond. Top-3 τ=.020 δ=.010 | 35% | 6.94% | 20% | 5.18 | 54.55 | 87.5% |
| Cond. Top-5 τ=.010 δ=.010 | 35% | 5.49% | 20% | 7.38 | 64.45 | 92.5% |
| Cond. Top-5 τ=.020 δ=.010 | 35% | 5.49% | 20% | 7.38 | 64.45 | 97.5% |

이 설정에서는 Conditional BADP가 Top-3 search success를 높이지 못했고 F1과 비용은 악화되었다.

또한 activation rate가 60~97.5%로 지나치게 높아 실제로는 always-on에 가까운 경우가 많았다.

따라서 다음 두 문제를 분리해야 한다.

```text
A. Boundary 주변 후보를 추가 보존하면 도움이 되는가?
B. 어느 boundary에서 추가 보존을 켜야 하는가?
```

WN18RR에서는 A에 긍정적 신호가 있었으나 WebQSP는 단순 `ΔK ≤ τ` 규칙이 B를 충분히 해결하지 못함을 보여준다.

---

# 20. 코드 오류와 평가 해석 교정 내역

| 항목 | 잘못 해석될 수 있었던 내용 | 교정 |
|---|---|---|
| CONAN 100% | 실제 CONAN 자연어 benchmark 성능처럼 보임 | CONAN gold relation을 재료로 우리가 생성한 controlled reasoner verification |
| CONAN 75→100 | Perspective Tableau가 CONAN에서 +25%p 향상한 것처럼 보임 | Synthetic Controlled Scope n=80 결과. CONAN benchmark 아님 |
| CONAN implicit recall 100% | 실제 secret/inferred relation 탐지 성능처럼 보임 | ontology semantics로 생성한 synthetic implicit contradiction case 단위검증 |
| Natural-language MAGIC | provenance metadata가 scorer input에 섞인 실행 | 수정 전 값 전부 폐기 |
| WN18RR Frozen | Top-1 16%와 Rashomon coverage 42%를 같은 정확도로 비교 | 서로 다른 지표. 후보 보존 진단으로만 사용 |
| MAGIC world 평균 수 | 반올림 값 혼재 | row 7.34 / query 4.08 / path-query 1.45로 통일 |
| MAGIC DeBERTa 개선폭 | 반올림 차이 혼재 | +18.71 / +14.68 / +8.33%p로 통일 |
| MAGIC Boundary | δ 미표기 | Top-3 δ=.01 / Top-5 δ=.01로 명시 |
| WN18RR n=50 이전 failure | 평가 전체 실패처럼 보임 | summary key 후처리 오류. 수정 run 32852520635 전체 성공 |
| WebQSP Conditional | success만 보면 정책 품질 판단 불충분 | F1, regret, width, expansion, activation을 함께 평가 |

### CONAN에 대한 가장 중요한 결론

현재 저장소에는 **공식 natural-language CONAN benchmark에 대한 우리 방법의 end-to-end 성능을 증명하는 결과 artifact가 없다.**

따라서 CONAN은 현재:

1. perspective-aware relation reasoning 문제의 실제 외부 근거
2. gold relation proposition 및 relation inventory의 일부 source
3. reasoner controlled verification을 만들기 위한 재료

로만 사용한다.

---

# 21. 코드 오류를 제외하고 실제로 개선된 결과

아래 표는 **같은 지표를 baseline과 비교했을 때 실제 개선이 확인된 결과만** 모은 것이다.

CONAN-derived 100%는 baseline comparison이 없고 자연 benchmark가 아니므로 이 표에서 제외한다.

| 실험 | Baseline | 방법 | 같은 지표의 변화 | 주의점 |
|---|---|---|---|---|
| Synthetic Controlled Scope n=80 | Accuracy 75%, Macro F1 66.67% | Perspective Tableau | **100%, 100%** | 합성 논리 단위검증 |
| Synthetic Explanation n=20 | Coverage 50% | Rashomon enumeration | **100%** | 설명 보존 |
| MAGIC structured | Row recall 22.79% | DeBERTa | **41.50%, +18.71%p** | 공식 자연어 MAGIC 아님 |
| MAGIC structured | Query recall 16.86% | DeBERTa | **31.53%, +14.68%p** | structured 진단 |
| MAGIC structured | Exact LOC 7.14% | DeBERTa | **15.48%, +8.33%p** | structured 진단 |
| DAFNA n=100 | Exact 61% | PW marginal | **62%, +1%p** | truth selection |
| DAFNA n=100 | Author F1 82.88% | PW marginal | **84.13%, +1.25%p** | truth selection |
| WN18RR iterative n=10 | Success 60% | Relative-loss .50 | **70%, +10%p** | 폭 크게 증가 |
| MAGIC recoverable n=420 | Top-3 survival 94.76% | Boundary Top-3 δ=.01 | **97.86%, +3.10%p** | Gold F1 감소 |
| MAGIC high-branching n=32 | Top-3 survival 37.50% | Boundary Top-3 δ=.01 | **78.13%, +40.63%p** | width 증가 |
| MAGIC high-branching n=32 | Top-5 survival 75.00% | Boundary Top-5 δ=.01 | **84.38%, +9.38%p** | width 증가 |
| WN18RR iterative n=20 | Top-3 success 50% | Boundary Top-3 δ=.005 | **55%, +5%p** | strict width-match에서는 동률 |
| WN18RR iterative n=20 | Top-5 success 55% | Boundary Top-5 δ=.010 | **60%, +5%p** | 비용 증가 |
| WN18RR iterative n=20 | Top-5 success 55% | Boundary Top-5 δ=.050 | **65%, +10%p** | 비용·noise 크게 증가 |
| WN18RR iterative n=50 | Top-3 success 40% | Boundary Top-3 δ=.005 | **46%, +6%p** | Viability F1 소폭 감소 |
| WN18RR iterative n=50 | Top-3 regret 58% | Boundary Top-3 δ=.005 | **52%, -6%p** | 낮을수록 좋음 |
| WN18RR iterative n=50 | Top-5 success 56% | Boundary Top-5 δ=.010 | **60%, +4%p** | 비용 증가 |
| WN18RR iterative n=50 | Top-5 regret 42% | Boundary Top-5 δ=.010 | **38%, -4%p** | 낮을수록 좋음 |

WN18RR Frozen의 `Top-1 16%`와 `Rashomon coverage 42%`는 서로 다른 지표이므로 이 개선표에서 제외한다.

WebQSP Conditional BADP도 Top-3 대비 search success가 개선되지 않았으므로 개선표에 넣지 않는다.

---

# 22. 실패하거나 제한된 가설

## 22.1 Possible Worlds가 자동으로 최종 정답을 해결한다

지지되지 않는다.

DAFNA:

```text
Gold-world coverage = 93%
Best exact selection = 62%
```

Possible Worlds는 후보 보존 구조이지 자동 truth selector가 아니다.

## 22.2 Ontology/Tableau만으로 실제 multi-hop relation을 모두 해결한다

지지되지 않는다.

MAGIC:

```text
Candidate path coverage = 68.03%
Ontology/Tableau conflict detection = 5.44%
```

## 22.3 Global Rashomon band가 항상 Top-K보다 우수하다

기각하였다.

WN18RR iterative n=10에서 Global .05/.10은 Top-K 60%보다 낮은 40% success였다.

## 22.4 후보를 많이 남길수록 항상 좋다

기각하였다.

MAGIC no-pruning은 survival 100%였지만 Gold F1은 63.64%로 낮았다.

## 22.5 BADP가 같은 비용에서 항상 Top-K보다 우수하다

아직 지지되지 않는다.

WN18RR n=20 strict nearest-width 비교에서는 success gain이 없었다.

## 22.6 Boundary margin 하나면 위험한 경계를 충분히 찾는다

현재로서는 지지되지 않는다.

WebQSP에서 Conditional BADP activation rate가 최대 97.5%까지 올라갔고 Top-3보다 성능이 좋아지지 않았다.

## 22.7 CONAN에서 100% 성능을 달성하였다

명확히 폐기한다.

100%는 공식 CONAN natural-language benchmark 결과가 아니라 controlled verification 결과이다.

---

# 23. 현재까지 가장 강한 관찰

### 관찰 1. Branching이 큰 구간에서 fixed Top-K가 특히 취약하다

MAGIC high-branching subset에서 Top-3 gold-path survival은 37.50%까지 하락하였다.

### 관찰 2. 실제 Top-K boundary 주변을 소량 추가 보존하면 일부 환경에서 success/regret가 개선된다

WN18RR n=20과 n=50에서 같은 방향이 반복되었다.

### 관찰 3. 더 많이 보존하면 precision과 비용이 나빠질 수 있다

따라서 목표는 최대 survival이 아니다.

```text
좋은 pruning 정책
= 중요한 경로 보존
+ 보존 집합의 유효성
+ 감당 가능한 탐색 비용
```

### 관찰 4. Risk detector와 preservation operator는 다른 문제다

```text
BADP = 무엇을 추가 보존할 것인가?
Risk detector = 언제 BADP를 켤 것인가?
```

WN18RR에서는 boundary-local preservation에 긍정적 신호가 있었지만 WebQSP에서는 margin-only detector가 충분하지 않았다.

---

# 24. 다음 단계: Boundary Risk

현재 다음 위험 신호를 함께 보는 방향이 자연스럽다.

```text
ΔK              = K/K+1 score margin
Branching        = 현재 후보 수
Score Entropy    = 후보 점수 분포의 불확실성
Boundary Density = cutoff 근처 후보 밀도
Depth            = 현재 탐색 깊이
Remaining Hops   = 남은 hop budget
```

개념적으로:

```text
Risk(k) = f(ΔK, Branching, Entropy, BoundaryDensity, Depth, RemainingHops)
```

그리고:

```text
if Risk(k) is high:
    BADP를 제한적으로 활성화
else:
    Top-K 유지
```

최종 목적은 단순 adaptive beam width가 아니라:

> **실제로 Pruning Regret가 발생할 가능성이 높은 비가역적 경계를 식별하고, 그때만 추가 탐색 예산을 쓰는 것**

이다.

---

# 25. 재현 가능한 주요 실행

| 실험 | Run / Commit | Artifact / 결과 |
|---|---|---|
| CONAN-derived controlled verification | commit `98b8d475...` | `preliminary_controlled_metrics.json` — 공식 CONAN 성능 아님 |
| Synthetic Controlled Scope | commit `457a6ebf...` | `ablation_metrics.json` — 완전 합성 |
| MAGIC Possible Worlds | Run `32725453943` | Artifact `9519356207` |
| MAGIC DeBERTa structured scoring | Run `32730398659` | Artifact `9521415589` |
| DAFNA Possible Worlds | Run `32726434311` | Artifact `9519739380` |
| WN18RR Frozen n=50 | Run `32799621678` | Artifact `9546119681` |
| WN18RR Relative-loss n=10 | Run `32813194834` | Artifact `9550550657` |
| MAGIC External Gold pruning | Run `32817516186` | Artifact `9551919328` |
| WN18RR Iterative budgeted n=20 | Run `32819877566` | Artifact `9553138233` |
| WebQSP Conditional BADP n=20 | Run `32829786375` | Artifact `9556981080` |
| WN18RR Conditional BADP n=50 | Run `32852520635` | Artifact `9566776300` |

---

# 26. 현재 결론

현재까지 코드 오류와 평가 설계 오해를 제외하면 다음처럼 정리할 수 있다.

1. **CONAN 100%는 공식 benchmark 성능이 아니며 controlled reasoner verification이다.**
2. **75% → 100% Perspective Tableau 역시 Synthetic Controlled Scope 결과이지 CONAN 결과가 아니다.**
3. Perspective separation은 합성 논리 환경에서 contradiction scope 구분에 유효했다.
4. Possible Worlds는 여러 해석을 보존하는 데 유용했지만 final selection을 자동으로 해결하지 않았다.
5. 실제 ontology는 multi-hop relation semantics를 모두 갖고 있지 않아 relation candidate prediction이 필요했다.
6. Structured MAGIC에서 semantic scorer는 weak lexical scoring보다 후보 ranking을 개선했다.
7. 좋은 candidate가 있어도 pruning에서 사라질 수 있으며 이를 Pruning Regret로 분리해 측정할 수 있다.
8. Fixed Top-K는 특히 high-branching 구간에서 gold/viable path를 크게 잃었다.
9. Boundary-local preservation은 MAGIC과 WN18RR에서 survival 또는 success 개선 신호를 반복적으로 보였다.
10. 그러나 추가 보존은 precision/F1과 탐색 비용을 악화시킬 수 있다.
11. Simple boundary-margin Conditional BADP는 WebQSP에서 충분히 선택적으로 동작하지 않았다.
12. 따라서 다음 핵심은 BADP 자체보다 **어떤 경계가 실제로 위험한지를 추정하는 Boundary Risk 모델**이다.

현재 논문에서 가장 안전한 핵심 주장은 다음과 같다.

> **고정 Top-K는 다중 홉 탐색 비용을 안정적으로 제한하지만, 후보 경쟁이 큰 구간에서는 이후 정답 또는 증거로 이어질 수 있는 경로를 비가역적으로 제거할 수 있다. MAGIC과 WN18RR에서는 Top-K 경계 주변 후보를 제한적으로 추가 보존했을 때 경로 생존 또는 search success가 개선되는 신호가 반복적으로 관찰되었다. 그러나 추가 보존은 precision과 비용을 악화시킬 수 있고, WebQSP에서는 단순 margin 기반 Conditional BADP가 개선되지 않았다. 따라서 현재 핵심 과제는 Pruning Regret 위험이 높은 경계를 더 정확하게 식별하는 것이다.**
