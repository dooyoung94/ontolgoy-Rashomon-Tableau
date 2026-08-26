# 불완전한 운영 온톨로지에서의 구조 관계 복원과 사건별 인과 경로 추론

**Structural Relation Recovery and Incident-Specific Causal Path Reasoning over Incomplete Operational Ontologies**

> 작성 기준: 2026-08-26  
> 대상 benchmark: OpenRCA 2.0 계열 `anon-ops/ops-lite` 500-case  
> 현재 500-case 20/40/60% 실험은 **Stage 2 causal-relation qualification** 실험이며, Stage 1 structural-relation 성능으로 해석하지 않는다.

---

## 초록

실제 Root Cause Analysis(RCA) 환경에서는 CMDB나 ontology가 완전하지 않다. 서비스 호출, 배포 위치, 데이터베이스 사용, 메시징 사용과 같은 운영 구조가 부분적으로 누락될 수 있으며, 구조적으로 연결된 두 구성요소가 특정 incident에서 실제 장애 전파에 참여했는지도 별도의 추론이 필요하다. 기존 접근은 이 두 문제를 하나의 causal edge prediction 문제로 합치는 경우가 많아, **운영 구조를 복원하는 문제**와 **사건별 인과관계를 판정하는 문제**가 혼재될 수 있다.

본 연구는 이를 두 단계로 분리한다. **Stage 1 Structural Relation Recovery**에서는 model-visible telemetry만 사용하여 `CALLS`, `DEPLOYED_ON`, `RUNS_ON`, `USES_DATABASE`, `USES_MESSAGING`과 같은 typed operational relation을 구성한다. **Stage 2 Incident Causal Qualification**에서는 Stage 1에서 확인된 구조적 dependency를 후보 영역으로 사용하되, 연결성 자체를 causal evidence로 사용하지 않고 incident telemetry의 시간 선후, 이상도, 의미적 지지 및 전역 경로 일관성을 이용하여 `causal_propagates_to`와 `non_causal_dependency`를 판정한다. Stage 2는 Abductive Hypothesis Generation, DeBERTa 기반 contrastive semantic scoring, Probabilistic Soft Logic(PSL), 그리고 선택적으로 constrained LLM adjudication으로 구성된다.

OpenRCA 2.0 계열 데이터는 trace, metric, log와 root-cause/causal-process 정답을 제공하므로 사건별 causal reconstruction을 평가할 수 있다. 다만 benchmark의 `causal_graph.json`은 구조 관계 타입의 정답표가 아니라 사건별 causal propagation supervision이므로, 본 연구는 PAVE/causal gold를 Stage 1 입력이나 구조 relation 생성에 사용하지 않는다. 구조 relation은 telemetry에 실제 속성이 존재할 때만 생성하며, 데이터가 노출하지 않는 DB·pod·node·messaging 관계를 임의로 보완하지 않는다.

기존 20-case controlled causal-relation masking 개발 실험에서 Abduction의 Relation F1은 29.67%였고, DeBERTa를 결합하면 37.17%로 향상되었다. Full model은 Relation F1 자체는 37.17%로 동일했으나 Path Reachability를 35%에서 40%, Root@3를 40%에서 45%로 개선하였다. Standard 150-case 중간 실험에서는 Edge Recall 80.26%에 비해 Edge Precision이 28.87%로 낮아, 현재 Stage 2의 주 병목이 후보 수의 폭발보다 false-positive causal edge의 과잉 유지임을 확인했다. 이 결과는 structural relation recovery와 incident causal qualification을 분리하여 평가해야 함을 뒷받침한다.

**주요어:** Root Cause Analysis, OpenRCA 2.0, Operational Ontology, Structural Relation Recovery, Causal Process Reconstruction, Abductive Reasoning, DeBERTa, Probabilistic Soft Logic

---

# 1. 서론

## 1.1 현실적 문제

운영자가 RCA를 수행할 때 필요한 지식은 단순한 서비스 목록이 아니다. 실제로는 다음과 같은 관계가 필요하다.

```text
System      --HAS_SERVICE-->   Service
Service     --CALLS-->         Service
Service     --DEPLOYED_ON-->   Pod
Pod         --RUNS_ON-->       Node
Service     --USES_DATABASE--> Database
Service     --USES_MESSAGING--> MessagingSystem
```

그러나 현실의 CMDB, topology, ontology는 자주 불완전하다. 신규 배포, 동적 scaling, 외부 DB 연결, 비정형 로그 기반 의존성 등은 정적 자산관리 정보에 즉시 반영되지 않을 수 있다. 따라서 RCA 이전에 **“무엇이 무엇과 어떤 관계로 연결되어 있는가”**를 관측 데이터로 보완해야 한다.

그 다음에는 또 다른 문제가 있다. 예를 들어

```text
frontend --CALLS--> order-service
```

가 정상 구조로 존재하더라도 모든 incident에서 `order-service`가 `frontend` 장애의 원인은 아니다. 특정 incident에서는 다음과 같은 별도의 인과 판정이 필요하다.

```text
order-service --causal_propagates_to--> frontend
```

즉 본 연구는 다음을 구분한다.

$$
\text{Structural Relation} \neq \text{Incident Causal Relation}
$$

## 1.2 연구 목적

본 연구의 목적은 완전한 운영 ontology를 가정하지 않고 telemetry로 구조적 관계를 구성한 뒤, 그 구조 위에서 사건별 causal process와 root cause를 추론하는 것이다.

```text
Telemetry
   ↓
Stage 1. Structural Relation Recovery
   CALLS / DEPLOYED_ON / RUNS_ON / USES_DATABASE / ...
   ↓
Operational Graph G_S
   ↓
Stage 2. Incident Causal Qualification
   causal_propagates_to / non_causal_dependency
   ↓
Incident Causal Graph G_C^(i)
   ↓
Root Cause → Propagation Path → Symptom
```

이 분리는 연구의 설명력을 높인다. Stage 1이 실패했는지, Stage 2의 causal discrimination이 실패했는지, 또는 causal graph는 적절하지만 root ranking이 실패했는지를 각각 측정할 수 있기 때문이다.

## 1.3 연구 질문

**RQ1. Structural induction.** Telemetry만으로 RCA에 필요한 typed operational relation을 어느 범위까지 관찰·복원할 수 있는가?

**RQ2. Abduction.** 관찰된 구조 relation을 후보 공간으로 제한한 abductive hypothesis generation이 무제한 node-pair 생성 없이 incident causal relation 복원에 기여하는가?

**RQ3. Semantic discrimination.** DeBERTa 기반 causal/non-causal contrastive scoring이 시간·이상도 기반 추론보다 causal relation precision/F1을 개선하는가?

**RQ4. Global coherence.** PSL을 이용한 soft global inference가 local relation classification을 넘어 causal process path reconstruction을 개선하는가?

**RQ5. Final adjudication.** A5 constrained LLM adjudication이 새로운 endpoint를 발명하지 않으면서 false-positive causal edge를 줄이고 최종 RCA 성능을 개선하는가?

## 1.4 연구 기여

본 연구의 기여는 다음과 같다.

1. 운영 topology 복원과 incident causal reconstruction을 **두 개의 명시적 relation layer**로 분리한다.
2. 구조 관계는 PAVE gold가 아니라 **model-visible telemetry만으로 생성**하여 gold leakage를 차단한다.
3. `CALLS`와 causal propagation의 방향을 분리한다. 구조상 `caller→callee`와 장애 전파 후보 `callee→caller`를 같은 edge로 취급하지 않는다.
4. Abduction의 후보 범위를 실제 관찰된 structural dependency에 제한하여 all-pairs candidate explosion을 방지한다.
5. DeBERTa, PSL, LLM의 역할을 각각 semantic discrimination, global consistency, final adjudication으로 분리한다.
6. Structural relation, causal relation, process graph, root cause를 서로 다른 metric으로 평가한다.

---

# 2. OpenRCA 2.0과 데이터 경계

OpenRCA 2.0 계열 benchmark는 microservice incident에 대해 정상/비정상 trace, metric, log와 root-cause 및 causal-process 정답을 제공한다. 본 연구가 사용하는 `anon-ops/ops-lite`는 500개 case로 구성되며 Train-Ticket, Hotel Reservation, OpenTelemetry Demo 세 시스템을 포함한다.

중요한 데이터 경계는 다음과 같다.

### Model-visible

- normal/abnormal traces
- normal/abnormal metrics
- normal/abnormal logs
- incident symptom information
- telemetry에서 직접 추출된 structural observations

### Evaluator-only

- `causal_graph.json`
- root-cause gold
- injection ground truth
- PAVE/manifest-derived causal process label

`causal_graph.json`은 사건별 causal propagation을 평가하기 위한 supervision이다. 이를 `CALLS`, `USES_DATABASE`, `RUNS_ON` 등의 구조 관계 생성에 사용하면 Stage 1과 Stage 2가 다시 섞이고 leakage가 발생할 수 있으므로 사용하지 않는다.

또한 OpenRCA benchmark는 완전한 기업 CMDB가 아니다. 따라서 telemetry에 DB system, pod, node, messaging destination 속성이 없다면 해당 typed relation은 **unknown/unsupported**로 남겨야 하며, 서비스 이름 패턴이나 gold causal edge에서 추측하여 채우지 않는다.

---

# 3. 문제 정의

## 3.1 Stage 1: Structural Relation Recovery

운영 구조 그래프를 다음과 같이 정의한다.

$$
G_S=(V_S,E_S,T)
$$

여기서 $V_S$는 service, pod, node, database, messaging system 등의 entity이며, $T$는 structural relation type 집합이다.

$$
T=\{CALLS, DEPLOYED\_ON, RUNS\_ON, USES\_DATABASE, USES\_MESSAGING, \ldots\}
$$

각 구조 relation은 typed triple이다.

$$
e_s=(u,t,v), \quad t\in T
$$

예:

$$
(service{:}frontend, CALLS, service{:}orders)
$$

$$
(service{:}orders, USES\_DATABASE, database{:}postgresql{:}orders-db)
$$

Stage 1은 raw telemetry $Z$로부터

$$
\hat E_S=f_{struct}(Z)
$$

를 구성한다.

## 3.2 Stage 2: Incident Causal Qualification

incident $i$에 대해 structural dependency가 실제 장애 전파에 참여했는지를 이진 변수로 둔다.

$$
z_e^{(i)}\in\{0,1\}
$$

- $z_e^{(i)}=1$: incident causal propagation에 참여
- $z_e^{(i)}=0$: 구조적으로 존재하지만 해당 incident의 causal propagation에는 참여하지 않음

Stage 2 출력은

$$
G_C^{(i)}=(V_C,E_C^{(i)})
$$

이며 $E_C^{(i)}$는 incident-specific causal edge 집합이다.

서비스 호출에서는 자연 topology 방향과 장애 전파 후보 방향을 명시적으로 구분한다.

```text
Natural structural direction
caller --CALLS--> callee

Potential synchronous failure propagation
callee --causal_propagates_to--> caller
```

따라서 단순 graph reachability는 causal relation의 증거가 아니다.

## 3.3 최종 RCA

모델은 causal graph와 root ranking을 함께 출력한다.

$$
\hat R^{(i)}=[\hat r_1,\hat r_2,\ldots,\hat r_k]
$$

최종 목표는 단순 root hit가 아니라 올바른 root에서 symptom/alarm까지 검증 가능한 predicted path를 제공하는 것이다.

---

# 4. 제안 방법

## 4.1 Telemetry-derived Structural Induction

현재 구현은 relation별로 명시적 extractor를 사용한다.

### CALLS

분산 trace의 `trace_id`, `span_id`, `parent_span_id`, `service_name`을 결합하여 parent span의 service를 caller, child span의 service를 callee로 해석한다.

```text
parent service --CALLS--> child service
```

### DEPLOYED_ON / RUNS_ON

trace/metric/log에 노출된 Kubernetes 또는 host attribute를 이용한다.

```text
service --DEPLOYED_ON--> pod
pod     --RUNS_ON--> node
```

### USES_DATABASE

`db.system`, server/peer address, namespace/name과 같은 OpenTelemetry 속성이 존재할 때만 생성한다.

```text
service --USES_DATABASE--> database
```

### USES_MESSAGING

`messaging.system`, destination 속성이 존재할 때만 생성한다.

```text
service --USES_MESSAGING--> messaging target
```

핵심 원칙은 **relation type별 evidence가 없으면 생성하지 않는 것**이다.

## 4.2 Structural Graph에서 Causal Candidate로의 Projection

현재 OpenRCA service-level causal evaluator와 호환하기 위해 `CALLS` relation만 service causal candidate로 projection한다.

```text
frontend --CALLS--> orders
                 ↓ projection
orders --dependency_propagates_to?--> frontend
```

DB/pod/node와 같은 heterogeneous relation은 `structural_relations`에 보존하고 임의로 service-service causal edge로 붕괴시키지 않는다. 향후 heterogeneous causal evaluator가 확보되면 직접 causal reasoning 대상으로 확장할 수 있다.

## 4.3 Abductive Hypothesis Generation

Abduction은 모든 node pair를 조합하지 않는다. Stage 1에서 관찰된 dependency 또는 Stage 2 controlled masking에서 endpoint가 보존된 pair만 causal hypothesis 후보가 된다.

$$
H_i=\{CAUSES(u,v)\mid (u,v)\in E_{candidate}^{(i)}\}
$$

각 후보의 초기 점수는 incident-specific temporal precedence와 endpoint anomaly로 계산한다.

$$
A_{uv}=0.55T_{uv}+0.45N_{uv}
$$

연결성 자체는 $A_{uv}$에 가산되지 않는다.

## 4.4 DeBERTa Contrastive Semantic Scoring

각 후보에 대해 같은 telemetry premise에 다음 두 가설을 비교한다.

```text
H+ : source anomaly causally propagated to target
H- : observed dependency did not propagate the incident anomaly
```

DeBERTa NLI의 절대 entailment만 사용하는 대신 두 가설의 상대적 entailment margin을 사용하고, 두 가설 모두 entailment가 낮으면 neutral에 가깝게 유지한다.

이를 통해 낮은 entailment 값의 작은 수치 차이를 과대증폭하는 문제를 줄인다.

## 4.5 PSL Global Inference

PSL은 temporal, anomaly, semantic evidence와 path coherence를 soft logic으로 결합한다. 구조적 dependency만 존재한다는 이유로 `CAUSES`를 강제하는 규칙은 사용하지 않는다.

PSL의 역할은 개별 edge classifier를 대체하는 것이 아니라, locally plausible한 관계들이 전체 root-to-symptom process에서 일관된지 조정하는 것이다.

## 4.6 A5 Constrained LLM Adjudication

A5는 A4 결과에 대한 최종 adjudicator이다. 입력은 masked observed pair, A4 decision/score, temporal/anomaly signal, semantic margin, PSL score, root ranking 및 telemetry evidence이다.

LLM은 **기존 observed candidate pair의 causal/non-causal 판정만 수정할 수 있고 새로운 endpoint pair를 생성할 수 없다.** 따라서 A5의 목표는 candidate expansion이 아니라 false-positive pruning과 최종 root/path 조정이다.

---

# 5. 실험 설계

연구를 두 relation layer와 최종 RCA로 분리하여 다음 트랙을 사용한다.

## 5.1 Track S — Structural Relation Audit / Recovery

Stage 1 자체를 평가한다.

1. normal telemetry에서 structural relation을 추출한다.
2. relation type별 관찰 coverage를 보고한다.
3. independent telemetry window 또는 별도 topology reference가 가능한 relation에 대해 typed triple P/R/F1을 측정한다.
4. endpoint entity type만으로 정답 relation이 자명해지는 단순 label-mask는 main structural benchmark로 사용하지 않는다.

핵심 지표:

- relation type별 count/coverage
- typed triple Precision / Recall / F1 (reference가 존재하는 경우)
- service CALLS coverage
- DB/pod/node/messaging relation observable-case rate

## 5.2 Track C — Controlled Incident Causal Qualification

현재 진행 중인 20/40/60% relation masking 실험이다.

여기서 mask되는 것은 `CALLS`, `USES_DATABASE`가 아니라 **관찰된 service dependency pair의 incident causal semantics**이다.

```text
causal_propagates_to
vs
non_causal_dependency
```

Mask ratio:

```text
20% / 40% / 60%
```

endpoint pair는 보존되며 gold causal label은 evaluator에서만 사용한다.

### Ablation

```text
A0  Graph/visible causal facts only
A1  Abduction
A2  Abduction + DeBERTa
A3  Abduction + PSL
A4  Abduction + DeBERTa + PSL
A5  A4 + constrained LLM adjudication
```

Direct LLM relation baseline은 A5와 분리하여 비교한다.

## 5.3 Track O — OpenRCA Standard

agent에 gold topology/causal graph를 주지 않고 telemetry만으로 구조와 incident causal process를 추론한다. 이 트랙이 최종 end-to-end 현실성 검증이다.

## 5.4 Two-stage End-to-End 평가

최종 연구에서는 다음 두 조건을 분리해 비교한다.

### C1 — Observed-Structure / Oracle-Candidate Condition

관찰 가능한 structural candidate가 확보되었다고 두고 Stage 2 성능을 격리한다. 현재 500-case controlled causal-mask 실험이 이 역할에 가깝다.

### C2 — Recovered-Structure Condition

Stage 1에서 telemetry로 복원한 structural graph를 실제 Stage 2 입력으로 사용한다.

C1과 C2 차이는 structural recovery error가 최종 RCA에 미치는 영향을 보여준다.

---

# 6. 평가 지표

## 6.1 Structural Recovery

- Structural typed-triple Precision
- Structural typed-triple Recall
- Structural typed-triple F1
- relation type별 telemetry coverage

## 6.2 Incident Causal Qualification

- Relation Precision / Recall / F1 (`causal_propagates_to` positive)
- Predicted-positive rate
- false-positive causal retention

## 6.3 Process Reconstruction

- Node Precision / Recall / F1
- Edge Precision / Recall / F1
- Process Path Reachability

## 6.4 Final RCA

- Any Service Hit (AnySvc)
- Root-service Precision / Recall / F1
- Root@1 / Root@3
- Exact root set

본 코드의 `root_service_f1`은 service-only 보조 지표이며 OpenRCA 공식 `(service, fault-kind)` F1과 동일 지표로 주장하지 않는다.

---

# 7. 현재 실험 결과

## 7.1 20-case Controlled Causal-Relation Masking Pilot

40% incident causal relation label을 masking한 개발용 20-case 결과는 다음과 같다.

| Variant | Relation F1 | Node F1 | Edge F1 | Path Reachability | Root@1 | Root@3 |
|---|---:|---:|---:|---:|---:|---:|
| A0 Graph-only | 0.00% | 78.86% | 72.83% | 20% | 10% | 25% |
| A1 Abduction | 29.67% | 69.02% | 61.76% | 30% | 15% | 30% |
| A2 Abduction + DeBERTa | **37.17%** | 75.68% | 67.43% | 35% | **20%** | 40% |
| A3 Abduction + PSL | **37.17%** | 75.68% | 67.43% | 35% | **20%** | 40% |
| A4 Full | **37.17%** | 75.68% | 67.43% | **40%** | 15% | **45%** |

A1→A2에서 Relation F1이 29.67%에서 37.17%로 증가하여 semantic discrimination의 이득이 나타났다. A2/A3/A4의 thresholded Relation F1은 동일하지만 A4는 Path Reachability와 Root@3를 추가 개선했다. 이는 local relation classification과 global process reconstruction이 동일한 문제가 아님을 보여준다.

이 표는 **Stage 2 causal-relation 성능**이며 `CALLS/USES_DATABASE/RUNS_ON` 복원 성능으로 해석해서는 안 된다.

## 7.2 Standard 150-case Intermediate Result

A4 Full의 150/500 case 중간 결과는 다음과 같다.

| Metric | Result |
|---|---:|
| Any Service Hit | 60.00% |
| All Service Hit | 39.33% |
| Process Path Reachability | 57.33% |
| Node F1 | 52.94% |
| Edge F1 | 38.11% |
| Edge Recall | 80.26% |
| Edge Precision | 28.87% |

Recall에 비해 Precision이 크게 낮다. 따라서 현재 병목은 “관계를 더 많이 생성해야 한다”가 아니라 **관찰된 후보 중 causal로 남길 edge를 더 엄격하게 판정해야 한다**는 데 있다.

## 7.3 500-case Final Controlled Run

500-case × mask 20/40/60% × A0-A5 실험은 Stage 2 causal qualification의 최종 controlled evaluation으로 사용한다. 완료 전 수치를 논문에 추정하여 채우지 않는다.

최종 표에서는 최소 다음을 보고한다.

| Mask | Variant | Rel F1 | Edge P | Edge R | Edge F1 | Path | AnySvc | Root@1 | Root@3 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | A0-A5 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 40 | A0-A5 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 60 | A0-A5 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

특히 A5가 A4 대비 recall을 지나치게 훼손하지 않으면서 precision을 높이는지가 핵심이다.

---

# 8. 코드-연구 정합성 원칙

본 연구 구현은 다음 원칙을 강제한다.

1. **Structural relation과 causal relation을 같은 `relation` 의미로 부르지 않는다.**
2. `RcaCase.structural_relations`에 typed operational triples를 별도로 보존한다.
3. 기존 `known_edges`는 Stage 2 service propagation candidate로 유지하여 기존 결과 재현성을 보존한다.
4. `mask_relation_types()`는 backward compatibility를 위해 유지하지만 의미를 **Stage-2 causal semantic masking**으로 명시한다.
5. Stage 1 extractor는 `causal_graph.json`과 injection labels를 읽지 않는다.
6. DB/pod/node/messaging relation은 관련 telemetry attribute가 없으면 생성하지 않는다.
7. `CALLS`의 natural direction과 failure-propagation candidate direction을 명시적으로 변환한다.
8. A5는 observed endpoint candidate 밖의 edge를 발명할 수 없다.

---

# 9. 위협 요인과 한계

## 9.1 Structural Ground Truth의 제한

OpenRCA의 causal graph는 typed operational ontology의 완전한 정답이 아니다. 따라서 Stage 1의 `USES_DATABASE`, `RUNS_ON` 등은 데이터가 제공하는 telemetry attribute 범위에서만 검증 가능하다. 완전한 structural gold가 없는 relation은 coverage/audit 결과와 별도의 reference topology가 필요하다.

## 9.2 Typed Endpoint Leakage

`service→database` endpoint를 그대로 제공하고 relation label만 mask하면 `USES_DATABASE`가 거의 자명해질 수 있다. 따라서 단순 structural label masking을 주요 성능 실험으로 사용하지 않는다. 독립 telemetry window에서 relation을 재구성하거나 전체 typed triple holdout/reference comparison을 사용해야 한다.

## 9.3 Service-level Causal Evaluation

현재 OpenRCA causal evaluator는 주로 service-level propagation을 평가하므로 pod/node/database와 같은 heterogeneous entity의 full causal graph를 직접 평가하지 못한다. 본 연구에서는 heterogeneous structure를 보존하되 service projection과 분리한다.

## 9.4 Structural Recovery와 Causal Qualification의 오류 전파

Stage 2 결과가 좋아도 Stage 1에서 중요한 dependency를 놓치면 end-to-end RCA는 실패할 수 있다. 반대로 Stage 1 coverage가 높더라도 Stage 2 precision이 낮으면 false-positive causal path가 증가한다. 따라서 C1/C2 조건을 분리한 실험이 필요하다.

## 9.5 현재 결과의 범위

현재 20-case와 150-case 수치는 주로 Stage 2를 검증한다. 이 결과만으로 structural ontology recovery 성능이 입증되었다고 주장하지 않는다.

---

# 10. 결론

본 연구가 해결하려는 현실적 문제는 단순 “missing causal edge prediction”이 아니다. 실제 운영 환경에서는 먼저 불완전한 CMDB/ontology를 telemetry로 보완하여 **현실적인 typed structural relation**을 구성해야 하고, 이후 그 관계들이 특정 incident의 장애 전파에 실제로 참여했는지를 별도로 판정해야 한다.

따라서 최종 방법론은 다음과 같이 정리된다.

$$
\boxed{
Telemetry
\rightarrow Structural\ Relation\ Recovery
\rightarrow Incident\ Causal\ Qualification
\rightarrow Causal\ Process\ Reconstruction
\rightarrow RCA
}
$$

현재 relation masking 실험은 이 중 두 번째 추론 단계인 incident causal qualification을 통제된 조건에서 검증한다. 새 structural layer는 첫 번째 단계를 코드와 논문에 명시적으로 추가하며, 향후 end-to-end 평가는 recovered structural graph를 실제 causal reasoning 입력으로 사용하여 두 단계의 결합 효과를 측정한다.

이 구조는 연구 결과를 현실 운영 문제와 직접 연결한다. 즉 “관계가 완전하지 않은 환경에서 구조를 관측으로 복원하고, 그 위에서 실제 장애 전파 관계만 선별하여 root cause와 설명 가능한 propagation path를 제공한다”는 것이 본 연구의 최종 주장이다.

---

# 참고문헌

[1] *OpenRCA 2.0: From Outcome Labels to Causal Process Supervision*, 2026.  
[2] J. R. Hobbs et al., *Interpretation as Abduction*, 1993.  
[3] Abductive reasoning / logical hypothesis generation over knowledge graphs 관련 연구.  
[4] P. He et al., *DeBERTa: Decoding-enhanced BERT with Disentangled Attention*, ICLR, 2021.  
[5] S. Bach et al., *Hinge-Loss Markov Random Fields and Probabilistic Soft Logic*, JMLR, 2017.  
[6] `anon-ops/ops-lite`, 500-case microservice RCA benchmark artifact, 2026.
