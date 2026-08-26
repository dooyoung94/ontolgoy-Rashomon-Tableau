# Abductive Structural Relation Recovery for OpenRCA 2.0

## 연구 목표

실제 운영환경에서는 CMDB, topology, ontology, business logic을 사람이 완전하게 정의하기 어렵다. 수집기를 통해 Service, Pod, Node, Database 등의 객체는 관찰되더라도 **객체 사이의 관계가 누락되거나 의미가 불명확한 상태**가 남을 수 있다.

본 연구의 중심 문제는 일반적인 “missing edge 생성”이 아니다. 그래프의 edge는 표현 단위일 뿐이며, 실제 연구대상은 다음과 같은 **typed structural relation triple**이다.

```text
(source, relation, target)

Service --CALLS--> Service
Service --DEPLOYED_ON--> Pod
Pod     --RUNS_ON--> Node
Service --USES_DATABASE--> Database
Service --USES_MESSAGING--> MessagingSystem
```

따라서 핵심 연구 질문은 다음과 같다.

> **불완전한 운영 지식과 telemetry 관측만으로 가능한 Structural Relation 후보를 생성하고, 그중 근거 있는 관계를 선별하여 Operational Graph를 복원할 수 있는가? 그리고 복원된 관계가 실제 causal-process RCA 성능을 개선하는가?**

---

## 1. 문제 정의

### 현실 문제

```text
CMDB / Ontology

Application: payment-api
Database:    payment-db
Pod:         payment-api-1
Node:        node-3

하지만 일부 관계는 미정의 / 미수집 / 최신화 지연
```

운영자가 모든 관계를 수작업으로 입력하도록 요구하면 동적 배포, 신규 서비스, 외부 데이터소스, 런타임 호출구조를 지속적으로 반영하기 어렵다.

본 연구는 이를 다음 두 문제로 분리한다.

### Stage 1 — Structural Relation Recovery

```text
Incomplete Operational Knowledge
            +
Model-visible Telemetry
            ↓
Relation Observation
            ↓
Abductive Relation Hypotheses
            ↓
DeBERTa Semantic Validation
            ↓
PSL Global Selection
            ↓
Recovered Structural Relations
```

### Stage 2 — Incident Causal Qualification

구조적으로 연결되었다고 해서 그 관계가 모든 incident에서 원인은 아니다.

```text
Structural topology
frontend --CALLS--> orders

Incident-specific failure propagation
orders --causal_propagates_to--> frontend
```

따라서 Stage 2에서는 복원된 구조를 후보 공간으로 사용하고, 특정 incident에서 실제 장애 전파에 참여한 관계만 판정한다.

```text
causal_propagates_to
non_causal_dependency
```

### Final — LLM RCA

LLM의 주 역할은 Structural Relation을 임의 생성하는 것이 아니라, 검증된 구조·인과 그래프와 telemetry evidence를 이용해 운영자가 사용할 RCA 결과를 생성하는 것이다.

```text
Root Cause
Propagation Path
Impact
Action
```

---

## 2. 핵심 파이프라인

```text
CMDB / Ontology / Telemetry
          |
          v
[1] Relation Observation
    trace parent-child
    service/pod resource context
    pod/node resource context
    DB / messaging context when observable
          |
          v
[2] Abduction
    possible (source, relation, target)
    hypotheses only from telemetry-grounded endpoints
          |
          v
[3] DeBERTa
    relation-support vs non-support
    contrastive semantic validation
          |
          v
[4] PSL
    ontology/type consistency
    competing candidate selection
    sparsity / global coherence
          |
          v
Recovered Operational Structural Graph
          |
          v
[5] Incident Causal Qualification
    temporal + anomaly + semantic + path coherence
          |
          v
Incident Causal Graph
          |
          v
[6] LLM RCA
    Root Cause → Path → Impact → Action
```

---

## 3. 각 구성요소의 역할

| 단계 | 해결하려는 문제 | 역할 |
|---|---|---|
| Relation Observation | collector가 본 사실과 최종 relation을 혼동 | telemetry의 관측 단서만 저장하고 relation을 확정하지 않음 |
| Abduction | 가능한 관계 후보가 필요 | 관측 endpoint와 ontology type constraint 안에서 relation hypothesis 생성 |
| DeBERTa | abductive candidate의 의미적 오탐 | telemetry premise가 relation claim을 실제로 지지하는지 contrastive NLI로 평가 |
| PSL | 개별 후보는 plausible하지만 전체 그래프에서 충돌 가능 | semantic/prior/ontology/global consistency를 soft logic으로 결합 |
| Structural Recovery | 불완전 운영지식 | 검증된 `(source, relation, target)`을 Operational Graph에 반영 |
| Causal Qualification | structural relation ≠ incident cause | 이번 incident에서 실제 전파된 관계만 causal/non-causal 판정 |
| LLM RCA | 그래프 결과를 운영 판단으로 변환 | root cause, propagation path, 영향, 조치 생성 |

### 후보 폭발 방지 원칙

본 연구는 모든 `Node × Node` 조합을 만들지 않는다.

```text
금지
all nodes × all nodes
        ↓
unconstrained relation hypothesis explosion

사용
telemetry-grounded endpoint observations
        +
ontology type constraints
        ↓
bounded relation hypothesis space
```

현재 구현의 `AbductiveStructuralRelationGenerator`는 **RelationObservation에 존재하는 endpoint pair만 후보화**하며, type-compatible relation만 허용한다. 관측 근거가 전혀 없는 두 독립 객체 사이의 관계는 임의로 발명하지 않고 unknown으로 남긴다.

---

## 4. Stage 1의 수식화

초기 운영 그래프를

\[
G_0=(V,E_0)
\]

라고 하고 structural relation vocabulary를

\[
\mathcal R=\{CALLS,DEPLOYED\_ON,RUNS\_ON,USES\_DATABASE,\ldots\}
\]

로 둔다.

Telemetry에서 relation observation 집합

\[
O=\{o_1,\ldots,o_m\}
\]

을 얻는다. Abduction은 관측 endpoint와 ontology constraint \(K\)를 만족하는 후보를 생성한다.

\[
\mathcal H(O,K)=
\{(u,r,v)\mid grounded(u,v,O)\land compatible(u,r,v,K)\}
\]

모든 node pair가 아니라 `grounded`된 endpoint만 사용한다.

각 후보 \(h\)의 abductive prior를 \(A(h)\), DeBERTa semantic support와 contradiction을 \(S(h),C(h)\)라 둔다. Semantic margin은

\[
M(h)=S(h)-C(h)
\]

로 정의한다.

PSL은 후보별 soft truth value \(y_h\in[0,1]\)에 대해 ontology/global rule violation을 최소화한다.

\[
y^*=\arg\min_y\sum_k w_k[\max(0,\ell_k(y))]^{p_k}
\]

최종 structural graph는

\[
\hat E_S=E_0\cup\{h\in\mathcal H\mid y_h^*\ge\tau_r\}
\]

이다.

핵심은 **Abduction이 후보를 만들고, DeBERTa와 PSL이 그 후보를 검증·선별한다는 역할 분리**다.

---

## 5. Structural Relation과 Causal Relation은 다르다

`CALLS`의 자연 방향과 장애 전파 방향도 구분한다.

```text
caller --CALLS--> callee

potential synchronous propagation candidate
callee --dependency_propagates_to--> caller
```

현재 OpenRCA service-level Stage 2에서는 `CALLS`만 propagation candidate로 projection하며, DB/Pod/Node 같은 heterogeneous structural relation을 임의로 service-service causal edge로 축약하지 않는다.

또한 connectivity 자체는 causal evidence에 가산하지 않는다.

---

## 6. OpenRCA 2.0과 연구 필요성

OpenRCA 2.0은 dependency graph를 diagnosing agent에게 직접 제공하지 않고 traces, metrics, logs를 이용해 structure, root cause, causal process를 추론하도록 한다. 따라서 본 연구의 incomplete-structure 문제와 잘 맞는다.

OpenRCA 2.0 v2의 11개 frontier LLM 평균은 다음과 같다.

| 문제 | 결과 | 의미 |
|---|---:|---|
| 최종 진단 | Outcome F1 **34.1%**, EM **20.7%** | root cause set 복원이 여전히 어려움 |
| Ungrounded diagnosis | AnySvc **76.0%** vs PR **61.5%** | root service를 찾고도 검증 가능한 path를 만들지 못하는 경우가 존재 |
| Relation reasoning 병목 | Node F1 **62.2%** vs Edge F1 **43.4%** | component 발견보다 directed relation/process 복원이 더 어려움 |

최고 Outcome F1도 Gemini 3.1 Pro **43.8%**, Claude Opus 4.7 **41.4%** 수준이다.

본 연구는 OpenRCA의 결함을 주장하는 것이 아니다. OpenRCA 2.0의 process supervision이 드러낸 **relation/path reasoning 병목을 더 세분화**한다.

```text
Component discovery
       ↓
Structural Relation Recovery
       ↓
Incident Causal Qualification
       ↓
Causal Process Reconstruction
       ↓
RCA
```

### Benchmark 범위 주의

PAVE `causal_graph.json`은 incident-specific causal process 정답이지 `CALLS / DEPLOYED_ON / RUNS_ON / USES_DATABASE`의 완전한 persistent ontology gold가 아니다.

따라서:

- `causal_graph.json`, injection label, gold root는 Stage 1에서 사용하지 않는다.
- Stage 1은 model-visible telemetry만 사용한다.
- OpenRCA로 enterprise CMDB 전체를 자동 복원했다고 주장하지 않는다.
- DB/messaging relation은 실제 telemetry attribute가 확인된 case에만 생성한다.

2026-08-26의 실제 20-case telemetry smoke에서는 **CALLS, DEPLOYED_ON, RUNS_ON**이 관찰되었다. `USES_DATABASE`, `USES_MESSAGING`은 해당 20-case에서는 확인되지 않았으므로 전체 500-case attribute audit 전에는 coverage를 주장하지 않는다.

---

## 7. 실험 설계

### Track S — Structural Relation Recovery

논문의 중심 실험이다.

Main question:

> 불완전한 operational observations에서 relation을 얼마나 복원할 수 있는가?

평가:

- Structural typed-triple Precision / Recall / F1
- relation type coverage
- observation coverage
- candidate count / selected relation count

**중요:** `service → database` endpoint를 그대로 주고 predicate 이름만 가리면 `USES_DATABASE`가 사실상 노출될 수 있다. 따라서 `mask_structural_relation_types()`는 unit/stress diagnostic일 뿐 main 논문 결과로 사용하지 않는다.

Main Stage-S는 다음 중 하나로 검증한다.

1. 독립 telemetry window / architecture topology reference와 complete triple 비교
2. full-observation reference를 만든 뒤 relation evidence를 통제적으로 누락시키는 evidence-missingness experiment

### Stage-S Ablation

```text
S-A0 Observation + Abduction
S-A1 Observation + Abduction + DeBERTa
S-A2 Observation + Abduction + PSL
S-A3 Observation + Abduction + DeBERTa + PSL
```

### Track C — Controlled Incident Causal Qualification

기존 20/40/60% 실험은 유지하되 의미를 명확히 한다.

```text
Observed service pair 보존
causal_propagates_to / non_causal_dependency만 mask
```

```text
A0 Graph/visible causal facts
A1 Abduction
A2 Abduction + DeBERTa
A3 Abduction + PSL
A4 Abduction + DeBERTa + PSL
A5 A4 + constrained LLM adjudication
```

이 결과는 **Stage 2 causal qualification**이며 Stage 1 structural relation recovery 성능이 아니다.

### Track O — OpenRCA Standard End-to-End

최종적으로 세 조건을 비교한다.

```text
Incomplete Structure → RCA
Recovered Structure  → RCA
Reference/Oracle Structure → RCA
```

핵심 downstream 효과는

\[
\Delta RCA = Metric(RCA_{Recovered})-Metric(RCA_{Incomplete})
\]

이다.

즉 relation F1만 높이는 것이 아니라 **복원된 relation이 Edge F1, Path Reachability, Root outcome을 실제로 개선하는지**가 최종 주장이다.

---

## 8. 현재 Stage 2 결과

### 20-case / 40% causal-relation mask

| Variant | Causal Rel F1 | Node F1 | Edge F1 | Path Reach | Root@1 | Root@3 |
|---|---:|---:|---:|---:|---:|---:|
| A0 | 0.00% | 78.86% | 72.83% | 20% | 10% | 25% |
| A1 | 29.67% | 69.02% | 61.76% | 30% | 15% | 30% |
| A2 | 37.17% | 75.68% | 67.43% | 35% | 20% | 40% |
| A3 | 37.17% | 75.68% | 67.43% | 35% | 20% | 40% |
| A4 | 37.17% | 75.68% | 67.43% | **40%** | 15% | **45%** |

A1→A2에서 semantic discrimination의 이득이 관찰되었고, A4는 thresholded relation F1은 동일하지만 Path Reachability와 Root@3를 개선했다.

### Standard 150-case intermediate

| Metric | Result |
|---|---:|
| AnySvc | 60.00% |
| Path Reachability | 57.33% |
| Node F1 | 52.94% |
| Edge F1 | 38.11% |
| Edge Precision | 28.87% |
| Edge Recall | 80.26% |

Stage 2에서는 Recall보다 Precision이 크게 낮아 현재 병목은 candidate enumeration보다 **false-positive causal relation pruning**에 가깝다.

500-case final 수치는 완료 결과를 확인하기 전에는 추정하여 기록하지 않는다.

---

## 9. 코드 구조와 연구-코드 정합성

```text
src/openrca_mr/
  models.py
    RelationObservation
    StructuralHypothesis
    Hypothesis                 # Stage 2 causal

  structural.py
    collect_structural_observations
    AbductiveStructuralRelationGenerator
    StructuralRelationRecovery
    recover_structural_relations
    propagation_service_edges

  semantic.py
    DebertaStructuralRelationScorer   # Stage 1
    DebertaEvidenceScorer             # Stage 2

  psl.py
    PslStructuralInference            # Stage 1
    PslGlobalInference                # Stage 2

  abduction.py                 # Stage 2 causal hypotheses
  masking.py                   # Stage 2 causal mask + diagnostic masks
  pipeline.py                  # Stage 2 RCA/path/root ranking
  openrca2.py                  # normalized IO
```

### 강제하는 불변조건

1. RelationObservation에는 gold relation label을 저장하지 않는다.
2. Stage 1은 PAVE causal graph/root/injection gold를 읽지 않는다.
3. Abduction은 global Cartesian `Node × Node`를 생성하지 않는다.
4. ontology type-compatible candidate만 허용한다.
5. generic/weak co-observation만으로 relation을 자동 확정하지 않는다.
6. Structural Relation과 Incident Causal Relation을 별도 자료구조/단계로 취급한다.
7. `CALLS` natural direction과 Stage-2 propagation direction을 명시적으로 구분한다.
8. 기존 normalized JSONL과 `RcaCase` positional constructor를 backward compatible하게 유지한다.
9. Stage-2 causal masking은 Stage-1 observations/relations를 보존한다.
10. LLM constrained adjudication은 관측되지 않은 endpoint pair를 새로 발명하지 않는다.

---

## 10. 검증 상태

- Stage-1 observation / abduction / semantic / soft-logic 경계에 대한 regression test 추가
- legacy JSONL / positional constructor / Stage-2 masking backward compatibility test 유지
- 최신 unit regression: **28 tests passed**
- Stage-1 실제 `pslpython` synthetic inference를 GitHub Actions smoke로 별도 검증
- OpenRCA 20-case real telemetry adapter smoke는 `[ops-lite-20]` gated workflow에서 재검증

---

## 11. 최종 논문 검증 순서

```text
S0  Telemetry relation-observation coverage audit
S1  Structural relation recovery A0-A3
S2  Evidence missingness / independent-reference evaluation
C1  Reference/observed structure → Stage-2 causal qualification
C2  Recovered structure → Stage-2 causal qualification
O1  Incomplete vs Recovered vs Oracle structure의 OpenRCA end-to-end 비교
```

최종 핵심 주장은 다음 하나로 제한한다.

> **수작업으로 완성하기 어려운 운영 ontology에서 telemetry-grounded abduction으로 structural relation 후보를 만들고 DeBERTa와 PSL로 후보를 검증·선별하면, 불완전한 operational graph를 보강할 수 있으며 그 보강이 causal-process RCA의 관계·경로 성능 개선으로 이어지는가?**

OpenRCA 2.0 원문: https://arxiv.org/html/2606.27154v2

이전 MAGIC, WN18RR, WebQSP, Rashomon Worlds, Tableau, BADP 기반 탐색 과정은 [`studycase.md`](studycase.md)에 보존한다.
