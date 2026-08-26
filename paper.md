# 불완전한 운영 관계 그래프에서의 증거 기반 인과관계 복원과 Root Cause Path 추론

**Evidence-Grounded Causal Relation Recovery and Root Cause Path Reasoning over Incomplete Operational Graphs**

> 작성 기준 시점: 2026-08-26  
> 현재 주 실험: OpenRCA 2.0 / ops-lite 500-case standard protocol  
> 현재 상태: 500/500 데이터 정규화 검증 완료, A4 Full Model은 150/500 case 완료 시점의 중간 결과를 포함함  
> 이전 MAGIC·DAFNA-EA·WN18RR·BADP 실험은 연구 문제의 발전 과정과 구성요소 검증을 위한 선행 실험으로만 사용함

---

## 초록

운영 시스템의 Root Cause Analysis(RCA)는 일반적으로 서비스 의존 관계, 배포 구조, 호출 관계, 데이터베이스 연결 관계와 같은 시스템 지식이 충분히 구축되어 있다는 가정하에 수행된다. 그러나 실제 환경에서는 CMDB, topology, ontology 또는 knowledge graph가 불완전하며, 장애 발생 시점에 필요한 인과관계가 명시적으로 존재하지 않는 경우가 많다. 이러한 환경에서 단순 그래프 탐색은 관찰된 연결성만 제공할 뿐 해당 연결이 실제 장애 전파에 참여했는지를 판단하지 못하며, 반대로 LLM 기반 RCA는 적절한 root service를 찾더라도 원인에서 증상까지의 검증 가능한 causal path를 제시하지 못하는 문제가 있다.

본 연구는 이 문제를 **불완전한 운영 관계 그래프에서 incident-specific causal relation을 복원하고, 복원된 관계를 이용하여 root cause에서 사용자 관찰 증상까지의 propagation path를 추론하는 문제**로 정식화한다. 제안 방법은 (1) 관찰된 dependency endpoint를 대상으로 하는 Abductive Hypothesis Generation, (2) 정상·비정상 telemetry와 인과/비인과 명제를 비교하는 DeBERTa 기반 contrastive semantic scoring, (3) temporal precedence, anomaly co-occurrence, semantic evidence, path coherence를 결합하는 Probabilistic Soft Logic(PSL) inference로 구성된다. 연결성 자체는 causal evidence로 사용하지 않고 후보 생성의 자격 조건으로만 사용하여 structural bias를 줄인다.

20-case controlled relation-masking development benchmark에서 Graph-only는 높은 Relation Accuracy(73.83%)에도 불구하고 causal positive class를 전혀 복원하지 못해 Relation F1이 0%였으며, Abduction은 Relation F1 29.67%, Abduction+DeBERTa는 37.17%를 기록했다. Full model은 Relation F1 37.17%로 분류 자체에서는 추가 이득이 없었지만 Path Reachability를 35%에서 40%로, Root@3를 40%에서 45%로 개선하였다. 이는 local relation classification과 global process reconstruction이 서로 다른 평가 대상임을 보여준다.

OpenRCA 2.0 standard 500-case 실험에서는 데이터 500/500 정규화 및 gold leakage 차단 검증이 완료되었다. 현재 완료된 150개 case에서 Full model은 Any Service Hit 60.00%, All Service Hit 39.33%, Process Path Reachability 57.33%, Node-F1 52.94%, Edge-F1 38.11%를 기록했다. 특히 Edge Recall 80.26%에 비해 Edge Precision이 28.87%로 낮아, 현재 모델의 주요 병목이 **causal edge를 찾지 못하는 것보다 불필요한 edge를 과도하게 유지하는 데 있음**을 확인하였다. 따라서 다음 단계의 핵심 개선 대상은 hypothesis generation 확대가 아니라 causal edge calibration 및 pruning이다.

**주요어:** Root Cause Analysis, OpenRCA 2.0, Causal Relation Recovery, Abductive Reasoning, DeBERTa, Probabilistic Soft Logic, Knowledge Graph, Observability

---

# 1. 서론

## 1.1 연구 배경

현대의 마이크로서비스 및 분산 시스템에서는 장애 원인이 사용자에게 관찰되는 증상과 동일한 서비스에서 발생하지 않을 수 있다. 데이터베이스 지연, downstream service failure, resource saturation, network latency와 같은 원인은 여러 서비스 및 구성요소를 거쳐 전파된 뒤 최종적으로 API latency, error rate 증가 또는 서비스 가용성 저하의 형태로 나타난다.

따라서 RCA의 핵심은 단순히 “어떤 서비스가 이상했는가”를 찾는 것이 아니라 다음의 인과적 연결을 복원하는 것이다.

$$
r \rightarrow v_1 \rightarrow v_2 \rightarrow \cdots \rightarrow a
$$

여기서 $r$은 root-cause service, $a$는 alarm 또는 symptom service, 중간 노드 $v_i$는 장애가 전파된 서비스 또는 구성요소를 의미한다.

OpenRCA 2.0은 이러한 문제를 명시적으로 평가하기 위해 root-cause label뿐 아니라 step-wise causal propagation annotation을 제공한다. OpenRCA 2.0 연구에서는 frontier LLM들이 적어도 하나의 올바른 root-cause service를 찾는 비율은 평균 76.0%였으나, 이를 검증된 causal propagation path에 grounding하는 비율은 61.5%에 그쳤다고 보고하였다. 이는 root-cause identification과 causal process reconstruction이 동일한 문제가 아님을 보여준다 [1].

## 1.2 기존 접근의 한계

본 연구가 다루는 현실적 제약은 **운영 지식 그래프가 완전하지 않다**는 점이다. 실제 시스템에서 다음 세 개념은 동일하지 않다.

$$
Graph\ Reachability \neq Semantic\ Relation \neq Causal\ Relation
$$

A 서비스가 B 서비스를 호출한다는 사실은 두 서비스가 구조적으로 연결되어 있음을 의미하지만, 특정 incident에서 A의 이상이 B로 전파되었다는 것을 자동으로 의미하지 않는다. 반대로 장애 전파가 실제로 발생했더라도 CMDB 또는 ontology에 해당 causal relation이 사전에 정의되어 있지 않을 수 있다.

초기 연구에서는 Rashomon Worlds와 Tableau를 이용하여 여러 가능한 설명을 보존한 뒤 논리적으로 모순된 설명을 제거하려 하였다. 그러나 실험 과정에서 다음 한계가 확인되었다.

1. Tableau는 ontology에 정의되지 않은 관계 의미를 스스로 생성하지 못한다.
2. 가능한 world를 많이 보존해도 semantic scorer가 약하면 올바른 설명을 선택하기 어렵다.
3. Boolean consistency만으로는 noisy telemetry와 confidence-valued evidence를 충분히 표현하기 어렵다.
4. RCA에서는 “모순인가 아닌가”보다 “여러 noisy evidence를 종합할 때 어느 causal edge가 더 가능성이 높은가”가 더 직접적인 문제다.

이에 따라 현재 방법은 Rashomon을 별도 알고리즘으로 사용하지 않고, 여러 후보를 조기에 하나로 확정하지 않는 **candidate-preservation principle**로만 유지한다. 누락 관계 생성은 abduction, 의미 적합도는 DeBERTa NLI, 전역 soft consistency는 PSL로 역할을 분리한다.

## 1.3 연구 질문

본 연구는 다음 세 질문을 검증한다.

**RQ1.** 불완전한 운영 관계 그래프에서 incident telemetry를 이용한 abductive relation hypothesis generation이 causal relation 복원에 기여하는가?

**RQ2.** 정상/비정상 telemetry와 causal/non-causal 명제를 비교하는 semantic scorer가 구조·시간 정보만 사용하는 방법보다 causal relation discrimination을 개선하는가?

**RQ3.** local relation score만으로 결정하는 것보다 PSL 기반 global path coherence를 결합하는 것이 root-cause propagation path 복원에 기여하는가?

## 1.4 연구 기여

본 연구의 현재 기여는 다음과 같이 정리된다.

- 완전한 ontology를 전제로 하지 않고, **관찰된 dependency 위에서 incident-specific causal relation을 복원하는 RCA 문제**를 정의한다.
- 구조적 연결성을 causal evidence로 사용하지 않고 **candidate eligibility**로만 사용하여 topology 자체가 정답을 암시하는 문제를 줄인다.
- Abduction, semantic NLI, soft logical inference의 역할을 분리한 모듈형 RCA 파이프라인을 제안한다.
- Root-cause hit뿐 아니라 Relation-F1, Node-F1, Edge-F1, Process Path Reachability를 함께 측정하여 “원인을 맞힘”과 “인과과정을 복원함”을 분리하여 평가한다.
- controlled relation-masking 실험과 OpenRCA 2.0 standard 실험을 분리하여, **누락 관계 내성**과 **표준 RCA 성능**을 서로 다른 조건에서 검증한다.

---

# 2. 관련 연구

## 2.1 OpenRCA 2.0과 causal process supervision

OpenRCA 2.0은 500개의 cross-system RCA instance에 대해 PAVE 기반 step-wise causal annotation을 제공한다. PAVE는 fault injection이라는 알려진 intervention에서 출발하여 cause-to-effect 방향으로 propagation을 검증한다. 따라서 단순 root label보다 causal process 자체를 평가할 수 있다는 점이 본 연구의 핵심 요구와 일치한다 [1].

본 연구는 OpenRCA 2.0의 gold causal graph를 추론 입력으로 사용하지 않는다. Standard track에서 model-visible structure는 telemetry의 trace dependency로부터만 구성하며, gold root 및 causal graph는 evaluation 단계에서만 사용한다.

## 2.2 Abductive Reasoning

Abduction은 관찰된 현상을 가장 잘 설명하는 가설을 찾는 추론 방식이다. 고전적으로 Hobbs 등은 weighted abduction을 “관찰을 설명하기 위한 최소 비용의 가설” 문제로 설명하였다 [2]. 최근에는 knowledge graph 상의 관찰을 설명하는 complex logical hypothesis generation 연구도 제안되었다 [3].

본 연구의 abduction은 생성형 LLM을 이용해 임의의 relation을 발명하는 방식이 아니다. 운영 trace가 관찰한 endpoint pair를 후보 영역으로 제한하고, 해당 dependency가 이번 incident의 causal propagation에 참여했는지를 가설로 둔다. 이는 후보 폭발과 hallucinated topology를 피하기 위한 설계이다.

## 2.3 DeBERTa 기반 Semantic Evidence Scoring

DeBERTa는 disentangled attention과 enhanced mask decoder를 이용하는 pretrained language model로 다양한 NLU 및 NLI task에서 강한 성능을 보였다 [4]. 본 연구에서는 DeBERTa를 독립적인 RCA 모델이 아니라 **telemetry description이 causal claim과 non-causal claim 중 어느 쪽을 더 지지하는지 판단하는 semantic evidence scorer**로 사용한다.

## 2.4 Probabilistic Soft Logic

PSL은 first-order logic 형태의 규칙에 soft truth value를 부여하고, Hinge-Loss Markov Random Field를 통해 MAP inference를 수행하는 probabilistic programming framework이다 [5]. RCA telemetry는 완전한 Boolean fact보다 confidence-valued evidence에 가깝기 때문에, hard Tableau보다 PSL이 현재 문제에 더 적합하다.

---

# 3. 문제 정의

## 3.1 입력

각 incident case를 다음과 같이 정의한다.

$$
X = (V, E_{obs}, Z, S)
$$

- $V$: 관찰된 service node 집합
- $E_{obs}$: trace 등 telemetry에서 관찰된 dependency endpoint pair
- $Z$: metric, log, trace로부터 생성된 incident evidence
- $S$: 관찰된 symptom node 집합

중요한 점은 $E_{obs}$가 causal edge 집합이 아니라는 것이다. 즉

$$
(u,v) \in E_{obs}
$$

는 단지 “$u$와 $v$ 사이의 dependency가 관찰되었다”는 의미이며,

$$
CAUSES(u,v)=1
$$

을 의미하지 않는다.

## 3.2 출력

모델은 다음 두 출력을 생성한다.

$$
\hat{E}_{causal}
$$

$$
\hat{R} = [\hat{r}_1, \hat{r}_2, \ldots, \hat{r}_k]
$$

여기서 $\hat{E}_{causal}$은 incident-specific causal propagation edge 집합이고, $\hat{R}$은 root-cause service ranking이다.

최종적으로 올바른 root service가 예측되고 해당 root에서 gold alarm service까지 directed path가 존재해야 causal process reconstruction에 성공한 것으로 본다.

## 3.3 연구 목표

본 연구의 최적화 목표는 단순 root-cause classification이 아니라 다음 두 조건을 동시에 만족하는 것이다.

$$
\hat{R} \approx R^*
$$

$$
\hat{E}_{causal} \approx E^*_{causal}
$$

따라서 root hit가 높더라도 edge/path가 낮으면 완전한 RCA로 간주하지 않는다.

---

# 4. 제안 방법

## 4.1 전체 구조

```text
Normal / Abnormal Telemetry
          |
          v
Observed Dependency Extraction
          |
          v
Abductive Causal Hypotheses
          |
          v
DeBERTa Contrastive NLI
          |
          v
PSL Soft Global Inference
          |
     +----+----+
     |         |
     v         v
Causal Edges  Root Ranking
     |         |
     +----+----+
          v
Root-to-Symptom Propagation Path
```

### 4.1.1 핵심 설계 원칙

구조적 연결성은 후보 생성에만 사용한다.

$$
ObservedDependency(u,v) \Rightarrow EligibleHypothesis(u,v)
$$

그러나 다음 규칙은 사용하지 않는다.

$$
ObservedDependency(u,v) \nRightarrow Causes(u,v)
$$

즉 topology가 있다는 이유만으로 causal score를 올리지 않는다.

---

## 4.2 Abductive Hypothesis Generation

각 관찰 dependency $(u,v)$에 대해 다음 가설을 생성한다.

$$
h_{uv}: Causes(u,v)
$$

후보는 모든 node pair의 Cartesian product가 아니라 $E_{obs}$에 존재하는 endpoint pair로 제한한다.

### 4.2.1 Temporal score

source와 target에서 최초 anomaly 시점을 각각 $t_u$, $t_v$라고 하고

$$
\Delta t = t_v - t_u
$$

로 정의한다. 현재 구현의 temporal score $T(h)$는 다음과 같다.

| 조건 | $T(h)$ |
|---|---:|
| source 또는 target anomaly time 없음 | 0.00 |
| $\Delta t < 0$ | 0.00 |
| $0 \le \Delta t \le 5$ | 1.00 |
| $5 < \Delta t \le 30$ | 0.80 |
| $30 < \Delta t \le 120$ | 0.55 |
| $\Delta t > 120$ | 0.20 |

이 값은 “원인이 결과보다 먼저 나타나는가”를 incident-local causal support로 사용한다. 단, temporal precedence 자체를 causal proof로 해석하지 않는다.

### 4.2.2 Endpoint anomaly score

source와 target에서 관찰된 최대 abnormality를 각각 $a_u$, $a_v$라 하면,

$$
A(h) = \min(a_u, a_v)
$$

로 정의한다. 한쪽 endpoint만 강하게 이상하고 다른 쪽이 정상이라면 causal propagation support를 높게 주지 않기 위한 보수적 결합이다.

### 4.2.3 Abductive score

현재 local abductive prior는 다음과 같다.

$$
S_{abd}(h) = 0.55T(h) + 0.45A(h)
$$

이 식에는 structural score가 포함되지 않는다. 구조는 후보 자격만 결정한다.

---

## 4.3 DeBERTa Contrastive Semantic Scoring

절대 entailment만 사용할 경우 telemetry 문장이 중립적으로 표현되었을 때 모든 score가 0에 가까워지는 문제가 발생하였다. 이를 줄이기 위해 동일한 evidence premise에 대해 서로 경쟁하는 두 claim을 비교한다.

Causal claim:

> incident anomaly at service $u$ causally propagated to service $v$.

Non-causal claim:

> observed dependency $u \rightarrow v$ did not causally propagate the incident anomaly.

각 claim의 entailment probability를 $e_c$, $e_n$이라 한다.

### 4.3.1 Contrastive preference

$$
p = \frac{e_c - e_n}{e_c + e_n}
$$

단, $e_c+e_n$이 0에 가까우면 $p=0$으로 처리한다.

### 4.3.2 Reliability attenuation

두 claim 모두 entailment mass가 매우 낮으면 작은 수치 차이를 과대해석하지 않도록 reliability를 둔다.

$$
r = \min\left(1, \max\left(0, \frac{e_c+e_n}{0.5}\right)\right)
$$

최종 semantic margin은

$$
m = p \cdot r
$$

이다.

Semantic support와 contradiction은 다음과 같이 정의한다.

$$
S_{sem}(h) = 0.5 + 0.5m
$$

$$
C_{sem}(h) = 0.5 - 0.5m
$$

Neutrality는

$$
N_{sem}(h) = 1-r
$$

이다.

PSL을 사용하지 않는 semantic ablation에서는 다음 보정 점수를 사용한다.

$$
S_{local}(h) = clip\left(S_{abd}(h) + 0.25(S_{sem}(h)-C_{sem}(h)), 0, 1\right)
$$

이 구조의 목적은 DeBERTa가 telemetry prior를 완전히 덮어쓰는 것이 아니라 causal-vs-noncausal preference만 제한적으로 보정하도록 하는 것이다.

---

## 4.4 PSL Global Inference

각 candidate edge의 soft truth value를

$$
y_{uv} = Causes(u,v) \in [0,1]
$$

로 둔다. PSL은 weighted logical rule의 violation을 최소화하는 MAP assignment를 계산한다.

개념적으로 다음 목적함수를 최소화한다.

$$
y^* = \arg\min_y \sum_j w_j \phi_j(y,x)^2
$$

여기서 $x$는 관찰 evidence, $w_j$는 규칙 weight, $\phi_j$는 soft rule violation을 의미한다.

현재 Full model의 주요 규칙은 다음과 같다.

| Weight | Soft rule | 역할 |
|---:|---|---|
| 1.2 | `TEMPORAL(A,B) -> CAUSES(A,B)` | 시간 선행성의 positive support |
| 1.1 | `ANOMALYPAIR(A,B) -> CAUSES(A,B)` | 양 endpoint 이상 동반 support |
| 0.8 | `!TEMPORAL(A,B) -> !CAUSES(A,B)` | 시간 조건 부재의 negative evidence |
| 1.2 | `!ANOMALYPAIR(A,B) -> !CAUSES(A,B)` | endpoint anomaly 부재의 negative evidence |
| 1.0 | `SEMANTIC(A,B) -> CAUSES(A,B)` | DeBERTa causal support |
| 1.0 | `CONTRADICTION(A,B) -> !CAUSES(A,B)` | DeBERTa non-causal support |
| 1.6 | `CAUSES(A,B) & REACHES(B) -> REACHES(A)` | downstream symptom 방향 path coherence |
| 0.8 | `TEMPORAL(A,B) & REACHES(B) -> CAUSES(A,B)` | local evidence와 global reachability 결합 |
| 0.5 | `CAUSES(A,B) -> !CAUSES(B,A)` | 역방향 동시 causal edge 억제 |
| 0.25 | `!CAUSES(A,B)` | 약한 sparsity prior |

PSL의 역할은 local edge score를 무조건 높이는 것이 아니다. downstream symptom으로 이어지는 global path context를 이용하되, local temporal/anomaly/semantic support가 약한 edge를 path 존재만으로 causal로 만들지 않도록 설계하였다.

---

## 4.5 Edge Selection

PSL 이후 각 hypothesis의 score를 $S_{psl}(h)$라 하고, 현재 threshold는 0.5이다.

$$
\hat{E}_{causal} = \{h \mid S_{psl}(h) \ge 0.5\}
$$

현재 standard 중간 결과에서 recall은 높고 precision은 낮게 나타나므로 이 고정 threshold 및 PSL calibration이 다음 개선의 핵심 대상이다.

---

## 4.6 Root Cause Ranking

선택된 causal hypotheses의 source node를 root 후보로 사용한다. 각 node $v$에 대해 다음 특성을 계산한다.

- $O(v)$: 최대 outgoing causal hypothesis score
- $I(v)$: 최대 incoming causal hypothesis score
- $A(v)$: node의 최대 abnormality
- $E(v)$: earliest anomaly score, 빠를수록 1에 가까움

Rootness는 다음과 같다.

$$
R(v) = 0.38O(v) + 0.30A(v) + 0.20E(v) + 0.12(1-I(v))
$$

causal edge가 threshold를 넘지 못한 경우에도 standard RCA agent가 빈 답을 반환하지 않도록 evidence-only fallback을 둔다.

$$
R_{fallback}(v) = 0.75A(v) + 0.25E(v)
$$

현재 최대 root prediction 수는 3개이다.

---

# 5. 실험 설계

## 5.1 Dataset

주 데이터셋은 OpenRCA 2.0의 `anon-ops/ops-lite` 500-case release를 사용한다. 각 case에서 normal/abnormal traces, metrics, logs를 읽고 service-level dependency 및 evidence를 정규화한다.

Standard 500-case adapter의 원칙은 다음과 같다.

- dependency candidate는 telemetry trace에서만 추출한다.
- root-cause gold는 manifest의 root service label을 evaluator에서만 사용한다.
- causal edge 및 alarm gold는 `causal_graph.json`을 evaluator에서만 사용한다.
- model inference 직전에 모든 gold field를 제거한다.
- service-level causal path가 하나의 service 내부에서 끝나는 경우 gold edge set이 비어 있을 수 있으며, 이 case도 denominator에서 제거하지 않는다.

## 5.2 두 개의 평가 트랙

### Track A. Standard OpenRCA 2.0

입력 구조를 인위적으로 mask하지 않고 telemetry-derived dependency만 제공한다. 공식 OpenRCA 2.0의 process-level metric과 최대한 동일한 service normalization을 사용하여 직접 비교 가능한 표준 결과를 만드는 것이 목표이다.

### Track B. Controlled Relation-Masking

관찰된 endpoint connectivity는 유지하되 해당 dependency가 `causal_propagates_to`인지 `non_causal_dependency`인지의 relation label 일부를 숨긴다. 이 트랙의 목적은 **불완전한 ontology/관계 그래프에서 relation semantics가 누락되었을 때 이를 telemetry로 복원할 수 있는가**를 직접 측정하는 것이다.

따라서 Track B 수치는 official standard leaderboard와 직접 비교하지 않는다.

## 5.3 Ablation

| Variant | 구성 | 검증 목적 |
|---|---|---|
| A0 | Observed graph only | topology만으로 가능한 수준 측정 |
| A1 | Abduction | temporal + anomaly evidence의 기여 측정 |
| A2 | Abduction + DeBERTa | semantic NLI의 추가 기여 측정 |
| A3 | Abduction + PSL | semantic model 없이 soft global logic의 기여 측정 |
| A4 | Abduction + DeBERTa + PSL | 전체 방법의 local + semantic + global 결합 효과 측정 |

---

# 6. 평가 지표와 검증 목적

본 연구에서는 하나의 지표만 높다고 RCA가 성공했다고 판단하지 않는다. 지표마다 검증하는 실패 유형이 다르기 때문이다.

## 6.1 Precision, Recall, F1

일반적인 binary/set 평가를 다음과 같이 정의한다.

$$
Precision = \frac{TP}{TP+FP}
$$

$$
Recall = \frac{TP}{TP+FN}
$$

$$
F1 = \frac{2 \cdot Precision \cdot Recall}{Precision+Recall}
$$

Precision은 “예측한 것 중 실제로 맞는 비율”, Recall은 “실제 정답 중 얼마나 찾아냈는가”를 의미한다.

본 연구에서 특히 중요한 해석은 다음과 같다.

- **High Recall + Low Precision**: 정답 causal edge는 많이 찾지만 불필요한 edge를 과다 예측함.
- **High Precision + Low Recall**: 보수적으로 맞는 edge만 예측하지만 실제 causal propagation을 많이 놓침.

## 6.2 Relation Accuracy / Relation F1

Controlled masking에서 각 masked observed pair를 causal positive 또는 non-causal negative로 분류한다.

**검증 목적:** 누락된 relation semantics 자체를 복원할 수 있는가?

Accuracy만 사용하지 않는 이유는 non-causal dependency가 많을 때 모든 edge를 negative로 예측해도 높은 accuracy가 나올 수 있기 때문이다. 실제 20-case 실험에서 Graph-only가 정확히 이 현상을 보였다.

## 6.3 Root Service Precision / Recall / F1

예측 root service set과 gold root service set을 비교한다.

**검증 목적:** 모델이 장애의 시작점을 service level에서 얼마나 정확히 특정하는가?

현재 모델은 최대 3개의 root를 반환하므로 올바른 root를 포함하면서 추가 root도 반환하면 recall은 높고 precision/exact는 낮을 수 있다.

## 6.4 Root Exact Set

$$
ExactRoot = 1[\hat{R}=R^*]
$$

예측 root 집합과 gold root 집합이 정확히 동일할 때만 1이다.

**검증 목적:** “정답 중 하나를 포함했다”가 아니라 root set 전체를 정확히 복원했는가?

이 지표는 매우 엄격하다. 예를 들어 gold가 `{A}`인데 모델이 `{A,B,C}`를 반환하면 Any Hit은 성공하지만 Exact Root는 실패한다.

## 6.5 Any Service Hit

$$
AnyHit = 1[\hat{R} \cap R^* \neq \emptyset]
$$

**검증 목적:** top root candidates 중 최소 하나라도 실제 root service를 포함하는가?

실무적으로 “조사 범위를 올바른 서비스까지 좁혔는가”를 보여주지만, extra false-positive root를 허용하므로 단독으로는 충분하지 않다.

## 6.6 All Service Hit

$$
AllHit = 1[R^* \subseteq \hat{R}]
$$

**검증 목적:** 복수 root가 존재하는 incident에서 필요한 모든 root service를 포함했는가?

Any Hit보다 엄격하지만 여전히 extra predicted roots를 허용한다.

## 6.7 Node-F1

Predicted propagation edge의 endpoint와 predicted root를 node set으로 만들고, gold causal edge endpoint와 gold root node set과 비교한다.

**검증 목적:** causal process에 참여하는 **서비스 범위**를 얼마나 잘 복원했는가?

Node-F1이 높고 Edge-F1이 낮다면 “관련 서비스는 찾았지만 서비스 사이의 올바른 인과 연결을 잘못 구성했다”는 의미가 된다.

## 6.8 Edge-F1

service name을 정규화한 directed pair `(source service, target service)`를 비교한다. Standard metric에서는 relation label 자체보다 directed service-pair propagation 구조를 평가한다.

**검증 목적:** 장애가 어떤 서비스에서 어떤 서비스로 전파되었는지 **인과 구조의 연결 관계**를 복원했는가?

본 연구의 핵심 지표 중 하나이다. 불완전한 relation recovery가 실제 causal graph reconstruction으로 이어졌는지를 가장 직접적으로 보여준다.

## 6.9 Process Path Reachability

본 연구의 standard evaluator에서 성공 조건은 두 가지를 동시에 요구한다.

1. predicted roots 중 실제 gold root가 존재한다.
2. 해당 correct root에서 gold alarm service까지 predicted directed edge path가 존재한다.

이를 다음과 같이 표현할 수 있다.

$$
PR = 1[\exists r \in (\hat{R} \cap R^*),\ \exists a \in A^*:\ r \leadsto a]
$$

**검증 목적:** root service를 단순히 맞힌 것이 아니라, root에서 관찰된 symptom까지 설명 가능한 propagation chain을 실제로 구성했는가?

OpenRCA 2.0이 강조하는 “ungrounded diagnosis”를 직접 드러내는 지표이다.

## 6.10 지표 간 해석 관계

| 관찰 패턴 | 의미 |
|---|---|
| Root Hit 높음, Path 낮음 | 원인 서비스는 찾지만 전파 설명이 약함 |
| Node-F1 높음, Edge-F1 낮음 | 관련 서비스는 찾지만 관계 방향/연결이 부정확함 |
| Edge Recall 높음, Precision 낮음 | causal graph를 과도하게 넓게 예측함 |
| Relation F1 상승, Path 변화 없음 | local relation 분류 개선이 global path 개선으로 연결되지 않음 |
| Path 상승, Relation F1 동일 | global inference가 동일한 local decision에서도 process-level 연결을 개선함 |

---

# 7. 실험 결과

## 7.1 선행 실험 1: Ontology/Tableau만으로는 누락 관계를 생성할 수 없음

초기 MAGIC multi-hop 실험에서 양방향 path coverage는 68.03%였지만 ontology/Tableau 기반 conflict detection은 5.44%에 그쳤다.

이 결과의 의미는 Tableau의 절대 성능이 낮다는 것이 아니라, **그래프에서 path를 찾았다는 사실만으로 path의 semantic relation이 ontology에 자동으로 존재하지 않는다**는 점이다.

따라서 다음 관계가 성립하지 않음을 실험적으로 확인하였다.

$$
PathFound \nRightarrow RelationKnown
$$

이 결과가 누락 relation을 먼저 hypothesis로 생성해야 한다는 현재 연구 방향의 출발점이 되었다.

## 7.2 선행 실험 2: 후보 생성과 후보 선택은 다른 문제

DAFNA-EA 100개 gold subset에서 candidate generation은 gold world를 93% 포함했으나 최종 exact selection은 최고 62%였다.

| 방법 | Exact-set Accuracy | Author F1 |
|---|---:|---:|
| Possible-world uniform | 58% | 80.38% |
| Hard commit reliability | 61% | 84.04% |
| Possible-world marginal | **62%** | **84.13%** |
| Atomic resolution | 61% | 82.88% |

핵심은 다음 차이이다.

$$
GoldCandidateCoverage = 93\%
$$

$$
BestExactSelection = 62\%
$$

즉 정답 후보가 존재해도 ranking/inference가 올바른 후보를 선택하지 못할 수 있다. 현재 연구에서 Abduction과 Semantic/PSL을 별도 구성요소로 분리하여 ablation하는 이유이다.

## 7.3 선행 실험 3: DeBERTa semantic scorer의 필요성

MAGIC structured experiment에서 weak lexical scorer를 DeBERTa NLI scorer로 교체했을 때 다음 개선이 관찰되었다.

| Metric | Weak lexical | DeBERTa | Improvement |
|---|---:|---:|---:|
| Row conflict recall | 22.79% | **41.50%** | **+18.71%p** |
| Query conflict recall | 16.86% | **31.53%** | **+14.68%p** |
| Structured exact localization | 7.14% | **15.48%** | **+8.33%p** |

이 결과가 검증한 것은 “DeBERTa가 RCA를 해결한다”가 아니다. 동일 candidate set에서 lexical similarity보다 semantic NLI가 의미적으로 유효한 candidate를 더 잘 구분한다는 점을 확인한 것이다.

이후 provenance metadata가 NLI input에 섞였던 구현 오류를 발견하여 수정 전 자연어 MAGIC 결과는 최종 논문 성능 수치에서 제외하였다. 위 표는 현재 `studycase.md`에 보존된 검증된 structured comparison의 역할로만 사용한다.

---

## 7.4 Controlled Relation-Masking 20-case Development Benchmark

### 7.4.1 실험 조건

- Dataset: `anon-ops/ops-lite`
- Case 수: 20
- Incident-specific relation label mask: 40%
- Seed: 42
- Endpoint connectivity: 유지
- Positive class: `causal_propagates_to`
- Gold causal label: model input에 노출하지 않고 masking construction/evaluation에만 사용

### 7.4.2 결과

| Variant | Relation Acc. | Relation Precision | Relation Recall | Relation F1 | Node F1 | Edge F1 | Path Reachability | Root@1 | Root@3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 Graph-only | **73.83%** | 0.00% | 0.00% | 0.00% | **78.86%** | **72.83%** | 20% | 10% | 25% |
| A1 Abduction | 32.17% | 21.67% | 50.00% | 29.67% | 69.02% | 61.76% | 30% | 15% | 30% |
| A2 Abduction + DeBERTa | 34.83% | 30.83% | **57.50%** | **37.17%** | 75.68% | 67.43% | 35% | **20%** | 40% |
| A3 Abduction + PSL | 34.83% | 30.83% | **57.50%** | **37.17%** | 75.68% | 67.43% | 35% | **20%** | 40% |
| A4 Abduction + DeBERTa + PSL | 34.83% | 30.83% | **57.50%** | **37.17%** | 75.68% | 67.43% | **40%** | 15% | **45%** |

### 7.4.3 결과 해석 1: Accuracy는 causal recovery를 대표하지 못함

A0 Graph-only의 Relation Accuracy는 73.83%로 가장 높지만 Relation F1은 0%이다. Graph-only는 masked pair에 대해 positive causal relation을 하나도 복원하지 않았다.

즉 class imbalance가 존재할 때

$$
HighAccuracy \nRightarrow CausalRecovery
$$

이다. 이 때문에 본 연구는 relation masking에서 positive-class F1을 핵심 지표로 사용한다.

### 7.4.4 결과 해석 2: Abduction은 causal positive recall을 회복함

A1은 Relation Recall 50.00%, Relation F1 29.67%를 기록했다. 이는 temporal precedence와 endpoint anomaly만으로도 일부 causal relation을 복원할 수 있음을 의미한다.

반면 Relation Precision은 21.67%로 낮다. 즉 Abduction은 hypothesis coverage를 확보하는 데 유리하지만, 단독 사용 시 false positive를 충분히 억제하지 못한다.

### 7.4.5 결과 해석 3: Semantic evidence는 relation discrimination을 개선함

A2는 A1 대비 Relation Precision을 21.67%에서 30.83%로, Recall을 50.00%에서 57.50%로, F1을 29.67%에서 37.17%로 개선했다.

이는 DeBERTa contrastive NLI가 단순 temporal/anomaly prior 위에서 causal/non-causal relation을 구분하는 추가 정보를 제공했음을 의미한다.

### 7.4.6 결과 해석 4: PSL의 가치는 local relation F1만으로 평가할 수 없음

A2, A3, A4의 thresholded Relation F1은 모두 37.17%였다. 작은 20-case development set에서는 PSL이 최종 binary edge decision을 바꾸지 못했다.

그러나 A4의 Path Reachability는 35%에서 40%로, Root@3는 40%에서 45%로 상승했다. 반대로 Root@1은 20%에서 15%로 하락했다.

이 결과는 PSL의 역할을 다음과 같이 해석하게 한다.

$$
LocalRelationClassification \neq GlobalProcessReconstruction
$$

즉 동일한 relation-level F1에서도 hypothesis score/order와 path coherence가 달라져 process-level 결과가 달라질 수 있다. 다만 표본이 20개이므로 이 차이는 confirmatory conclusion이 아니라 **다음 500-case ablation에서 검증해야 하는 가설**로 취급한다.

---

## 7.5 OpenRCA 2.0 Standard 500-case: 데이터 검증 상태

현재 standard workflow는 500개 case를 10개 shard, 각 50개로 구성한다. 다음 검증이 완료되었다.

| 검증 항목 | 상태 |
|---|---|
| 10개 standard shard 생성 | 완료 |
| 각 shard 50 case assertion | 완료 |
| 총 500 case merge | 완료 |
| unique case ID = 500 | 완료 |
| gold field inference input 제거 | 코드 검증 완료 |
| A4 Full model inference | **150/500 완료 시점** |
| 500-case aggregate | 실행 완료 전이므로 본 문서에 미기재 |

따라서 아래 standard 결과는 **중간 결과(interim result)**이며 최종 논문 성능표로 확정하지 않는다.

---

## 7.6 OpenRCA 2.0 Standard A4 중간 결과: 150/500

완료된 shard 3, 4, 5는 각각 50 case이며, 총 150 case의 macro average는 다음과 같다.

| Metric | A4 Interim 150/500 |
|---|---:|
| Root Service Precision | 27.89% |
| Root Service Recall | 49.67% |
| Root Service F1 | 34.18% |
| Root Exact Set | 4.67% |
| **Any Service Hit** | **60.00%** |
| **All Service Hit** | **39.33%** |
| **Process Path Reachability** | **57.33%** |
| Node Precision | 42.17% |
| **Node Recall** | **87.07%** |
| **Node F1** | **52.94%** |
| Edge Precision | 28.87% |
| **Edge Recall** | **80.26%** |
| **Edge F1** | **38.11%** |

### 7.6.1 Shard별 안정성 확인

| Shard | Cases | Any Hit | Path Reachability | Node F1 | Edge F1 |
|---|---:|---:|---:|---:|---:|
| 3 | 50 | 66% | 62% | 53.55% | 33.34% |
| 4 | 50 | 58% | 56% | 55.06% | 39.92% |
| 5 | 50 | 56% | 54% | 50.21% | 41.07% |
| **150-case mean** | **150** | **60.00%** | **57.33%** | **52.94%** | **38.11%** |

세 shard에서 Any Hit은 56~66%, Path Reachability는 54~62%, Node-F1은 50.21~55.06% 범위로 나타났다. Edge-F1은 33.34~41.07%로 상대적으로 변동이 더 크다.

단, shard는 random sample이 아니라 manifest index에 따른 분할이므로 이 범위를 confidence interval처럼 해석해서는 안 된다.

### 7.6.2 핵심 결과 1: Root를 찾는 것과 Exact Root Set을 맞히는 것은 큰 차이가 있음

Any Service Hit은 60.00%인 반면 Root Exact Set은 4.67%이다.

이는 현재 모델이 상당수 case에서 실제 root service를 후보 안에 포함하지만, 최대 3개의 root를 반환하는 정책과 imperfect ranking으로 인해 extra root service를 함께 예측한다는 뜻이다.

즉

$$
AnyHit \gg ExactRoot
$$

이며, 현재 root ranking은 **coverage 중심으로는 일정 수준 동작하지만 calibration과 false-positive suppression이 부족하다.**

### 7.6.3 핵심 결과 2: Root를 맞힌 경우 상당수가 실제 propagation path로 연결됨

Any Hit 60.00%와 Process Path Reachability 57.33%의 차이는 2.67%p이다.

Path Reachability는 올바른 root가 있어야만 성공할 수 있으므로, 현재 완료 subset에서는 correct root를 포함한 case 중 상당수가 alarm service까지 predicted path를 형성하고 있음을 시사한다.

그러나 이 값을 조건부 비율로 직접 해석하려면 case-level 결과로 `P(Path | CorrectRoot)`를 별도로 계산해야 한다. 현재 표의 57.33/60.00 단순 비율을 공식 conditional metric으로 사용하지 않는다.

### 7.6.4 핵심 결과 3: Node는 많이 찾지만 Edge 구조가 과도하게 넓음

Node Recall은 87.07%로 높지만 Node Precision은 42.17%이다. Edge에서도 Recall 80.26%, Precision 28.87%로 동일한 패턴이 더 강하게 나타난다.

가장 중요한 현재 병목은 다음과 같다.

$$
EdgeRecall = 80.26\% \gg EdgePrecision = 28.87\%
$$

이는 hypothesis generator가 gold causal path의 많은 edge를 candidate/selected graph에 포함시키는 데는 성공하고 있지만, non-causal dependency까지 causal propagation으로 남기는 경우가 많다는 뜻이다.

따라서 현재의 오류는 주로

```text
Missing causal edge
```

보다

```text
Too many causal edges
```

형태에 가깝다.

이 결과는 다음 연구 방향을 명확하게 만든다.

$$
MoreHypotheses \not\approx BetterRCA
$$

현재 필요한 것은 후보 확대가 아니라 **causal edge precision을 높이는 calibration/pruning**이다.

### 7.6.5 핵심 결과 4: Edge-F1 38.11%를 단독으로 낮다고 해석하면 안 되는 이유

Edge-F1은 38.11%로 Node-F1 52.94%와 Path Reachability 57.33%보다 낮다. 이는 모델이 관련 service와 root-to-alarm 연결 가능성은 일정 부분 포착하면서도, graph 전체의 exact edge structure를 세밀하게 맞히는 데 어려움이 있음을 의미한다.

즉 현재 모델은 다음 상태에 가깝다.

```text
관련 서비스 탐색       : 비교적 잘 됨
정답 causal edge recall : 높음
불필요 edge 제거        : 부족함
정확한 전체 graph 복원  : 아직 부족함
```

따라서 다음 개선에서 Edge Precision이 상승하면서 Path Reachability가 유지되는지가 가장 중요한 검증 대상이다.

---

## 7.7 공식 OpenRCA 2.0 결과와의 관계

OpenRCA 공식 사이트는 standard harness에 대해 Node-F1, Edge-F1, any-hit, all-hit, path-acc 등을 제공한다. 예를 들어 2026-08-26 확인 기준 DeepResearch + Claude Opus 5는 Node-F1 80.15%, Edge-F1 66.99%, any-hit 88.80%, all-hit 64.00%, path-acc 68.80%를 기록하고 있다 [6].

그러나 현재 본 연구의 150-case 결과는 다음 이유로 공식 leaderboard와 **직접 수치 비교하지 않는다.**

- 아직 500/500 inference aggregate가 끝나지 않았다.
- 현재 완료된 150 case는 random sample이 아니다.
- 본 연구는 fault type을 별도로 예측하지 않는 현재 구현 단계이므로 leaderboard의 전체 outcome metric과 완전히 동일한 출력 범위를 갖지 않는다.

따라서 direct comparison은 500-case aggregate 완료 후 동일 metric 정의를 확인한 뒤 수행한다.

---

# 8. 논의

## 8.1 현재까지 가장 강한 실험적 결론

현재까지 가장 일관된 결론은 **좋은 RCA는 후보를 많이 생성하는 문제보다 causal/non-causal relation을 얼마나 잘 구분하고 불필요한 edge를 제거하는가의 문제**라는 점이다.

연구 과정은 다음과 같이 이동하였다.

```text
Tableau가 관계를 검증하면 되는가?
        ↓
Ontology에 관계가 없으면 검증 자체가 불가능
        ↓
누락 relation hypothesis를 생성해야 함
        ↓
Abduction으로 candidate coverage 확보
        ↓
DeBERTa로 semantic discrimination 강화
        ↓
PSL로 local evidence + path coherence 결합
        ↓
현재 결과: Recall은 높지만 Precision이 낮음
        ↓
다음 병목: Causal Edge Calibration / Pruning
```

## 8.2 PSL에 대한 현재 판단

20-case masking에서 A2/A3/A4의 Relation F1이 동일하므로 현재 결과만으로 “PSL이 relation classification을 유의하게 개선한다”고 주장할 수 없다.

반면 Full model은 Path Reachability와 Root@3에서 작은 개선을 보였다. 따라서 PSL의 가설은 **relation classifier가 아니라 process-level structured inference component**로 검증해야 한다.

향후 500-case ablation에서는 다음 비교가 핵심이다.

$$
\Delta Path = Path(A4) - Path(A2)
$$

$$
\Delta EdgeF1 = EdgeF1(A4) - EdgeF1(A2)
$$

그리고 PSL이 의미 있으려면 적어도 Path 또는 Edge 구조에서 반복 가능한 개선을 보여야 한다.

## 8.3 DeBERTa에 대한 현재 판단

과거 MAGIC 실험과 20-case relation masking 모두 semantic scorer가 candidate discrimination에 도움을 줄 가능성을 지지한다. 그러나 20-case 표본이 작고 standard A2 vs A4 500-case ablation이 아직 완료되지 않았으므로 DeBERTa의 최종 기여도 역시 확정하지 않는다.

현재 DeBERTa는 novelty가 아니라 **semantic grounding module**이다.

## 8.4 Root ranking의 한계

현재 max root causes가 3으로 고정되어 있어 Any Hit을 높이는 대신 Exact Root Precision을 낮출 수 있다. 따라서 향후에는 다음을 검토해야 한다.

- fixed Top-3 대신 confidence-based root set selection
- root score margin에 따른 adaptive cutoff
- incident별 expected root cardinality 추정

다만 이러한 개선은 development split에서만 조정하고 최종 test set에서는 고정해야 한다.

## 8.5 다음 핵심 개선: Edge Precision

현재 standard interim 결과에서 가장 명확한 개선 지점은 Edge Precision 28.87%이다.

다음 개선 후보는 다음과 같다.

1. PSL edge threshold calibration
2. source-target anomaly time-lag의 연속형 모델링
3. negative evidence 강화
4. path-minimality 또는 sparsity constraint 강화
5. 동일 symptom에 도달하는 redundant branch pruning
6. semantic score reliability calibration
7. system별 threshold가 아닌 validation-set 기반 global calibration

목표는 단순히 edge 수를 줄이는 것이 아니라 다음 조건을 만족하는 것이다.

$$
Precision \uparrow,\quad Recall \approx 유지,\quad PathReachability \approx 유지
$$

---

# 9. 타당성 위협 및 제한사항

## 9.1 150/500 결과는 최종 결과가 아님

현재 standard 결과는 500개 중 150개만 inference가 완료된 시점의 중간값이다. 따라서 최종 논문에서 이 값을 확정 성능으로 사용하지 않는다.

## 9.2 Shard ordering bias

완료된 shard 3, 4, 5는 manifest 순서에 따른 부분집합이며 random sampling이 아니다. system/fault distribution이 전체 500개와 다를 수 있다.

## 9.3 20-case masking은 development benchmark

Relation masking 20-case 결과는 설계 오류 수정 후의 corrected benchmark이지만 표본이 작고 hyperparameter 개발에 사용된 development set이다. 따라서 statistical significance 또는 generalization claim을 하지 않는다.

## 9.4 Causality와 temporal correlation의 구분

Temporal precedence, anomaly co-occurrence, NLI support 및 PSL consistency는 causal evidence를 강화하지만 그 자체로 intervention-based causal proof는 아니다. OpenRCA 2.0의 PAVE gold는 fault injection intervention에서 forward verification된 ground truth이므로 평가에는 적합하지만, 본 모델의 inference score 자체를 “인과관계가 증명되었다”고 표현해서는 안 된다.

## 9.5 Service-level abstraction

현재 주요 metric은 service-level directed pair를 사용한다. 실제 장애는 pod, container, database, SQL, instance, network component 수준에서 시작될 수 있으므로 향후 component-level relation recovery로 확장할 필요가 있다.

---

# 10. 재현성 및 결과 사용 원칙

본 연구는 실험 과정에서 발견된 구현 오류를 결과 해석과 분리한다. 다음 원칙을 적용한다.

1. gold causal graph/root label은 evaluator 이외의 inference code에 전달하지 않는다.
2. provenance/audit metadata를 semantic proposition에 혼입하지 않는다.
3. relation masking에서는 endpoint connectivity를 제거하지 않고 relation semantics만 숨긴다.
4. observed connectivity 자체에는 causal positive score를 주지 않는다.
5. class imbalance가 큰 relation task에서 Accuracy만으로 우수성을 주장하지 않는다.
6. development에서 선택한 threshold/weight를 test result를 보고 재조정하지 않는다.
7. 중간 shard 결과와 최종 500-case aggregate를 명확히 구분한다.
8. 공식 OpenRCA leaderboard와 비교할 때 동일 입력 조건과 metric scope가 확인된 결과만 direct comparison으로 표기한다.

---

# 11. 결론

본 연구는 불완전한 운영 지식 그래프에서 사전에 정의되지 않은 incident-specific causal relation을 telemetry evidence로 복원하고, 이를 root-cause propagation path로 연결하는 RCA 방법을 연구한다. 초기의 Rashomon Worlds + Tableau 접근에서 출발했으나, 실제 ontology의 relation incompleteness와 noisy evidence 문제를 확인한 뒤 현재는 Abductive Hypothesis Generation + DeBERTa Contrastive NLI + Probabilistic Soft Logic의 구조로 재정의하였다.

현재까지의 controlled relation-masking 결과는 Abduction이 positive causal relation recall을 확보하고, semantic evidence가 relation discrimination을 개선할 수 있음을 보여준다. Full model의 작은 20-case 실험에서는 relation F1 자체보다 process-level Path Reachability에서 추가 개선이 관찰되었다.

OpenRCA 2.0 standard에서는 500/500 데이터 정규화 및 leakage-safe evaluation pipeline 검증을 완료하였다. 현재 완료된 150 case에서 Any Service Hit 60.00%, Process Path Reachability 57.33%, Node-F1 52.94%, Edge-F1 38.11%를 기록하였다. 가장 중요한 진단은 Edge Recall 80.26% 대비 Edge Precision 28.87%라는 비대칭이다. 이는 현재 모델이 causal propagation 후보를 충분히 찾고 있으나 non-causal edge를 과도하게 유지하고 있음을 의미한다.

따라서 다음 연구 단계의 핵심 질문은 더 이상 “누락 관계 후보를 더 많이 만들 수 있는가”가 아니다. 다음을 검증해야 한다.

$$
Can\ we\ remove\ false\ causal\ edges\ without\ losing\ the\ true\ propagation\ path?
$$

즉 **정답 causal path의 recall을 유지하면서 graph precision을 높이는 evidence-grounded causal pruning**이 현재 연구의 가장 직접적인 후속 과제이다.

---

# 참고문헌

[1] A. Fang, Y. Yang, J. Shang, Q. Lu, J. Xu, R. Wang, S. Zhang, Y. Zhang, B. Yu, and P. He, “OpenRCA 2.0: From Outcome Labels to Causal Process Supervision,” arXiv:2606.27154, 2026. https://arxiv.org/abs/2606.27154

[2] J. R. Hobbs, M. E. Stickel, D. E. Appelt, and P. Martin, “Interpretation as Abduction,” *Artificial Intelligence*, vol. 63, no. 1–2, pp. 69–142, 1993. https://doi.org/10.1016/0004-3702(93)90015-4

[3] J. Bai, Y. Wang, T. Zheng, Y. Guo, X. Liu, and Y. Song, “Advancing Abductive Reasoning in Knowledge Graphs through Complex Logical Hypothesis Generation,” *Proceedings of ACL 2024*, pp. 1312–1329, 2024. https://aclanthology.org/2024.acl-long.72/

[4] P. He, X. Liu, J. Gao, and W. Chen, “DeBERTa: Decoding-Enhanced BERT with Disentangled Attention,” *International Conference on Learning Representations (ICLR)*, 2021. https://openreview.net/forum?id=XPZIaotutsD

[5] S. H. Bach, M. Broecheler, B. Huang, and L. Getoor, “Hinge-Loss Markov Random Fields and Probabilistic Soft Logic,” *Journal of Machine Learning Research*, vol. 18, no. 109, pp. 1–67, 2017. https://jmlr.org/papers/v18/15-631.html

[6] OpenRCA Official Leaderboard, “OpenRCA 2.0,” accessed 2026-08-26. https://microsoft.github.io/OpenRCA/

---

# Appendix A. 현재 결과의 상태 구분

| Result | Status | 논문 사용 방식 |
|---|---|---|
| MAGIC path coverage vs Tableau detection | 선행 구조 실험 | 연구 동기 설명 |
| DAFNA-EA candidate coverage 93% vs exact selection 62% | 선행 실험 | 후보 생성/선택 분리 근거 |
| MAGIC weak lexical vs DeBERTa | 검증된 structured 선행 비교 | semantic scorer 선택 근거 |
| 수정 전 natural-language MAGIC | **폐기** | 최종 성능 근거 사용 금지 |
| Relation Masking 20-case corrected | Development result | ablation 방향성 근거 |
| OpenRCA2 Standard normalized 500/500 | 검증 완료 | protocol/reproducibility 근거 |
| OpenRCA2 A4 150/500 | **Interim** | 중간 진단만 사용 |
| OpenRCA2 A4 500/500 aggregate | Pending | 완료 후 최종 주요 결과로 교체 |

# Appendix B. GitHub Markdown 수식 표기 원칙

본 문서의 수식은 GitHub Markdown math renderer에서 깨지는 문제를 줄이기 위해 다음 원칙으로 작성하였다.

- display equation은 `$$ ... $$`만 사용한다.
- 수식 내부에 한글 문장을 넣지 않는다.
- 복잡한 `\boxed`, nested `\text{}`, 과도한 `aligned` 환경을 사용하지 않는다.
- piecewise 정의는 복잡한 LaTeX `cases` 대신 표와 단순 수식으로 분리한다.
- `\neq`, `\Rightarrow`, `\leadsto`, `\arg\min` 등 GitHub가 안정적으로 지원하는 기본 명령만 사용한다.
