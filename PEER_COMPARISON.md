# Final Peer Comparison — BADP vs Multi-hop KG Reasoning / Adaptive Pruning Peers

## 1. 목적

이 문서는 현재 연구의 **최종 peer comparison protocol**을 정의한다.

현재 WN18RR/MAGIC 실험은 pruning mechanism과 evidence preservation을 직접 분석하기 위한 controlled benchmark이며, ToG/PoG/FastToG/ProgRAG/Flow-RAG 등이 주로 사용하는 WebQSP/CWQ의 end-to-end KGQA accuracy와 동일한 숫자가 아니다.

따라서 최종 비교는 두 층으로 나눈다.

```text
Layer A — Mechanism-level comparison
Pruning Regret / Viable Path Survival / Retained Validity / Cost

Layer B — Shared KGQA benchmark comparison
WebQSP / CWQ Answer EM/F1/Hit@1 + Evidence + Cost
```

핵심 원칙:

> **서로 다른 dataset / model / metric의 숫자를 단순 leaderboard처럼 섞지 않는다.**

---

# 2. Direct benchmark peer group

## 2.1 Published end-task references

아래 값은 원 논문/공식 발표 자료에서 확인한 **context reference**다. 우리 시스템이 아직 동일 WebQSP/CWQ protocol로 실행되지 않았으므로 현재 단계에서 head-to-head superiority를 주장하지 않는다.

| Method | Venue | Backbone / setting | Reported metric | WebQSP | CWQ | Pruning/Search mechanism |
|---|---|---|---|---:|---:|---|
| Think-on-Graph | ICLR 2024 | ChatGPT / Freebase | paper KGQA answer score | 76.2 | 58.9 | fixed Top-N iterative relation/entity beam |
| Think-on-Graph | ICLR 2024 | GPT-4 / Freebase | paper KGQA answer score | 82.6 | 69.5 | fixed Top-N iterative beam |
| Think-on-Graph 2.0 | ICLR 2025 | GPT-3.5-class hybrid | EM | 81.1 | — | graph + document context iterative retrieval |
| Paths-over-Graph (PoG-path) | WWW 2025 | GPT-3.5-Turbo | Accuracy | **93.9** | **74.7** | fuzzy → branch-reduced → precise path pruning |
| Paths-over-Graph (PoG-path) | WWW 2025 | GPT-4 | Accuracy | **96.7** | **81.4** | three-stage path pruning |
| Fast Think-on-Graph | AAAI 2025 | GPT-4o-mini / Wikidata | Accuracy | 65.8 | 45.0 | community-level coarse/fine pruning |
| Plan-on-Graph | 2025 | adaptive breadth / Freebase | Hits@1 / exact-style | 82.0 | 63.2 | planning + adaptive exploration breadth |
| ProgRAG* | AAAI 2026 | GPT-4o-mini / Freebase | Hit@1 | 90.4 | 73.3 | progressive relation/triple pruning |
| Flow-RAG | KBS 2026 | trained gated-flow retriever | paper KGQA/retrieval metrics | TBD | TBD | distribution-aware adaptive decision boundary |
| **BADP (ours)** | — | shared benchmark pending | **must report EM/F1/Hit@1 together** | pending | pending | Top-K core + boundary-near delayed pruning |

### 비교 주의

`Accuracy`, `EM`, `Hit@1`은 논문마다 answer normalization과 평가 구현이 다를 수 있다.

따라서 위 표는:

```text
Published contextual reference
```

이고 최종 direct comparison은 동일 evaluator를 사용한 reproduced results로 별도 작성한다.

Source provenance는:

```text
results/peer_published_reference.json
```

에 고정한다.

---

# 3. 왜 이 peer group인가

## 3.1 ToG — fixed-width anchor

ToG의 핵심은 반복적으로:

```text
Relation Search
→ Relation Prune
→ Entity Search
→ Entity Prune
```

를 수행하면서 Top-N 후보를 유지하는 것이다.

우리 연구의 출발점은 ToG가 multi-path를 안 쓴다는 것이 아니다.

차이는:

```text
ToG-style:
rank 기준 고정 N

BADP:
Top-K는 유지하되 K/K+1 score boundary가 불명확하면 pruning을 잠시 지연
```

이다.

따라서 ToG-style Top-3/Top-5는 **가장 중요한 internal baseline**이다.

---

## 3.2 Paths-over-Graph — path pruning peer

Paths-over-Graph는 graph, LLM, PLM을 사용해 multi-hop paths를 단계적으로 줄인다.

중요한 이유는:

- path-level pruning을 직접 수행
- WebQSP/CWQ 성능이 강함
- LLM call efficiency도 분석

한다는 점이다.

PoG precise path-selection efficiency reference:

```text
CWQ     ≈ 9.1 LLM calls
WebQSP  ≈ 7.5 LLM calls
```

따라서 BADP의 최종 실험도 단순 width뿐 아니라:

```text
LLM / scorer calls
```

을 반드시 보고해야 한다.

---

## 3.3 Plan-on-Graph — adaptive breadth peer

Plan-on-Graph의 ablation은 adaptive breadth 자체가 end-task 성능에 기여한다는 prior evidence다.

Reported ablation:

| | WebQSP | CWQ |
|---|---:|---:|
| Full adaptive breadth | 82.0 | 63.2 |
| w/o adaptive breadth | 80.2 | 61.3 |
| Gain | **+1.8pp** | **+1.9pp** |

따라서:

> dynamic/adaptive width 자체가 novelty

라고 주장하면 안 된다.

BADP의 차별점은 **왜 width를 늘리는가**에 있다.

```text
query complexity 때문이 아니라
Top-K irreversible boundary uncertainty 때문
```

이다.

---

## 3.4 Flow-RAG — 가장 중요한 최근 conceptual peer

Flow-RAG는 score distribution을 이용해 context-adaptive pruning boundary를 결정한다.

따라서:

```text
score-distribution-aware adaptive pruning
```

역시 이미 prior work다.

우리의 차별화 후보는:

1. Top-K cutoff 자체를 분석 대상으로 둠
2. viable prefix를 잃는 순간을 Pruning Regret으로 직접 정의
3. boundary-local near-tie만 보존
4. retained validity를 별도 측정
5. budget-matched Pareto comparison

이다.

Flow-RAG의 정확한 WebQSP/CWQ table 값은 현재 접근 가능한 primary text에서 검증하지 못했으므로 **TBD로 남겼다.** Secondary source 숫자를 임의로 넣지 않는다.

---

# 4. 최종 비교 지표

BADP 논문의 peer comparison은 다음 4개 영역을 동시에 보고해야 한다.

## A. End-task correctness

Shared WebQSP/CWQ에서:

```text
Answer-set Exact Match
Macro Answer F1
Micro Answer F1
Hit@1
```

가능하면 기존 peer metric과 별개로 **네 지표를 모두 계산**한다.

왜냐하면 published paper가 사용하는 Accuracy/EM/Hit@1 정의 차이를 최소화하기 위해서다.

---

## B. Evidence / Search Quality

```text
Gold Evidence Recall
Gold Evidence Precision
Gold Evidence F1
Gold / Viable Path Survival @ depth
Search Success
```

Gold path가 없는 dataset에서는 supporting entities/facts coverage로 대체한다.

---

## C. Pruning-specific metrics — 핵심 차별화

### Pruning Regret

```text
PR_(i,k)
=
1[
 pre-prune candidate에 viable evidence 존재
 AND
 post-prune selected set에 viable evidence 없음
]
```

Query-level:

```text
QPR_i = max_k PR_(i,k)
```

Dataset:

```text
QPR = mean_i QPR_i
```

이 지표는 기존 peer leaderboard가 직접 측정하지 않는 **우리 논문의 핵심 diagnostic**이다.

### Boundary margin

```text
Delta_K = s_(K) - s_(K+1)
```

최종 분석에서는 반드시:

```text
P(Pruning Regret | Delta_K bin)
```

을 보고한다.

예:

| Boundary margin | Top-K Regret | BADP Regret |
|---|---:|---:|
| 0–.005 | | |
| .005–.01 | | |
| .01–.05 | | |
| >.05 | | |

이 표가 BADP의 가장 직접적인 hypothesis test다.

---

## D. Efficiency / Cost

최소한:

```text
Avg Active Width
Expanded Nodes / Paths
Unique Scorer Calls
LLM Calls
Input / Retrieved Context Tokens
Retrieval Latency
End-to-End Latency
```

를 기록한다.

최종 peer table에서 성능만 비교하고 토큰/호출량을 누락하면 안 된다.

---

# 5. 최종 Main Table 형식

최종 논문 Table은 아래 형태를 목표로 한다.

| Method | WebQSP EM | WebQSP F1 | WebQSP Hit@1 | CWQ EM | CWQ F1 | CWQ Hit@1 | Evidence Recall | QPR ↓ | Avg Width ↓ | Expanded ↓ | LLM Calls ↓ | Tokens ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ToG reproduced | | | | | | | | | | | | |
| Global band | | | | | | | | | | | | |
| Relative-loss | | | | | | | | | | | | |
| **BADP** | | | | | | | | | | | | |

Published-only external references는 별도 표에 남긴다.

---

# 6. Budget-matched 비교

동일 K를 강제로 cap하면 BADP가 Top-K와 동일해질 수 있으므로 다음 방식으로 비교한다.

Top-K anchor:

```text
A in {Top-3, Top-5}
```

adaptive policy family `F_lambda`에 대해 development split에서:

```text
lambda*_F(A)
=
argmin_lambda
| Cost(F_lambda) - Cost(A) |
```

Cost는 우선순위대로:

```text
1. Avg Active Width
2. Expanded Paths
3. Scorer/LLM Calls
4. Context Tokens
```

을 사용한다.

그 뒤 test split에서 parameter는 변경하지 않는다.

최종 보고:

```text
Delta Answer F1
Delta Hit@1
Delta Pruning Regret
Delta Evidence Recall
Delta Width
Delta Expansions
Delta LLM Calls
Delta Tokens
```

---

# 7. 현재 실제 우리 결과 — direct peer 숫자로 쓰면 안 됨

현재 WN18RR iterative n=20은 **mechanism-level evidence**다.

| Policy | Search success | Regret ↓ | Viability F1 | Width | Expanded |
|---|---:|---:|---:|---:|---:|
| Top-3 | 50% | 50% | **33.58%** | 2.71 | 24.80 |
| Top-5 | 55% | 45% | 29.97% | 4.06 | 32.35 |
| BADP Top-3 δ=.005 | 55% | 45% | 32.05% | 3.34 | 27.15 |
| BADP Top-5 δ=.010 | 60% | 40% | 28.10% | 5.00 | 35.10 |
| BADP Top-5 δ=.050 | **65%** | **35%** | 26.20% | 6.16 | 38.25 |

Run:

```text
32819877566
Artifact 9553138233
```

해석:

- BADP가 더 많은 search budget을 사용하면 success/regret를 개선하는 positive signal
- 하지만 viability precision/F1은 하락 가능
- 따라서 현재도 **success–validity–cost Pareto**로 평가해야 함
- `65%`를 ToG의 WebQSP `76.2`와 직접 비교해서는 안 됨

---

# 8. 최종 연구 주장과 peer comparison의 연결

최종 논문이 증명해야 할 것은:

> BADP가 모든 KGQA architecture보다 최고 정확도다.

가 아니다.

증명 목표는 다음이다.

### Claim A

```text
Fixed Top-K has non-zero irreversible Pruning Regret.
```

### Claim B

```text
Pruning Regret increases in high-branching / small-boundary-margin regimes.
```

### Claim C

```text
At matched search budget,
BADP reduces Pruning Regret and/or increases evidence/answer survival
more efficiently than broad global retention.
```

### Claim D

```text
The gain remains observable on a shared KGQA benchmark
without unacceptable token/call/latency inflation.
```

A–C가 pruning-method 논문의 핵심이고 D가 peer-level external validity다.

---

# 9. Final experiment checklist

## 반드시 수행

- [ ] WebQSP dev/test loader
- [ ] CWQ dev/test loader
- [ ] 동일 Freebase KG/subgraph 조건
- [ ] Top-3 baseline
- [ ] Top-5 baseline
- [ ] Global epsilon baseline
- [ ] Relative-loss baseline
- [ ] BADP
- [ ] dev에서 epsilon/delta 선택
- [ ] test에서 hyperparameter freeze
- [ ] EM/F1/Hit@1 동시 산출
- [ ] gold evidence/path recall 가능 시 산출
- [ ] pruning regret 기록
- [ ] boundary margin 기록
- [ ] avg width / expanded candidates
- [ ] LLM/scorer calls
- [ ] context tokens
- [ ] latency
- [ ] hop별 분석
- [ ] branching별 분석
- [ ] boundary-margin별 분석
- [ ] Pareto frontier

---

# 10. 권장 최종 Figure

### Figure 1 — Main efficiency frontier

```text
X = Expanded paths / context tokens
Y = Answer F1 or Hit@1
```

### Figure 2 — Core mechanism validation

```text
X = Boundary margin Delta_K
Y = Pruning Regret
```

Top-K와 BADP를 동시에 그린다.

### Figure 3 — Retained validity trade-off

```text
X = Avg active width
Y = Viability / Evidence F1
```

### Figure 4 — Regime analysis

```text
branching factor
×
Top-K / BADP success-regret difference
```

---

# 11. 결론

peer comparison까지 포함했을 때 현재 연구의 가장 안전한 positioning은 다음이다.

> **Existing graph reasoners already use fixed beams, multi-stage pruning, adaptive breadth, and distribution-aware adaptive pruning. BADP therefore does not claim adaptivity itself as novel. Instead, it isolates the Top-K cutoff as an irreversible uncertainty boundary, measures the resulting loss with Pruning Regret, and tests whether boundary-local delayed commitment improves evidence preservation under matched validity and search-cost constraints.**

이 positioning으로 WebQSP/CWQ에서 같은 evaluator를 적용한 결과가 나오면 peer comparison을 완성할 수 있다.
