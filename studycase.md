# Study Case — Rashomon / Tableau / Multi-hop Pruning 연구 진화 기록

## 0. 문서 목적

이 문서는 현재 논문의 최종 주장만 정리하는 문서가 아니다.

연구를 진행하면서 실제로 시도했던 가설, 방법, 데이터셋, 실패한 접근, 유의미했던 결과, 그리고 그 결과 때문에 연구 질문이 어떻게 바뀌었는지를 한 번에 추적하기 위한 **연구 의사결정 기록(Study Case / Research Log)** 이다.

핵심 질문은 처음부터 현재까지 다음처럼 변화했다.

```text
초기
상반된 multi-hop 주장을 어떻게 해결할 것인가?
        ↓
Rashomon Worlds + Ontology + Tableau
        ↓
경로는 찾지만 논리적 conflict 확정이 어려움
        ↓
Semantic scorer(DeBERTa) 도입
        ↓
좋은 evidence가 있어도 search/pruning 단계에서 먼저 사라질 수 있음
        ↓
Preserve before Resolve
        ↓
Fixed Top-K의 premature pruning 측정
        ↓
Global Rashomon / Relative-loss / Boundary-aware pruning 비교
        ↓
현재
상반된 evidence를 해결하기 전에, 유효한 competing path를
얼마나 안전하고 효율적으로 보존할 수 있는가?
```

현재 논문은 **Resolve**가 아니라 **Preserve**를 다룬다.

---

# 1. 최초 연구 아이디어

## 1.1 처음 주장하려 했던 것

초기 연구의 중심 아이디어는 다음이었다.

> **Multi-hop reasoning에서 서로 상반되는 설명 또는 주장이 존재할 때 하나의 경로를 조기에 확정하지 말고, 여러 plausible world를 유지한 뒤 ontology와 Tableau를 이용해 논리적으로 일관되지 않는 world를 제거하여 최종 주장을 결정한다.**

초기 파이프라인은 다음과 같았다.

```text
Query / Claim
    ↓
Multi-hop graph search
    ↓
복수의 evidence path
    ↓
Rashomon / Possible Worlds
    ↓
Ontology constraints
    ↓
Tableau consistency checking
    ↓
consistent worlds only
    ↓
최종 claim / explanation
```

초기 핵심 개념은 두 가지였다.

1. **Rashomon / Possible Worlds**
   - 하나의 최적 설명만 즉시 선택하지 않는다.
   - 비슷하게 가능한 여러 설명을 유지한다.

2. **Tableau**
   - 여러 explanation 중 ontology constraint와 충돌하는 world를 논리적으로 제거한다.

즉 초기 연구는:

```text
Competing hypotheses
        +
Logical consistency
        ↓
Conflict resolution
```

을 한 논문 안에서 해결하려 했다.

---

# 2. Controlled Ontology/Tableau 검증

## 2.1 목적

가장 먼저 확인한 것은 자연어 성능이 아니라 **Tableau reasoner 자체가 의도한 contradiction scope를 정확히 구분할 수 있는가**였다.

Controlled benchmark에서 다음 4개 클래스를 구성했다.

- consistent
- divergence
- intra-contradiction
- inter-contradiction

총 `n=80`, class별 20개였다.

## 2.2 비교 방법

### Vanilla merged Tableau

모든 perspective의 assertion을 하나의 ABox로 합친 뒤 contradiction 존재 여부를 확인했다.

문제는 contradiction이 발견되더라도:

```text
한 perspective 내부에서 이미 발생한 contradiction인지
vs
서로 다른 perspective를 합쳐서 발생한 contradiction인지
```

구분하기 어렵다는 점이었다.

### Perspective-aware Tableau

각 perspective를 분리해서 reasoning한 뒤 perspective 간 관계를 비교했다.

### Rashomon-Tableau

복수 explanation / perspective를 유지한 상태에서 contradiction scope를 계산했다.

## 2.3 실제 결과

| Method | Accuracy | Macro F1 |
|---|---:|---:|
| Vanilla merged Tableau | 75.0% | 66.67% |
| Perspective Tableau | **100%** | **100%** |
| Rashomon Tableau | **100%** | **100%** |

개선폭:

```text
Perspective vs Vanilla
Accuracy  +25.0pp
Macro F1  +33.33pp
```

하지만 중요한 해석은 다음이다.

> 이 결과는 **generic natural-language reasoning 성능이 아니라 controlled contradiction-scope classification capability**를 검증한 것이다.

또한 이 실험에서는 Perspective Tableau와 Rashomon Tableau가 동일한 class decision을 냈다.

즉 이 단계만으로는:

> Rashomon이 classification accuracy를 높인다.

고 주장할 수 없었다.

## 2.4 Explanation coverage 실험

각 case에 independent minimal contradiction 2개가 존재하도록 만든 controlled 20-case에서는:

| Method | Minimal explanation coverage |
|---|---:|
| Single-path explanation | 50% |
| Rashomon enumeration | **100%** |

즉 Rashomon의 초기 강점은 **최종 class accuracy보다 multiple valid explanation coverage**에서 더 명확하게 나타났다.

이 결과는 이후 연구의 중요한 힌트가 되었다.

```text
Rashomon의 가치
≠ 항상 더 높은 final accuracy

Rashomon의 가치
= 중요한 alternative explanation을 잃지 않는 것
```

Source:

```text
results/ablation_metrics.json
```

---

# 3. CONAN controlled contradiction verification

Gold relation proposition을 이용해 explicit / implicit contradiction을 검증했다.

Dataset:

```text
CONAN Gold relation propositions
Story: 655-The Mysterious Case of Zhangdong Town
n = 80
```

구성:

| Type | n |
|---|---:|
| contradiction | 40 |
| consistent | 20 |
| divergence | 20 |

Contradiction subtype:

- explicit: 20
- implicit hierarchy: 10
- implicit inverse: 10

실행 결과:

```text
Accuracy = 100%
Macro F1 = 100%
Implicit contradiction recall = 100%
```

하지만 이 값도 **ontology semantics를 이용해 생성한 controlled label에 대한 reasoner correctness test**였다.

따라서 자연어 일반화 성능으로 사용하지 않았다.

Source:

```text
results/preliminary_controlled_metrics.json
```

---

# 4. DAFNA-EA — Possible Worlds / Truth Discovery 시도

## 4.1 연구 질문

다음 단계에서는 단순 contradiction detection보다 실제로:

> 여러 source가 서로 다른 값을 주장할 때 하나의 값을 너무 빨리 확정하지 않고 possible worlds를 유지하면 truth discovery가 개선되는가?

를 확인했다.

Dataset:

```text
DAFNA-EA Books / AuthorsNamesList gold subset
Gold books = 100
Source-object claims = 1,999
Sources = 227
```

## 4.2 비교 방법

- Possible-world uniform
- Possible-world hard commit reliability
- Possible-world marginal reliability
- Prior atomic resolution
- Official TruthFinder
- Official AccuSim
- 2-Estimates
- 3-Estimates
- Accu

## 4.3 실제 결과

| Method | Exact-set Accuracy | Author F1 |
|---|---:|---:|
| Possible-world uniform | 58% | 80.38% |
| Hard commit reliability | 61% | 84.04% |
| **Marginal possible world** | **62%** | **84.13%** |
| Prior atomic resolution | 61% | 82.88% |
| TruthFinder | 57% | 66.85% |
| AccuSim | 57% | 66.18% |
| 2-Estimates | 54% | 65.28% |
| 3-Estimates | 53% | 65.45% |
| Accu | 53% | 65.45% |

Possible-world candidate generation은:

```text
Gold world coverage = 93%
Mean candidate worlds = 27.94
Max candidate worlds = 256
```

였지만 실제 exact selection은 62%였다.

## 4.4 얻은 결론

이 결과는 possible world의 가치가 전혀 없다는 결과는 아니었다.

```text
Marginal world vs hard commit
Exact +1pp

Marginal world vs prior atomic
Exact +1pp
Author F1 +1.25pp
```

정도의 작은 개선이 있었다.

그러나 더 중요한 관찰은:

> **Candidate generation이 gold를 93% 포함해도 ranking/calibration이 좋지 않으면 final selection은 62%에 그친다.**

였다.

즉 이후 연구에서는:

```text
좋은 후보를 생성하는 것
≠
좋은 후보를 선택하는 것
```

을 분리해서 생각하게 됐다.

Validated run:

```text
32726434311
Artifact 9519739380
```

Sources:

```text
results/dafna_possible_worlds_summary.json
results/dafna_official_comparison.json
```

---

# 5. MAGIC — Ontology + Bidirectional Tableau

## 5.1 원래 기대

MAGIC multi-hop conflict benchmark에서 다음을 시도했다.

```text
Forward graph path
+
Reverse graph path
+
Ontology closure
+
Tableau q / not-q verification
```

최대 hop은 4였다.

여기서 기대한 것은:

> multi-hop path가 conflict evidence를 연결해주고 Tableau가 이를 논리적으로 확정할 수 있을 것이다.

였다.

## 5.2 실제 결과

Aggregate:

| Metric | Result |
|---|---:|
| Single-hop legacy direct detection | 97.56% |
| Multi-hop legacy direct detection | 33.16% |
| Single-hop ontology/Tableau detection | 42.68% |
| **Multi-hop ontology/Tableau detection** | **5.44%** |
| Single-hop bidirectional path coverage | 61.38% |
| **Multi-hop bidirectional path coverage** | **68.03%** |

여기서 매우 중요한 차이가 발생했다.

```text
Multi-hop path coverage = 68.03%
Ontology/Tableau conflict detection = 5.44%
```

즉 **경로 자체는 상당 부분 찾아지지만, 해당 경로가 conflict임을 hard logical constraint만으로 증명하지 못했다.**

이유는 MAGIC의 자연어/관계 conflict가 항상:

- explicit negation
- declared exclusivity
- ontology incompatibility

로 표현되는 것이 아니기 때문이다.

따라서 이 단계에서 처음으로 다음 한계가 명확해졌다.

> **Graph reachability와 logical contradiction verification은 다른 문제다.**

그리고 Tableau가 약해서가 아니라:

> hard ontology constraint가 없는 semantic contradiction을 Tableau만으로 만들 수 없다.

는 문제가 있었다.

Validated run:

```text
32720349460
Artifact 9517514860
```

Source:

```text
results/magic_bidirectional_tableau_metrics.json
```

---

# 6. MAGIC — Rashomon Possible Worlds 첫 실험

## 6.1 아이디어

Tableau만으로 semantic conflict를 판정하기 어려웠기 때문에 관계 해석 자체를 여러 world로 유지했다.

Ablation:

```text
B1 Static hard ontology + Tableau
B2 Single-world early commitment
B3 Possible-world existential retention
B4 Weighted possible-world marginalization
```

Scorer는 이 단계에서는 weak lexical relation prior였다.

## 6.2 실제 결과

Dataset:

```text
588 rows
1,056 queries
```

| Method | Result |
|---|---:|
| B1 static Tableau row conflict recall | 5.44% |
| B1 static Tableau query recall | 4.45% |
| B2 early commit row recall | 29.93% |
| B2 early commit query recall | 22.63% |
| B3 gold-world query recall | **39.39%** |
| B3 structured exact LOC | **29.42%** |
| B4 weighted world row recall | 22.79% |
| B4 weighted world query recall | 16.86% |
| B4 structured exact LOC | 7.14% |

World statistics:

```text
Mean worlds / row = 7.36
Mean worlds / query = 4.10
Mean candidate paths / query = 1.46
```

## 6.3 해석

B3에서 gold world가 존재하는지 보는 existential retention은 비교적 높은 coverage를 보였다.

하지만 실제 weighted world ranking(B4)은 오히려 낮았다.

즉 다시 같은 문제가 나타났다.

```text
좋은 world가 후보에 존재
        ↓
그러나 scorer가 좋은 world를 선택하지 못함
```

이 시점에서 연구의 병목은 Tableau보다 **semantic ranking / scoring** 쪽으로 이동했다.

Validated run:

```text
32725453943
Artifact 9519356207
```

Source:

```text
results/magic_possible_worlds_summary.json
```

---

# 7. DeBERTa Semantic World Scorer 도입

## 7.1 목적

Weak lexical prior를 실제 NLI semantic scorer로 교체하면 candidate world/path를 더 잘 구분할 수 있는지 확인했다.

Model:

```text
MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli
```

출력은:

```text
Support / Contradiction / Unresolved
```

였다.

## 7.2 실제 결과

MAGIC 588 rows / 1,056 queries:

| Metric | Weak lexical | DeBERTa | Gain |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71pp** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68pp** |
| Structured exact LOC | 7.14% | **15.48%** | **+8.33pp** |

추가:

```text
Query gold path selection = 22.06%
Mean worlds/query = 4.09
Mean paths/query = 1.45
```

이 결과는 과거 연구 중 현재도 가장 중요한 positive signal 중 하나다.

## 7.3 현재 해석

이 결과를 이제 다음처럼 사용한다.

> DeBERTa가 multi-hop search를 해결했다.

가 아니다.

정확한 해석은:

> **유용한 candidate path가 존재할 때 semantic NLI scoring은 weak lexical prior보다 의미 있는 conflict-path discrimination을 제공한다.**

이다.

즉 DeBERTa는 현재 논문에서도 버리지 않고 **semantic scorer validity evidence**로 유지한다.

Run:

```text
32730398659
Artifact 9521415589
```

Source:

```text
results/magic_deberta_worlds_summary.json
```

---

# 8. 연구 질문의 첫 번째 큰 전환

여기까지의 연구에서 반복적으로 같은 패턴이 나타났다.

```text
1. Gold/좋은 path가 후보 공간에 존재한다.
2. 그러나 ranking/selection에서 제거되거나 선택되지 않는다.
3. 제거된 뒤에는 Tableau/semantic verifier가 아무리 좋아도 복구할 수 없다.
```

그래서 연구 질문을 다음처럼 바꿨다.

### 이전 질문

> 상반된 multi-hop 주장을 어떻게 최종 해결할 것인가?

### 변경된 질문

> **상반된 주장을 해결하기 전에, downstream verifier가 검사해야 할 competing evidence를 search/pruning 단계에서 먼저 잃고 있지는 않은가?**

즉:

```text
Resolve
```

보다 앞에:

```text
Preserve
```

가 필요하다고 판단했다.

현재 연구 분리:

```text
Paper 1: Preserve
    pruning / path survival / information loss

Paper 2: Resolve
    DeBERTa S/C/U + Possible Worlds + Ontology/Tableau
```

---

# 9. WN18RR Frozen-score Pruning Diagnostic

## 9.1 목적

고정된 scorer score에서 pruning policy만 바꾸면 gold hypothesis survival이 어떻게 변하는지 측정했다.

Protocol:

```text
Dataset = WN18RR
n = 50
Candidate relations = 11
Scorer = DeBERTa
Gold = evaluation only
```

이 실험은 iterative search가 아니라 **frozen relation-hypothesis pruning diagnostic**이다.

## 9.2 실제 결과

| Policy | Gold survival | Pruning regret | Avg active |
|---|---:|---:|---:|
| Top-1 | 16% | 84% | 1.00 |
| Top-3 | 32% | 68% | 3.00 |
| Top-5 | 40% | 60% | 5.00 |
| Threshold .7 | 70% | 30% | 7.08 |
| Threshold .5 | 78% | 22% | 8.40 |
| Rashomon ε=.01 | 16% | 84% | 1.98 |
| Rashomon ε=.03 | 26% | 74% | 3.22 |
| **Rashomon ε=.05** | **42%** | **58%** | **3.82** |
| **Rashomon ε=.10** | **58%** | **42%** | **5.08** |
| No pruning | 100% | 0% | 11.00 |

핵심 비교:

```text
Rashomon .05 vs Top-3
Survival +10pp
Width +0.82
```

```text
Rashomon .05 vs Top-5
Survival +2pp
Width -1.18
```

```text
Rashomon .10 vs Top-5
Survival +18pp
Width +0.08
```

이 결과만 보면 near-optimal retention이 매우 유망해 보였다.

Source run:

```text
32799621678
Artifact 9546119681
```

Source:

```text
results/wn18rr_pruning_policy_ablation_50.json
```

---

# 10. Iterative Multi-hop Search — Naive Additive Rashomon 실패

Frozen score에서 좋은 결과가 나왔기 때문에 실제 반복 탐색 안에 pruning operator를 넣었다.

Search:

```text
Expand
  ↓
DeBERTa edge score
  ↓
path score = mean edge support
  ↓
Prune
  ↓
Expand again
```

10-query pilot 결과:

| Policy | Search success | Query pruning regret | Avg width | Avg expanded |
|---|---:|---:|---:|---:|
| Top-1 | 20% | 80% | 1.00 | 10.9 |
| **Top-3** | **60%** | **40%** | 2.67 | 21.3 |
| **Top-5** | **60%** | **40%** | 3.88 | 28.1 |
| Additive Rashomon .05 | 40% | 60% | 2.65 | 23.7 |
| Additive Rashomon .10 | 40% | 60% | 3.59 | 28.5 |

즉 frozen relation-level 결과와 반대로 additive Rashomon이 실제 iterative search에서는 실패했다.

대표 failure:

```text
best score ≈ 0.15 ~ 0.39
```

같이 raw score scale이 낮은 query에서:

```text
s >= s* - ε
```

가 예상보다 aggressive하게 작동했다.

## 10.1 중요하게 얻은 negative finding

> **Near-optimality를 raw score absolute gap으로 정의하면 score calibration/scale에 따라 오히려 premature pruning이 증가할 수 있다.**

따라서 이 결과는 숨기지 않고 현재 연구의 핵심 negative evidence로 남긴다.

Run:

```text
32812403726
Artifact 9550470150
```

---

# 11. Relative-loss Rashomon

Naive additive epsilon의 score-scale 문제를 보완하기 위해 loss space에서 near-optimality를 정의했다.


after support score `s(p)`:

```text
L(p) = 1 - s(p)
```

Relative-loss set:

```text
L(p) <= (1 + ε)L*
```

지원점수 형태:

```text
s(p) >= s* - ε(1-s*)
```

의도:

```text
best score 낮음
→ scorer uncertainty 큼
→ tolerance 넓어짐

best score 높음
→ scorer confidence 큼
→ tolerance 좁아짐
```

## 11.1 실제 10-query 결과

| Policy | Success | Regret | Avg width | Expanded |
|---|---:|---:|---:|---:|
| Top-3 | 60% | 40% | 2.67 | 21.3 |
| Top-5 | 60% | 40% | 3.88 | 28.3 |
| Additive .10 | 40% | 60% | 3.62 | 28.5 |
| Relative-loss .25 | 50% | 50% | 4.09 | 31.4 |
| **Relative-loss .50** | **70%** | **30%** | **5.97** | 31.4 |

즉 scale-aware formulation은 additive failure를 일부 회복했다.

그러나:

```text
Top-5 width 3.88
Relative-loss .50 width 5.97
```

로 cost가 증가했다.

따라서 결론은:

> scale-aware preservation은 효과가 있을 수 있지만, 단순 survival만 보고 좋다고 할 수 없고 비용을 같이 봐야 한다.

Run:

```text
32813194834
Artifact 9550550657
```

---

# 12. MAGIC — Conflict Evidence Preservation으로 문제 재정의

## 12.1 왜 MAGIC을 다시 사용했는가

WN18RR은 multi-hop path search에는 좋지만 explicit conflict benchmark는 아니다.

따라서 원래 연구 주제였던:

```text
상반된 evidence를 pruning이 잃는가?
```

를 직접 측정하기 위해 MAGIC으로 돌아왔다.

중요한 변경은 **DeBERTa가 gold를 만들지 않게 한 것**이다.

Gold conflict path는 MAGIC의:

```text
original_triplet ↔ perturb_triplet provenance
```

로 외부 정의했다.

Selection score는 side-agnostic하게:

```text
relevance = Support + Contradiction = 1 - Unresolved
```

를 사용했다.

즉 support와 contradiction 모두 보존 가치가 있는 evidence로 취급했다.

## 12.2 Protocol

```text
588 rows
1,056 queries
618 queries with candidate path
420 queries with externally-gold conflict path recoverable before pruning
```

Primary pruning evaluation은 recoverable 420 query에만 수행했다.

이유:

> pruning 전에 gold path 자체가 없었다면 그것은 retrieval failure이지 pruning failure가 아니다.

---

# 13. MAGIC Preservation + Retained-set Validity 실제 결과

## 13.1 전체 recoverable n=420

| Policy | Conflict survival | Gold precision | Gold recall | Gold F1 | Avg width |
|---|---:|---:|---:|---:|---:|
| Top-1 | 80.71% | **80.71%** | 80.52% | **80.62%** | **1.00** |
| Top-3 | 94.76% | 59.38% | 94.77% | 73.01% | 1.60 |
| Top-5 | **98.10%** | 55.07% | 98.10% | 70.54% | 1.79 |
| Additive .05 | 94.76% | 54.00% | 94.54% | 68.74% | 1.75 |
| Additive .10 | 97.14% | 50.18% | 97.15% | 66.18% | 1.94 |
| Relative-loss .25 | 83.81% | 74.26% | 83.61% | 78.66% | 1.13 |
| **Boundary Top-3 + .001** | **97.86%** | 55.30% | **97.86%** | 70.67% | **1.77** |
| Boundary Top-5 + .001 | 98.81% | 52.93% | 98.81% | 68.93% | 1.87 |
| No pruning | 100% | 46.67% | 100% | 63.64% | 2.15 |

## 13.2 매우 중요한 validity 결과

이 실험에서 다음 사실이 명확해졌다.

```text
더 많이 남길수록 survival은 증가
하지만 precision은 감소
```

예:

```text
Top-1
Survival 80.71%
Precision 80.71%
```

vs

```text
No pruning
Survival 100%
Precision 46.67%
```

즉:

> **More retained paths ≠ better reasoning.**

현재 논문에서 반드시:

```text
Preservation
×
Retained-set validity
×
Search cost
```

를 동시에 보는 이유다.

---

# 14. High-branching MAGIC 결과

현재 가장 강하게 증명된 조건은 **candidate branching**이다.

Gold conflict path survival:

| Candidate regime | Top-3 | Top-5 | Rashomon .10 |
|---|---:|---:|---:|
| overall | 94.76% | 98.10% | 97.14% |
| paths >=3 | 72.84% | 90.12% | 91.36% |
| paths >=4 | 52.17% | 82.61% | 93.48% |
| paths >=5 | **37.50%** | **75.00%** | **96.88%** |

즉 candidate가 많아질수록 fixed cardinality의 survival이 급격히 떨어졌다.

특히 paths >=5, n=32:

| Policy | Survival | Gold precision | Gold F1 | Width |
|---|---:|---:|---:|---:|
| Top-3 | 37.50% | 12.50% | 18.75% | 3.00 |
| Top-5 | 75.00% | **15.00%** | **25.00%** | 5.00 |
| Rashomon .05 | 84.38% | 11.95% | 20.93% | 7.06 |
| Rashomon .10 | **96.88%** | 11.52% | 20.60% | 8.41 |
| Boundary Top-5+.001 | 84.38% | 13.78% | 23.68% | 6.13 |
| No pruning | 100% | 10.26% | 18.60% | 9.75 |

이 결과가 현재 논문의 가장 중요한 empirical motivation이다.

> **Fixed-width pruning은 candidate competition이 커질수록 brittle해진다.**

하지만 broad Rashomon은 noise를 많이 남긴다.

따라서 새로운 질문이 생겼다.

> 모든 near-best 후보를 남기지 말고, 실제 pruning boundary 근처의 near-tie만 추가로 살릴 수는 없는가?

Run:

```text
32817516186
Artifact 9551919328
```

Source:

```text
results/magic_conflict_preservation_summary.json
```

---

# 15. Boundary-Aware Delayed Pruning (BADP)

## 15.1 아이디어

Fixed Top-K:

```text
1위 keep
2위 keep
...
K위 keep
---------------
K+1위 drop
```

문제는:

```text
s_(K) = 0.812
s_(K+1) = 0.809
```

처럼 거의 동일한데도 rank 하나 차이 때문에 K+1을 삭제한다는 점이다.

그래서 global best 주변이 아니라 **실제 pruning boundary 주변만 delayed pruning**한다.

정렬된 score:

```text
s_(1) >= ... >= s_(K) >= s_(K+1) ...
```

BADP:

```text
B_(K,δ) = {p : s(p) >= s_(K) - δ}
```

즉:

```text
Top-K core
+
K-th cutoff와 δ 이내인 near-tie paths
```

이다.

## 15.2 MAGIC exploratory result

```text
Top-3
Survival 94.76%
Width 1.60
```

vs

```text
Boundary Top-3+.001
Survival 97.86%
Width 1.77
```

즉:

```text
Survival +3.10pp
Avg width +0.17
```

paired query result:

```text
Boundary only wins = 13
Top-3 only wins = 0
Both = 398
Neither = 9
```

Exploratory exact sign test:

```text
p = 0.000244
```

단 이 값은 boundary formulation을 본 뒤 선택한 exploratory 결과이므로 final confirmatory test로 취급하지 않는다.

---

# 16. 최신 Iterative Budget-matched BADP 실험 — n=20

## 16.1 목적

MAGIC frozen candidates에서만 나타난 BADP 효과가 실제 iterative multi-hop search에서도 유지되는지 확인했다.

Protocol:

```text
Dataset = WN18RR
n = 20
2~4 hop iterative evidence-path search
Scorer = DeBERTa edge support
Path score = mean edge support
Adaptive safety cap = 10
```

비교군:

- Top-3
- Top-5
- Global best-minus-epsilon
- Relative-loss
- BADP Top-3
- BADP Top-5

평가:

- Search success
- Query pruning regret
- Viability precision
- Viability recall
- Viability F1
- Avg active width
- Avg expanded candidates

Run:

```text
32819877566
Artifact 9553138233
Digest sha256:a81df2ee2277595a869e038e1de8a383c19faf9fe6284f7cf13d8f36fd90e7c2
```

## 16.2 실제 결과

| Policy | Success | Regret | Viability P | Viability R | Viability F1 | Width | Expanded |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Top-3** | 50% | 50% | **24.46%** | 53.57% | **33.58%** | 2.71 | 24.80 |
| **Top-5** | 55% | 45% | 20.22% | 57.89% | 29.97% | 4.06 | 32.35 |
| Global ε=.03 | 35% | 65% | 21.29% | 49.25% | 29.73% | 2.28 | 20.40 |
| Global ε=.05 | 40% | 60% | 19.89% | 52.24% | 28.81% | 2.63 | 20.70 |
| Global ε=.10 | 45% | 55% | 17.08% | 56.16% | 26.20% | 3.58 | 27.40 |
| Relative-loss .10 | 35% | 65% | 18.89% | 50.00% | 27.42% | 2.57 | 23.00 |
| Relative-loss .25 | 45% | 55% | 16.67% | 53.95% | 25.47% | 3.62 | 30.00 |
| Relative-loss .50 | 55% | 45% | 15.90% | 61.90% | 25.30% | 5.03 | 36.20 |
| BADP Top-3 δ=.001 | 50% | 50% | 22.84% | 53.57% | 32.03% | 2.90 | 26.50 |
| **BADP Top-3 δ=.005** | **55%** | **45%** | 22.32% | 56.82% | 32.05% | 3.34 | 27.15 |
| BADP Top-3 δ=.010 | 55% | 45% | 20.90% | 57.30% | 30.63% | 3.64 | 27.95 |
| BADP Top-5 δ=.001 | 55% | 45% | 18.64% | 57.89% | 28.21% | 4.40 | 33.40 |
| **BADP Top-5 δ=.010** | **60%** | **40%** | 18.18% | 61.86% | 28.10% | **5.00** | 35.10 |
| BADP Top-5 δ=.020 | 60% | 40% | 17.03% | 63.27% | 26.84% | 5.52 | 37.80 |
| **BADP Top-5 δ=.050** | **65%** | **35%** | 16.24% | **67.74%** | 26.20% | 6.16 | 38.25 |

## 16.3 현재 해석

### Top-3 anchor

```text
Top-3
Success 50%
Regret 50%
Width 2.71
```

BADP Top-3 δ=.005:

```text
Success 55%   (+5pp)
Regret 45%    (-5pp)
Width 3.34    (+0.64)
Expanded 27.15 vs 24.80
```

즉 small boundary relaxation으로 search success가 개선되는 signal이 있다.

### Top-5 anchor

```text
Top-5
Success 55%
Regret 45%
Width 4.06
Expanded 32.35
```

BADP Top-5 δ=.010:

```text
Success 60%   (+5pp)
Regret 40%    (-5pp)
Width 5.00
Expanded 35.10
```

BADP Top-5 δ=.050:

```text
Success 65%   (+10pp)
Regret 35%    (-10pp)
Width 6.16
Expanded 38.25
```

즉 BADP는 실제 iterative search에서도 **더 큰 budget을 쓰면서 pruning regret을 줄이고 search success를 올리는 방향**을 보였다.

그러나 validity precision은 감소한다.

예:

```text
Top-5 viability precision = 20.22%
BADP Top-5 δ=.050 = 16.24%
```

따라서 현재도 결론은 동일하다.

> **BADP가 더 많이 보존하면서 success를 올릴 수 있지만, retained-set quality와 cost까지 같이 최적화해야 한다.**

## 16.4 Pareto frontier

이번 20-query run에서 Search Success vs Expanded Candidates Pareto frontier에 포함된 주요 points:

```text
Global .01       25% / 16.8 expanded
Global .03       35% / 20.4
Global .05       40% / 20.7
Top-3            50% / 24.8
BADP Top-3 .005  55% / 27.15
BADP Top-5 .010  60% / 35.10
BADP Top-5 .050  65% / 38.25
```

현재까지의 결과에서는 BADP 계열이 **고비용 구간의 Pareto frontier에 실제로 진입**했다.

다만 `n=20`이므로 최종 superiority claim을 하기에는 작다.

---

# 17. 전체 연구에서 버린 주장 / 남긴 주장

## 17.1 더 이상 주장하지 않는 것

### A. Rashomon이 항상 Top-K보다 좋다

실제 iterative 10-query에서 additive Rashomon은:

```text
Top-3 / Top-5 = 60%
Additive = 40%
```

로 실패했다.

따라서 폐기.

### B. Tableau만으로 semantic multi-hop contradiction을 해결할 수 있다

MAGIC에서:

```text
Path coverage 68.03%
Logical detection 5.44%
```

였다.

따라서 hard logical constraints가 없는 semantic contradiction까지 Tableau가 해결한다고 주장하지 않는다.

### C. Adaptive pruning 자체가 novelty다

ToG 후속, adaptive GraphRAG, Flow-RAG 등 이미 adaptive search/pruning이 존재한다.

따라서 주장하지 않는다.

### D. Score ambiguity가 branching과 독립적으로 pruning failure를 만든다

현재 MAGIC top-2 margin quartile:

```text
0.00197 / 0.01307 / 0.04769
```

이지만 low margin과 high branching이 같이 나타나는 경향이 있어 독립 causal factor라고 말하기 어렵다.

현재는 hypothesis로만 남긴다.

---

# 18. 현재까지 지지되는 주장

## Claim 1 — Premature pruning은 실제 존재한다

Pruning 전에 viable/gold evidence가 있었는데 pruning 뒤 사라지는 case가 반복적으로 관찰됐다.

이를 Pruning Regret으로 정의한다.

```text
PR = 1[
    pre-prune candidate에 viable path 존재
    AND
    post-prune selected set에는 viable path 없음
]
```

---

## Claim 2 — High branching에서 fixed-width pruning이 특히 brittle하다

MAGIC external gold에서:

```text
Top-3 survival
94.76% overall
→ 37.50% at paths>=5
```

```text
Top-5 survival
98.10% overall
→ 75.00% at paths>=5
```

으로 하락했다.

이것이 현재 가장 강한 regime-dependent empirical claim이다.

---

## Claim 3 — Broad preservation은 survival을 올리지만 noise와 cost를 증가시킨다

MAGIC에서 Rashomon .10:

```text
paths>=5 survival = 96.88%
precision = 11.52%
width = 8.41
```

즉 survival만으로 method를 평가하면 안 된다.

---

## Claim 4 — Boundary-local delayed pruning은 유망하다

MAGIC:

```text
Top-3 94.76% / width 1.60
BADP 97.86% / width 1.77
```

Iterative WN18RR n=20:

```text
Top-5
55% success / 45% regret

BADP Top-5 δ=.010
60% / 40%

BADP Top-5 δ=.050
65% / 35%
```

으로 positive signal이 반복됐다.

단 final method claim은 더 큰 held-out test가 필요하다.

---

# 19. 현재 논문의 최종 연구 질문

현재 연구가 답하려는 질문은 더 이상:

> 상반된 주장 중 무엇이 참인가?

가 아니다.

현재 질문은:

> **Multi-hop reasoning에서 fixed-width pruning은 언제 유효한 competing evidence를 너무 일찍 제거하며, Top-K decision boundary 근처의 near-tie candidate만 선택적으로 보존하면 pruning regret을 줄이면서 search cost와 retained-set noise를 통제할 수 있는가?**

이를 간단하게:

```text
When is it unsafe to prune?
```

라고 표현한다.

---

# 20. 현재 제안 방법의 핵심 수식

Candidate expansion:

```text
C_(k+1) = Expand(P_k, G)
```

Scoring:

```text
s_theta(p,q)
```

Fixed Top-K:

```text
P_(k+1)^TopK = TopK(C_(k+1), s_theta, K)
```

Global Rashomon ablation:

```text
R_eps = {p : s(p) >= s* - eps}
```

Relative-loss ablation:

```text
L(p)=1-s(p)
R_eps^loss={p : L(p) <= (1+eps)L*}
```

Boundary-Aware Delayed Pruning:

```text
B_(K,delta)
=
{p : s(p) >= s_(K)-delta}
```

Pruning boundary margin:

```text
Delta_K = s_(K) - s_(K+1)
```

핵심 intuition:

```text
Delta_K 큼
→ K와 K+1이 명확히 구분
→ prune

Delta_K 작음
→ scorer가 cutoff를 명확히 구분하지 못함
→ delayed pruning
```

---

# 21. 현재 평가 원칙

최종 논문에서는 한 숫자만 보고 method를 평가하지 않는다.

## Preservation

- Search Success
- Conflict Path Survival
- Viable Prefix Survival
- Pruning Regret

## Retained-set Validity

- Viability Precision
- Viability Recall
- Viability F1
- MAGIC External-Gold Precision/Recall/F1
- Invalid Retention Rate

## Cost

- Avg Active Width
- Expanded Candidates
- Unique Scorer Calls
- LLM Calls / Tokens
- Latency

## Regime

- Hop depth
- Candidate branching
- Boundary margin `Delta_K`
- Score distribution / entropy

## 최종 분석

```text
Success vs Cost Pareto
Pruning Regret vs Width
Viability F1 vs Width
```

---

# 22. Peer group과 현재 positioning

관련 peer group은 별도 문서:

```text
PEER_GROUP.md
```

으로 관리한다.

핵심 peer:

- Think-on-Graph (ToG)
- Think-on-Graph 2.0
- Paths-over-Graph (PoG)
- FastToG
- Query-Driven Adaptive Graph Retrieval
- Flow-RAG

현재 novelty는:

```text
X first adaptive pruning
X first dynamic beam
X first multiple path KG reasoning

O Top-K cutoff 자체를 uncertainty boundary로 해석
O pruning regret를 irreversible path-loss로 직접 측정
O global widening이 아닌 boundary-local delayed commitment
O survival + retained validity + cost를 함께 평가
O budget-matched / Pareto protocol
```

---

# 23. 연구 진화 요약표

| Stage | 처음 주장/질문 | 방법 | 실제 결과 | 결정 |
|---|---|---|---|---|
| Controlled Tableau | perspective contradiction을 논리적으로 구분 가능한가 | Perspective/Rashomon Tableau | 100% controlled accuracy | reasoner correctness 확인 |
| Explanation enumeration | 복수 explanation을 보존할 가치가 있는가 | Rashomon enumeration | coverage 50%→100% | alternative preservation 가치 확인 |
| DAFNA | early commit보다 worlds가 truth discovery에 좋은가 | Possible worlds | 61%→62% exact, gold world coverage 93% | world generation보다 ranking 병목 |
| MAGIC Tableau | graph+ontology+Tableau로 multi-hop conflict 해결? | Bidirectional paths + Tableau | path 68.03%, detection 5.44% | semantic conflict와 hard logic 분리 |
| MAGIC Worlds | possible worlds가 conflict evidence를 살리는가 | B1~B4 worlds | B3 query recall 39.39%, B4 16.86% | scorer 병목 확인 |
| DeBERTa Worlds | semantic scorer가 개선하는가 | DeBERTa NLI | row +18.71pp, query +14.68pp | scorer validity 확보 |
| WN18RR Frozen | fixed Top-K가 gold를 너무 버리는가 | Top-K vs epsilon | Top5 40% vs eps.10 58% | pruning 연구 전환 |
| Iterative additive | frozen result가 실제 search에도 유지되는가 | best-minus-epsilon | 60% vs 40% 실패 | additive rule 폐기 |
| Relative loss | scale-aware criterion이면 회복되는가 | relative loss | 70% success, width 5.97 | calibration 중요 |
| MAGIC Preservation | conflict path를 pruning이 잃는가 | external gold preservation | Top5 98.1% overall, 75% at paths>=5 | high branching risk 확인 |
| MAGIC Validity | 많이 남긴 path가 유효한가 | precision/recall/F1 | survival↑ precision↓ | 3-way tradeoff 정의 |
| BADP Frozen | cutoff near-tie만 살리면? | Top-K boundary + delta | 94.76→97.86%, width 1.60→1.77 | BADP 후보 생성 |
| BADP Iterative n=20 | 실제 search에서도 유효한가 | budgeted BADP | Top5 55%, BADP .01 60%, BADP .05 65% | positive signal, larger test 필요 |

---

# 24. 현재 남은 실험

## 필수

1. WN18RR larger held-out test
2. dev/test 분리 후 `delta` 고정
3. Boundary margin `Delta_K`와 Pruning Regret 관계 검증
4. high-branching sample 확대
5. 동일 budget / Pareto analysis
6. structural scorer 또는 다른 scorer로 scorer-independence 확인

## Peer comparison

직접 ToG 계열과 비교하려면:

```text
WebQSP
또는
CWQ
```

같은 shared KGQA benchmark가 필요하다.

그때 반드시:

```text
same scorer
same graph
same hop budget
same candidate generator
only pruning policy changes
```

조건의 in-framework ablation과,

```text
ToG / peer published or reproduced system
```

의 system-level comparison을 분리해야 한다.

---

# 25. 현재 연구를 한 문장으로 정리

> **초기에는 Rashomon Worlds와 Tableau를 이용해 상반된 multi-hop 주장을 직접 해결하려 했지만, 실제 실험을 통해 최종 resolution 이전에 search/pruning 단계에서 유효한 competing evidence가 먼저 소실되는 문제가 더 근본적임을 확인했다. 현재 연구는 fixed Top-K의 pruning regret를 정량화하고, Top-K cutoff 근처의 near-tie path만 선택적으로 보존하는 Boundary-Aware Delayed Pruning을 통해 evidence preservation, retained-set validity, search cost의 trade-off를 개선할 수 있는지 검증하는 방향으로 발전했다.**

---

# 26. 주요 실행 기록

| Experiment | Run | Artifact |
|---|---:|---:|
| MAGIC Ontology Bidirectional Tableau | 32720349460 | 9517514860 |
| MAGIC Rashomon Possible Worlds | 32725453943 | 9519356207 |
| DAFNA Possible Worlds | 32726434311 | 9519739380 |
| MAGIC DeBERTa Worlds | 32730398659 | 9521415589 |
| WN18RR relation pruning source | 32799621678 | 9546119681 |
| WN18RR iterative incremental 10 | 32812403726 | 9550470150 |
| WN18RR relative-loss iterative 10 | 32813194834 | 9550550657 |
| MAGIC preservation + validity | 32817516186 | 9551919328 |
| **WN18RR BADP budgeted iterative 20** | **32819877566** | **9553138233** |

---

# 27. 관련 핵심 파일

```text
README.md
RESEARCH_PAPER.md
PEER_GROUP.md
studycase.md

results/ablation_metrics.json
results/preliminary_controlled_metrics.json
results/dafna_official_comparison.json
results/dafna_possible_worlds_summary.json
results/magic_bidirectional_tableau_metrics.json
results/magic_possible_worlds_summary.json
results/magic_deberta_worlds_summary.json
results/wn18rr_pruning_policy_ablation_50.json
results/magic_conflict_preservation_summary.json

scripts/evaluate_iterative_pruning_search_incremental.py
scripts/evaluate_iterative_pruning_relative_loss.py
scripts/evaluate_iterative_pruning_budgeted.py
scripts/evaluate_magic_conflict_preservation.py
```
