# OpenRCA Structural-to-Causal Relation Recovery

## 연구 목표

본 연구는 완전한 CMDB/온톨로지를 가정하지 않는다. 실제 운영 telemetry에서 먼저 **현실적인 구조 관계(Structural Relation)** 를 관찰·복원하고, 그 위에서 장애 시점별 **인과 관계(Incident Causal Relation)** 를 판정하여 Root Cause → Symptom 경로를 재구성한다.

핵심 문제는 두 관계를 분리하는 것이다.

```text
Structural relation != Incident causal relation

frontend --CALLS--> order-service
order-service --USES_DATABASE--> postgres
order-service --DEPLOYED_ON--> order-pod
order-pod --RUNS_ON--> node-3

                    + incident telemetry
                              |
                              v
postgres --causal_propagates_to--> order-service --> frontend
```

기존 코드의 `relation masking`은 위의 `CALLS / USES_DATABASE / DEPLOYED_ON`을 가리는 실험이 아니라, 이미 관찰된 service pair의 `causal_propagates_to / non_causal_dependency`를 가리는 **Stage-2 causal-relation masking**이었다. 이 저장소는 두 의미가 섞이지 않도록 구조를 분리한다.

---

## 1. 두 개의 그래프

### Stage 1 — Operational Structural Graph `G_struct`

운영 구조 자체를 표현한다.

| Relation | 의미 | OpenRCA 2.0에서 사용하는 관측원 |
|---|---|---|
| `CALLS` | caller service → callee service | trace `parent_span_id → span_id` |
| `DEPLOYED_ON` | service → pod | `service_name`, `attr.k8s.pod.name` |
| `RUNS_ON` | pod → node | pod/node resource attributes가 있을 때만 |
| `USES_DATABASE` | service → DB | `db.system`, server/db attributes가 있을 때만 |
| `USES_MESSAGING` | service → broker/topic | messaging attributes가 있을 때만 |
| `HAS_SERVICE` | system → service | 시스템 inventory/manifest가 명시적으로 있을 때만 |

**원칙:** telemetry에 없는 relation을 만들지 않는다. 특히 `USES_DATABASE`, `RUNS_ON`, `USES_MESSAGING`은 해당 attribute가 실제 parquet에 존재하는 case에서만 생성한다.

### Stage 2 — Incident Causal Graph `G_causal(i)`

특정 incident에서 어느 구조 관계를 따라 이상이 실제로 전파되었는지 표현한다.

```text
causal_propagates_to
non_causal_dependency
```

구조적으로 연결되어 있다는 사실은 causal evidence가 아니다.

---

## 2. 방향도 분리한다

운영 relation과 장애 전파 방향은 같지 않을 수 있다.

```text
Structural topology
frontend --CALLS--> order

Potential failure propagation
order --dependency_propagates_to--> frontend
```

OpenTelemetry의 parent span은 caller, child span은 callee로 해석한다. 따라서 `CALLS`는 **caller → callee**로 저장하고, 현재 service-level RCA의 propagation candidate는 **callee → caller**로 명시적으로 reverse projection한다.

이 분리는 기존 코드가 `child_service -> parent_service`를 바로 `dependency_propagates_to`로 저장하면서 relation 의미가 모호했던 문제를 해결한다.

---

## 3. 전체 파이프라인

```text
OpenRCA 2.0 normal + abnormal telemetry
                 |
                 v
      Structural Relation Induction
      CALLS / DEPLOYED_ON / RUNS_ON
      USES_DATABASE / USES_MESSAGING
                 |
                 v
       Incomplete G_struct
                 |
       propagation candidates
                 v
       Abductive Hypothesis Generation
                 |
                 v
       DeBERTa Semantic Evidence Score
                 |
                 v
            PSL Inference
                 |
                 v
       Incident Causal Qualification
                 |
                 v
        A5 LLM Adjudication (optional)
                 |
                 v
        Root Cause + Causal Path
```

### 구성요소 역할

- **Structural extractor**: trace/resource attributes에서 관찰 가능한 typed operational relation을 생성한다.
- **Abduction**: 구조적으로/telemetry상 가능한 observed pair 중 이번 incident의 causal propagation 후보를 만든다. 모든 node pair를 조합하지 않는다.
- **DeBERTa**: 정상/비정상 telemetry가 causal claim과 non-causal claim 중 어느 쪽을 더 지지하는지 contrastive NLI로 점수화한다.
- **PSL**: temporal precedence, anomaly evidence, semantic score, path coherence를 soft logic으로 결합한다.
- **A5 LLM**: A4가 생성한 observed pair만 최종 adjudication한다. 새 endpoint를 발명할 수 없다.
- **Rashomon principle**: 초기 단계에서 하나의 설명으로 조기 확정하지 않고 근접 후보를 보존하는 원칙으로만 사용한다.

---

## 4. OpenRCA 2.0과의 관계

OpenRCA 2.0의 diagnosing agent는 dependency graph를 직접 받지 않고 traces/metrics/logs만 본다. 따라서 agent가 telemetry에서 dependency structure를 추론해야 한다.

### OpenRCA 2.0이 드러낸 기존 LLM RCA의 핵심 한계

OpenRCA 2.0은 이 한계를 만든 benchmark라기보다, **Outcome-only 평가로 보이지 않던 한계를 process-level 평가로 드러낸 benchmark**이다. 논문 v2의 11개 frontier LLM 평균을 요약하면 다음과 같다.

| 문제 | OpenRCA 2.0 결과 | 해석 |
|---|---:|---|
| 낮은 최종 진단 정확도 | Outcome F1 **34.1%**, EM **20.7%** | root service와 fault kind를 함께 정확히 맞히는 것은 여전히 어려움 |
| Ungrounded diagnosis | AnySvc **76.0%** vs Path Reachability **61.5%** | 맞는 root service를 언급해도 전체 case의 **14.5%p**는 검증 가능한 causal path가 없음 |
| 관계 추론 취약 | Node F1 **62.2%** vs Edge F1 **43.4%** | 관련 component를 찾는 것보다 방향 있는 causal dependency를 연결하는 능력이 **18.8%p** 낮음 |

최고 Outcome F1도 Gemini 3.1 Pro **43.8%**, Claude Opus 4.7 **41.4%** 수준이다. 즉 강한 LLM을 사용해도 **정답 component 발견 → 관계 방향 판정 → causal path 구성** 사이에 큰 성능 손실이 남는다.

이 결과가 본 연구와 직접 연결되는 지점은 다음과 같다.

```text
Current LLM RCA weakness
  component discovery > relation reasoning
                      ↓
본 연구
  Structural Relation Recovery
            +
  Incident Causal Qualification
            ↓
  evidence-grounded causal path
```

### OpenRCA 2.0 benchmark의 범위와 본 연구의 추가 문제

OpenRCA 2.0의 주목적은 **incident-specific causal process 평가**이며, 완전한 enterprise operational ontology 복원을 평가하는 benchmark는 아니다.

- agent에 topology를 주지 않는 것은 의도된 설계이며, relation은 trace에서 추론해야 한다.
- primary process metric은 service-level Node/Edge/Path 평가이다.
- PAVE `causal_graph`는 특정 incident의 verified causal propagation graph이지 지속적인 CMDB/operational ontology 자체가 아니다.
- `CALLS`, `DEPLOYED_ON`, `RUNS_ON`, `USES_DATABASE`, `USES_MESSAGING` 같은 typed structural relation recovery를 독립적인 Stage로 분리해 점수화하지 않는다.

따라서 본 연구는 OpenRCA 2.0을 대체하기보다 그 앞단을 확장한다.

1. **Structural Relation Recovery** — 시스템이 현실적으로 어떻게 연결되어 있는가?
2. **Incident Causal Qualification** — 그 연결 중 이번 장애를 실제로 전달한 관계는 무엇인가?

OpenRCA의 PAVE causal graph는 Stage 2의 evaluator에만 사용한다. Stage 1 structural extractor는 `causal_graph.json`, injection label, gold root를 읽지 않는다.

### OpenRCA entity 범위 주의

OpenRCA 2.0은 enterprise CMDB 전체를 제공하는 데이터셋이 아니다. service/pod/node/span 중심이며, DB·message broker는 telemetry attribute가 노출되는 범위에서만 relation화한다. 따라서 본 연구가 `HAS_APPLICATION`, `USES_DATABASE` 등 모든 enterprise ontology relation을 OpenRCA가 gold annotation으로 제공한다고 주장하지 않는다.

근거: OpenRCA 2.0 v2, Table 2 및 Section 3.2 / Appendix G — https://arxiv.org/html/2606.27154v2

---

## 5. 실험 트랙

### Track S — Structural Relation Audit / Recovery

새 normalized artifact에는 `structural_relations`가 별도로 저장된다.

먼저 데이터가 실제로 어떤 typed relation을 얼마나 노출하는지 audit한다.

```bash
python scripts/build_ops_lite_cases_fast.py \
  --start-index 0 --end-index 50 \
  --out artifacts/ops_lite_structural.jsonl

python scripts/audit_structural_relations.py \
  --data artifacts/ops_lite_structural.jsonl \
  --out results/structural_relation_audit.json
```

`mask_structural_relation_types()`는 코드 경계와 unit/stress test를 위한 보조 도구로만 둔다. `service→database`처럼 endpoint type이 relation type을 사실상 노출할 수 있으므로, **단순 structural label masking을 논문의 main Structural-Recovery 성능으로 사용하지 않는다.** Main Track S는 독립 telemetry window 또는 별도 topology reference와의 typed-triple 비교로 검증한다.

### Track C — Controlled Incident-Causal Relation Masking

현재 진행 중인 500-case 실험은 이 트랙이다.

```text
Observed service pair는 보존
causal_propagates_to / non_causal_dependency 의미만 20/40/60% mask
```

Ablation:

```text
A0  Graph / visible causal facts only
A1  Abduction
A2  Abduction + DeBERTa
A3  Abduction + PSL
A4  Abduction + DeBERTa + PSL
A5  A4 + final LLM adjudication
```

이 트랙은 **Structural Relation Recovery 성능이 아니라 Stage-2 causal qualification 성능**을 측정한다.

### Track O — OpenRCA 2.0 Standard

공식 조건에서는 topology/gold causal graph를 model input으로 주지 않는다. 구조 관계와 causal process 모두 telemetry에서 추론한다.

주요 지표:

- Root outcome: AnySvc, Root-service Precision/Recall/F1, Root@1/Root@3
- Process: Node-F1, Edge-F1, Path Reachability
- Controlled Stage C: Causal Relation Precision/Recall/F1
- Structural Track S: exact typed relation Precision/Recall/F1 및 relation-type coverage

`Root-service F1`은 repository의 service-only 보조 지표이며 OpenRCA 공식 `(service, fault_kind)` F1과 동일 지표라고 부르지 않는다.

---

## 6. 현재까지의 결과 해석

### Stage C 개발용 20-case, 40% causal-relation mask

| Variant | Causal Rel F1 | Node F1 | Edge F1 | Path Reach | Root@3 |
|---|---:|---:|---:|---:|---:|
| A0 | 0.00% | 78.86% | 72.83% | 20% | 25% |
| A1 | 29.67% | 69.02% | 61.76% | 30% | 30% |
| A2 | 37.17% | 75.68% | 67.43% | 35% | 40% |
| A3 | 37.17% | 75.68% | 67.43% | 35% | 40% |
| A4 | 37.17% | 75.68% | 67.43% | **40%** | **45%** |

이 결과는 **typed structural relation 복원 결과가 아니다.** observed pair의 incident causal/non-causal 판정 결과다.

A4는 A2/A3 대비 Causal Relation F1 자체는 오르지 않았지만 Path Reachability와 Root@3가 개선됐다. 즉 local relation classification과 global causal-process reconstruction은 분리해서 평가해야 한다.

### Standard 150/500 중간 결과

A4는 AnySvc 60.00%, Path Reachability 57.33%, Node-F1 52.94%, Edge-F1 38.11%였다. Edge Recall 80.26%에 비해 Precision 28.87%가 낮아 현재 Stage-2 병목은 candidate 수보다 **false-positive causal edge pruning**에 가깝다.

이 값은 아직 500-case 최종 결과가 아니다.

---

## 7. 코드 구조

```text
src/openrca_mr/
  models.py       # structural + causal relation vocabulary
  structural.py   # typed telemetry relation extraction / masking / projection
  masking.py      # Stage-2 causal masking + legacy edge masking
  abduction.py    # incident causal hypotheses
  semantic.py     # DeBERTa contrastive scorer
  psl.py          # soft global inference
  pipeline.py     # causal path + root ranking
  openrca2.py     # backward-compatible normalized IO

scripts/
  build_ops_lite_cases.py
  build_ops_lite_cases_fast.py
  audit_structural_relations.py
  run_openrca2_ablation.py
  run_openrca2_llm_adjudication.py
```

Backward compatibility:

- 기존 normalized JSONL에 `structural_relations`가 없어도 로드된다.
- 기존 `mask_relation_types()`는 Stage-2 causal mask 의미로 유지한다.
- 새 코드에서는 혼동을 줄이기 위해 `mask_causal_relation_types` alias와 `mask_structural_relation_types()`를 구분한다.
- 기존 Stage-2 service pair 방향과 평가 결과를 깨지 않도록 CALLS → propagation projection을 명시적으로 reverse한다.

---

## 8. 최종 연구 검증 순서

최종 논문에서는 다음 순서로 결과를 보고한다.

```text
S0  Structural telemetry coverage audit
S1  Structural relation recovery vs independent telemetry/topology reference
C1  Oracle/observed structure → causal qualification A0-A5
C2  Recovered structure → causal qualification A0-A5
O1  OpenRCA Standard end-to-end RCA
```

핵심 비교는 `Oracle/observed structure`와 `Recovered structure`의 최종 RCA 차이다. 이 비교가 있어야 “structural relation recovery가 실제 RCA 성능 향상에 기여했다”는 주장을 직접 검증할 수 있다.

이전 MAGIC, WN18RR, WebQSP, Rashomon Worlds, Tableau, BADP 기반 연구 과정은 [`studycase.md`](studycase.md)에 보존한다.
