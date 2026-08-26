# 불완전한 운영 관측에서의 귀추적 구조 관계 복원과 인과 기반 RCA

**Abductive Structural Relation Recovery and Causal RCA under Incomplete Operational Observations**

> 작성 기준: 2026-08-26  
> 대상 benchmark: OpenRCA 2.0 / `anon-ops/ops-lite` 500 cases  
> 연구 중심: **Structural Relation Recovery → Incident Causal Qualification → LLM RCA**  
> 현재 20/40/60% controlled relation-mask 실험은 Stage 2 causal qualification 실험이며 Stage 1 structural recovery 성능으로 해석하지 않는다.

---

## 초록

실제 IT 운영환경에서 Root Cause Analysis(RCA)를 수행하려면 서비스 호출, 배포 위치, 데이터베이스 사용, 호스트 배치와 같은 구조적 관계가 필요하다. 그러나 CMDB, topology, ontology와 business logic을 운영자가 지속적으로 완전하게 수작업 정의하는 것은 어렵다. APM·trace·metric·log 수집기를 통해 Service, Pod, Node, Database 등의 객체는 발견되더라도 객체 사이의 관계가 누락되거나 의미가 불명확한 상태가 남을 수 있다. 이러한 상황에서 모든 node pair를 무차별적으로 연결하면 관계 가설 공간이 조합적으로 증가하고 false positive가 확대된다.

본 연구는 이 문제를 단순한 missing-edge prediction이 아니라 **불완전한 운영 관측으로부터 typed structural relation triple을 복원하는 문제**로 정의한다. Stage 1에서는 model-visible telemetry를 `RelationObservation`으로 변환하되 관계를 즉시 확정하지 않는다. 이후 Abductive Hypothesis Generation이 관측된 endpoint와 ontology type constraint에 근거하여 가능한 `(source, relation, target)` 후보를 생성하고, DeBERTa 기반 contrastive Natural Language Inference(NLI)가 telemetry evidence의 semantic support와 contradiction을 평가하며, Probabilistic Soft Logic(PSL)이 후보 간 경쟁, ontology consistency 및 sparsity를 고려해 최종 Structural Relation을 선별한다. Stage 2에서는 복원된 structural graph를 incident causal reasoning의 후보 공간으로 사용하여 특정 장애에서 실제 propagation에 참여한 관계와 그렇지 않은 관계를 구분한다. 최종 LLM은 검증된 구조·인과 그래프와 telemetry evidence를 기반으로 root cause, propagation path, impact 및 action을 생성한다.

OpenRCA 2.0은 본 문제의 필요성을 정량적으로 보여준다. 11개 frontier LLM의 평균 Outcome F1은 34.1%, Exact Match는 20.7%이고, AnySvc는 76.0%인 반면 Path Reachability는 61.5%이다. 또한 Node F1 62.2%에 비해 Edge F1은 43.4%로 18.8%p 낮다 [1]. 이는 관련 component를 발견하는 능력과 방향 있는 relation 및 causal process를 구성하는 능력 사이에 명확한 간극이 있음을 보여준다. 본 연구는 이 간극을 **Structural Relation Recovery 오류**, **Incident Causal Qualification 오류**, **Root/Path Reconstruction 오류**로 분해하여 분석한다.

현재 OpenRCA 20-case telemetry smoke에서는 `CALLS`, `DEPLOYED_ON`, `RUNS_ON` relation을 실제 model-visible telemetry에서 관찰할 수 있음을 확인하였다. `USES_DATABASE`, `USES_MESSAGING`은 해당 20-case에서는 확인되지 않았으므로 전체 500-case attribute audit 이전에는 coverage를 주장하지 않는다. 기존 Stage 2 20-case controlled experiment에서는 Abduction Relation F1 29.67%에서 DeBERTa 결합 시 37.17%로 향상되었고, Full model은 Path Reachability 40%, Root@3 45%를 기록하였다. 이 수치는 Structural Relation Recovery 결과가 아니라 incident causal qualification의 개발용 중간 결과다.

본 연구의 최종 검증 목표는 단순 structural relation F1 향상에 그치지 않는다. Incomplete, Recovered, Reference/Oracle structural graph 조건에서 OpenRCA causal-process 및 root-cause 성능을 비교하여, **복원된 structural relation이 실제 RCA 성능 개선으로 이어지는가**를 검증한다.

**주요어:** Root Cause Analysis, OpenRCA 2.0, Operational Ontology, Structural Relation Recovery, Abductive Reasoning, DeBERTa, Probabilistic Soft Logic, Causal Process Reconstruction

---

# 1. 서론

## 1.1 연구 배경

운영자가 시스템 장애를 분석하기 위해 필요한 지식은 단순한 객체 목록이 아니다. 실제 RCA에는 다음과 같은 관계가 필요하다.

```text
System      --HAS_SERVICE-->    Service
Service     --CALLS-->          Service
Service     --DEPLOYED_ON-->    Pod
Pod         --RUNS_ON-->        Node
Service     --USES_DATABASE-->  Database
Service     --USES_MESSAGING--> MessagingSystem
```

그러나 현실의 CMDB와 ontology는 완전하지 않다. 신규 deployment, autoscaling, 동적 service discovery, 외부 data source, runtime API call과 같은 변화가 정적 자산정보에 즉시 반영되지 않을 수 있다. business logic을 담당자에게 모두 수작업으로 입력받는 것 역시 지속 가능한 방법이 아니다.

반면 observability collector는 runtime에서 다양한 객체와 단서를 수집한다. 예를 들어 distributed trace에서는 `trace_id`, `span_id`, `parent_span_id`, `service_name`이 관찰되고, resource attribute에서는 Kubernetes Pod/Node가 관찰될 수 있다. DB 및 messaging attribute가 노출될 경우 database 또는 broker에 관한 단서도 얻을 수 있다. 하지만 **collector가 객체를 관찰했다는 사실과 객체 사이의 operational relation을 확정했다는 사실은 동일하지 않다.**

따라서 본 연구는 다음의 현실적 문제를 다룬다.

> **객체는 관찰되지만 CMDB/ontology에 structural relation이 없거나 불완전할 때, telemetry evidence를 이용하여 가능한 relation을 생성하고 검증할 수 있는가?**

## 1.2 Edge가 아니라 Relation 문제

본 연구에서 graph edge는 relation을 표현하는 자료구조일 뿐이다. 연구 대상은 다음 typed triple이다.

\[
e=(u,r,v), \qquad r\in\mathcal R
\]

예를 들어:

\[
(service{:}frontend, CALLS, service{:}orders)
\]

\[
(service{:}orders, USES\_DATABASE, database{:}orders-db)
\]

따라서 “missing edge”라는 표현은 관계가 없는 두 node를 임의로 연결하는 것으로 오해될 수 있다. 본 연구는 **relation observation에 근거한 structural relation hypothesis**만 생성한다.

또한 모든 node pair를 후보로 만들지 않는다.

\[
|V|^2\times|\mathcal R|
\]

의 무제한 후보 공간 대신 telemetry에서 endpoint 연관성이 관찰된 pair와 ontology type constraint를 이용해 후보 영역을 제한한다.

## 1.3 Structural Relation과 Incident Causal Relation의 분리

운영 구조와 사건별 인과관계는 서로 다르다.

```text
Structural topology
frontend --CALLS--> orders

Incident-specific causal propagation
orders --causal_propagates_to--> frontend
```

`frontend CALLS orders`는 평상시에도 존재하는 structural relation이지만, 모든 incident에서 `orders`가 `frontend` 장애의 원인은 아니다. 따라서 본 연구는 두 relation layer를 분리한다.

\[
G_S \neq G_C^{(i)}
\]

- \(G_S\): persistent/operational structural graph
- \(G_C^{(i)}\): incident \(i\)의 causal propagation graph

## 1.4 연구 목적

전체 연구 흐름은 다음과 같다.

```text
Incomplete CMDB / Ontology
          +
Operational Telemetry
          ↓
Relation Observation
          ↓
Abductive Structural Hypotheses
          ↓
DeBERTa Semantic Validation
          ↓
PSL Global Selection
          ↓
Recovered Structural Graph
          ↓
Incident Causal Qualification
          ↓
Causal Process Reconstruction
          ↓
LLM RCA
```

최종적으로 단순히 relation을 맞히는 것이 아니라, 복원된 relation이 RCA의 Edge F1, Path Reachability, Root outcome을 개선하는지 확인한다.

## 1.5 연구 질문

**RQ1. Abductive Structural Hypothesis Generation.** 불완전한 operational observations에서 모든 node pair를 생성하지 않고도 유효한 structural relation 후보를 구성할 수 있는가?

**RQ2. Semantic Validation.** DeBERTa 기반 contrastive semantic scoring이 Abduction-only 대비 잘못된 structural relation 후보를 줄이고 Precision/F1을 개선하는가?

**RQ3. Global Relation Selection.** PSL의 ontology/global constraint가 개별 semantic score만 사용할 때보다 relation consistency와 structural triple F1을 개선하는가?

**RQ4. Downstream Causal Effect.** Recovered structural graph를 사용했을 때 incomplete structural graph 대비 OpenRCA causal Edge F1 및 Path Reachability가 개선되는가?

**RQ5. End-to-End RCA Effect.** Recovered structural/causal graph가 최종 LLM RCA의 root-cause outcome과 설명 가능한 propagation path를 개선하는가?

## 1.6 연구 기여

본 연구의 기여는 다음과 같다.

1. RCA 이전의 **Structural Relation Recovery**와 사건별 **Incident Causal Qualification**을 명시적으로 분리한다.
2. collector output을 곧바로 relation fact로 간주하지 않고 **RelationObservation → Abduction → Validation → Selection**의 단계형 모델을 제안한다.
3. Abduction 후보를 telemetry-grounded endpoint와 ontology type constraint로 제한하여 global all-pairs relation hypothesis explosion을 방지한다.
4. DeBERTa를 structural relation support/non-support의 semantic discriminator로 사용하고 PSL을 global candidate selector로 분리한다.
5. `CALLS`의 natural direction과 failure-propagation candidate direction을 분리한다.
6. Stage 1은 PAVE causal gold를 사용하지 않아 structural recovery와 causal evaluator 사이의 leakage를 차단한다.
7. Structural relation 성능과 downstream causal-process/RCA 성능을 함께 측정하여 **relation recovery의 실질적 RCA 기여도**를 검증한다.

---

# 2. OpenRCA 2.0과 연구 공백

## 2.1 OpenRCA 2.0의 기여

OpenRCA 2.0은 outcome label만 평가하는 기존 RCA benchmark에서 확장하여 causal process 자체를 평가한다 [1]. Diagnosing agent는 dependency graph를 직접 입력받지 않고 traces, metrics, logs를 통해 dependency structure, root cause, propagation path를 추론해야 한다. 이 설정은 operational structure가 미리 완전하게 주어지지 않는 본 연구의 문제와 자연스럽게 연결된다.

## 2.2 OpenRCA 2.0이 드러낸 현재 LLM RCA의 한계

OpenRCA 2.0 v2의 11개 frontier LLM 결과는 다음과 같다.

| 한계 | 결과 | 해석 |
|---|---:|---|
| 낮은 최종 진단 정확도 | Outcome F1 **34.1%**, EM **20.7%** | service와 fault kind를 포함한 정확한 root cause 복원이 어려움 |
| Ungrounded diagnosis | AnySvc **76.0%** vs PR **61.5%** | root service를 찾더라도 검증 가능한 causal path가 없는 경우 존재 |
| Relation/process reasoning 병목 | Node F1 **62.2%** vs Edge F1 **43.4%** | 관련 component 식별보다 directed relation 복원이 **18.8%p** 낮음 |

최고 Outcome F1도 Gemini 3.1 Pro 43.8%, Claude Opus 4.7 41.4% 수준이다 [1].

AnySvc와 PR 사이의 14.5%p 차이는 “정답 service 이름을 언급하는 것”과 “그 service가 왜 원인인지 directed causal path로 설명하는 것”이 다른 문제임을 보여준다. Node F1과 Edge F1의 18.8%p 차이도 relation reasoning이 주요 병목임을 뒷받침한다.

## 2.3 OpenRCA의 범위와 본 연구의 추가 문제

본 연구는 OpenRCA 2.0을 대체하거나 benchmark의 결함을 주장하지 않는다. OpenRCA의 핵심 목표는 incident-specific causal-process supervision이다. 반면 본 연구는 그 앞단의 persistent operational structure를 별도 연구문제로 분리한다.

PAVE의 `causal_graph.json`은 특정 incident에서 검증된 causal propagation graph이며 `CALLS`, `DEPLOYED_ON`, `RUNS_ON`, `USES_DATABASE` 같은 typed operational relation의 완전한 gold ontology가 아니다.

따라서 본 연구에서는:

- PAVE causal graph는 Stage 2 evaluator로만 사용한다.
- Stage 1 RelationObservation/Abduction은 `causal_graph.json`, injection label, gold root를 읽지 않는다.
- OpenRCA가 제공하지 않는 enterprise business-function/owner/SQL ontology를 임의로 정답처럼 사용하지 않는다.
- DB/messaging relation은 실제 telemetry attribute가 존재하는 경우에만 관찰 대상으로 인정한다.

## 2.4 현재 OpenRCA telemetry 적합성

실제 20-case smoke에서 다음 structural relation source가 확인되었다.

```text
CALLS
DEPLOYED_ON
RUNS_ON
```

case별로 `CALLS` 6~17, `DEPLOYED_ON` 18~21, `RUNS_ON` 21 수준의 relation이 구성되었다. 이는 OpenRCA telemetry가 적어도 service call과 Kubernetes deployment/resource relation 연구에는 사용 가능함을 보여준다.

반면 해당 20-case에서는 `USES_DATABASE`, `USES_MESSAGING` relation이 관찰되지 않았다. 따라서 이 두 relation의 OpenRCA coverage는 전체 500-case attribute audit 결과를 확인한 후 결정한다.

---

# 3. 문제 정의 및 수식화

## 3.1 초기 불완전 운영 그래프

초기 운영 그래프를

\[
G_0=(V,E_0)
\]

라고 한다. \(V\)는 Service, Pod, Node, Database, MessagingSystem 등의 객체 집합이고, \(E_0\)는 이미 신뢰 가능한 relation 집합이다.

Structural relation vocabulary는

\[
\mathcal R=
\{CALLS,DEPLOYED\_ON,RUNS\_ON,USES\_DATABASE,USES\_MESSAGING,HAS\_SERVICE\}
\]

로 정의한다.

목표는 누락되거나 불완전한 relation 집합 \(M\)을 추론하여

\[
\hat G_S=(V,E_0\cup\hat M)
\]

을 구성하는 것이다.

## 3.2 Relation Observation

Raw telemetry \(Z\)를 직접 relation fact로 변환하지 않고 observation 집합으로 변환한다.

\[
O=f_{obs}(Z)=\{o_1,\ldots,o_m\}
\]

각 observation은

\[
o_j=(u_j,v_j,k_j,c_j,x_j)
\]

로 표현한다.

- \(u_j,v_j\): model-visible endpoint
- \(k_j\): evidence kind
- \(c_j\in[0,1]\): observation confidence
- \(x_j\): textual/contextual evidence

중요하게도 \(o_j\)에는 gold structural relation label이나 PAVE causal label이 포함되지 않는다.

현재 observation kind 예시는 다음과 같다.

```text
trace_parent_child
service_pod_cooccurrence
pod_node_cooccurrence
db_client_context
messaging_context
system_inventory
```

## 3.3 Abductive Structural Hypothesis Generation

Ontology/domain constraint를 \(K\)라고 한다. 예를 들어 relation type compatibility는 다음과 같다.

```text
(Service, Service)  → CALLS
(Service, Pod)      → DEPLOYED_ON
(Pod, Node)         → RUNS_ON
(Service, Database) → USES_DATABASE
```

후보 집합은

\[
\mathcal H(O,K)=
\{(u,r,v)\mid grounded(u,v,O)\land compatible(u,r,v,K)\}
\]

로 정의한다.

여기서 `grounded`는 두 endpoint가 RelationObservation으로 연결되어 있음을 의미한다. 따라서 모든 \(V\times V\)를 후보로 만들지 않는다.

Observation 종류별 relation prior를 \(w_{k,r}\)라고 할 때 후보 \(h\)의 abductive support를 noisy-OR 형태로 정의할 수 있다.

\[
A(h)=1-\prod_{o_j\in O_h}(1-c_jw_{k_j,r_h})
\]

이 값은 relation의 최종 정답 확률이 아니라 **관측을 설명하기 위해 해당 relation을 고려할 가치**를 나타낸다.

전통적인 abduction 관점에서는 설명 집합 \(H\)가

\[
K\cup G_0\cup H \models O
\]

를 만족하면서

\[
K\cup G_0\cup H\not\models\bot
\]

인 설명 중 낮은 비용을 갖는 것을 선호한다고 해석할 수 있다 [2].

## 3.4 DeBERTa Semantic Validation

각 structural hypothesis \(h=(u,r,v)\)에 대해 동일한 telemetry premise \(P_h\)를 사용해 두 claim을 비교한다.

```text
H+ : u has structural relation r with v.
H- : telemetry does not support relation r; u and v are only co-observed.
```

DeBERTa NLI의 entailment 값을 각각 \(e^+_h,e^-_h\)라고 한다. 두 claim 모두 entailment가 매우 낮을 때 작은 차이를 과대증폭하지 않도록 reliability를 사용한다.

\[
q_h=\min\left(1,\frac{e^+_h+e^-_h}{\gamma}\right)
\]

\[
m_h=q_h\frac{e^+_h-e^-_h}{e^+_h+e^-_h+\epsilon}
\]

그리고 semantic support를

\[
S(h)=\frac{1+m_h}{2}
\]

형태로 해석한다. 현재 구현은 \(\gamma=0.5\)인 neutral-preserving contrastive margin을 사용한다.

## 3.5 PSL Global Relation Selection

각 hypothesis \(h\)의 soft truth value를

\[
y_h\in[0,1]
\]

로 둔다. PSL은 abductive prior, semantic support/contradiction, candidate competition, sparsity 및 ontology consistency를 soft rule로 결합한다 [5].

일반적인 PSL objective는

\[
y^*=\arg\min_{y\in[0,1]^n}
\sum_k w_k[\max(0,\ell_k(y))]^{p_k}
\]

로 표현된다.

현재 Stage 1 rule의 역할은 다음과 같다.

```text
AbductivePrior(A,R,B)      -> Relation(A,R,B)
SemanticSupport(A,R,B)     -> Relation(A,R,B)
Contradiction(A,R,B)       -> !Relation(A,R,B)
CompetingCandidate(...)    -> mutual penalty
                             + sparsity prior
```

PSL 역시 새로운 endpoint를 발명하지 않는다. candidate domain은 Abduction이 생성한 \(\mathcal H\)로 고정된다.

최종 relation 집합은

\[
\hat M=\{h\in\mathcal H\mid y_h^*\ge\tau_r\}
\]

이고

\[
\hat G_S=(V,E_0\cup\hat M)
\]

를 얻는다.

## 3.6 Incident Causal Qualification

incident \(i\)에서 structural relation 또는 그 projection이 실제 장애 propagation에 참여했는지를

\[
z_e^{(i)}\in\{0,1\}
\]

로 둔다.

- \(z_e^{(i)}=1\): causal propagation 참여
- \(z_e^{(i)}=0\): 구조적으로 연결되어 있지만 이번 incident에서는 non-causal

Stage 2의 abductive prior는 현재 코드와 동일하게 temporal precedence \(T_{uv}\)와 anomaly-pair evidence \(N_{uv}\)를 이용한다.

\[
A_{uv}^{causal}=0.55T_{uv}+0.45N_{uv}
\]

Structural connectivity 자체는 causal evidence score에 더하지 않는다. connectivity는 candidate eligibility일 뿐이다.

## 3.7 Natural Direction과 Propagation Direction

Trace의 parent service를 caller, child service를 callee로 해석한다.

\[
caller\xrightarrow{CALLS}callee
\]

현재 synchronous service-level RCA에서는 downstream failure가 caller에 영향을 줄 수 있으므로 propagation candidate는 명시적으로 reverse projection한다.

\[
callee\xrightarrow{dependency\_propagates\_to?}caller
\]

이 projection은 causal truth가 아니라 Stage 2 후보 방향이다.

## 3.8 최종 RCA와 Downstream Effect

최종 RCA는 root ranking과 causal graph를 함께 출력한다.

\[
\hat R^{(i)}=[\hat r_1,\ldots,\hat r_k]
\]

그리고 LLM은 structural/causal graph와 evidence를 입력으로 root cause, path, impact, action을 생성한다.

Structural recovery의 실제 가치는 downstream difference로 측정한다.

\[
\Delta RCA_m=
Metric_m(RCA_{Recovered})-Metric_m(RCA_{Incomplete})
\]

주요 \(m\)은 Edge F1, Path Reachability, Root outcome이다.

---

# 4. 제안 방법

## 4.1 Stage 1-A: Telemetry Relation Observation

수집기에서 직접 최종 relation을 확정하지 않는다. 현재 구현의 `collect_structural_observations()`는 model-visible telemetry만 사용하여 RelationObservation을 만든다.

### Service call observation

```text
trace_id
span_id
parent_span_id
service_name
```

parent-child span join을 통해 endpoint pair와 관측 근거를 얻는다. join key는 parquet reader에 따른 type mismatch로 relation이 소실되지 않도록 string-normalization한다.

### Deployment/resource observation

```text
service_name + k8s.pod.name
k8s.pod.name + k8s.node.name / host.name
```

### Database/messaging observation

DB 또는 messaging attribute가 실제 telemetry에 존재하는 경우에만 observation을 만든다. 없는 relation을 service 이름 패턴으로 추정하여 만들지 않는다.

반복 telemetry row가 traffic volume에 의해 confidence를 과도하게 증가시키지 않도록 같은 `(source,target,evidence_kind)` observation을 deduplicate하고 occurrence count를 metadata로 보존한다.

## 4.2 Stage 1-B: Abductive Structural Candidate Generation

`AbductiveStructuralRelationGenerator`는 다음 두 제약을 강제한다.

1. endpoint pair는 RelationObservation에 grounded되어 있어야 한다.
2. relation type은 ontology schema와 compatible해야 한다.

따라서 global Cartesian all-pairs 후보를 만들지 않는다.

직접 evidence가 강한 observation은 높은 abductive prior를 갖고, generic weak co-observation은 threshold 아래의 candidate로 남도록 설계한다. 즉 “관찰됨”과 “relation으로 확정됨”을 분리한다.

## 4.3 Stage 1-C: DeBERTa Structural Semantic Scoring

`DebertaStructuralRelationScorer`는 Stage 2 causal scorer와 동일 NLI backbone을 사용하되 claim을 분리한다.

Stage 1:

```text
relation is supported
vs
relation is not supported / only co-observed
```

Stage 2:

```text
incident anomaly causally propagated
vs
observed dependency did not propagate the incident
```

따라서 같은 DeBERTa를 쓰더라도 structural semantics와 causal semantics를 혼동하지 않는다.

## 4.4 Stage 1-D: PSL Structural Selection

`PslStructuralInference`는 이미 제한된 candidate domain에서 global selection을 수행한다. PSL이 모든 node를 새로 조합하지 않는다.

주 역할은:

- abductive support 결합
- semantic support/contradiction 결합
- 동일 endpoint의 competing relation penalty
- unsupported candidate sparsity

이다.

## 4.5 Stage 2 Causal Qualification

Stage 1에서 복원된 `CALLS`는 current OpenRCA service evaluator와 호환하기 위해 propagation candidate로 projection한다. Pod/Node/Database 등의 heterogeneous structural relation은 구조 그래프에 보존하고 service-only causal edge로 임의 축약하지 않는다.

Stage 2에서는 기존 A0–A5 ablation을 유지한다.

```text
A0  Graph / visible causal facts
A1  Abduction
A2  Abduction + DeBERTa
A3  Abduction + PSL
A4  Abduction + DeBERTa + PSL
A5  A4 + constrained LLM adjudication
```

A5는 observed candidate endpoint 밖의 새로운 pair를 만들 수 없다.

## 4.6 LLM RCA

LLM의 최종 역할은 relation generator가 아니라 operational decision layer다.

```text
Input
- recovered structural graph
- incident causal graph
- anomaly/evidence summary
- root ranking

Output
- 장애현상
- Root Cause
- Propagation Path / 영향범위
- 조치방안
```

A5 constrained adjudication은 별도의 Stage 2 보조 실험으로 유지하되, 논문의 핵심 Stage 1 novelty와 동일시하지 않는다.

---

# 5. 실험 설계

## 5.1 데이터

본 연구는 `anon-ops/ops-lite` 500-case를 사용한다. 세 시스템은 Train-Ticket, Hotel Reservation, OpenTelemetry Demo로 구성된다 [1][6].

### Model-visible

- normal traces / metrics / logs
- abnormal traces / metrics / logs
- incident symptom information
- model-visible telemetry에서 생성한 RelationObservation

### Evaluator-only

- `causal_graph.json`
- root-cause gold
- injection ground truth
- PAVE causal-process label

## 5.2 Track S0 — Structural Observation Coverage Audit

먼저 OpenRCA가 실제로 어느 relation evidence를 노출하는지 측정한다.

- observation kind count/coverage
- structural candidate count
- recovered relation type count/coverage
- system별 observable relation 차이

이 결과는 데이터 가능성 audit이며 structural recovery 성능 자체로 해석하지 않는다.

## 5.3 Track S1 — Structural Relation Recovery

Stage 1의 핵심 ablation은 다음과 같다.

```text
S-A0 Observation + Abduction
S-A1 Observation + Abduction + DeBERTa
S-A2 Observation + Abduction + PSL
S-A3 Observation + Abduction + DeBERTa + PSL
```

평가 지표:

- Structural Triple Precision
- Structural Triple Recall
- Structural Triple F1
- relation-type coverage
- candidate-to-selected ratio

## 5.4 Track S2 — Evidence Missingness / Independent Reference

단순 predicate-label masking은 main experiment로 사용하지 않는다. 예를 들어 `service→database` endpoint type을 제공하면서 label만 mask하면 `USES_DATABASE`가 자명해질 수 있기 때문이다.

따라서 main Stage 1은 다음 중 하나 또는 둘 모두를 사용한다.

### Controlled Evidence Missingness

full telemetry/reference observation에서 일부 direct relation evidence를 통제적으로 누락시키고 relation recovery 성능을 측정한다.

```text
0% / 20% / 40% / 60% evidence missingness
```

### Independent Reference

공식 architecture/deployment specification 또는 독립 telemetry window에서 얻은 structural triple을 evaluator-only reference로 사용한다.

이때 reference는 Stage 1 candidate generation에 사용하지 않는다.

## 5.5 Track C — Controlled Incident Causal Qualification

기존 500-case 20/40/60% masking은 이 트랙이다.

```text
endpoint pair 유지
causal_propagates_to / non_causal_dependency 의미만 mask
```

이 실험은 Stage 1 relation recovery가 아니라 Stage 2 causal discrimination을 평가한다.

## 5.6 Track O — OpenRCA Standard End-to-End

최종 연구에서는 다음 세 조건을 비교한다.

| 조건 | 의미 |
|---|---|
| Incomplete | relation 누락을 그대로 둔 graph |
| Recovered | 제안 Stage 1으로 relation을 보강한 graph |
| Reference/Oracle | 평가 가능한 범위에서의 reference structure |

기대 검증 관계는 단순 가정이 아니라 실험으로 확인한다.

\[
Metric_{Incomplete}
\stackrel{?}{<}
Metric_{Recovered}
\stackrel{?}{\le}
Metric_{Reference}
\]

`Recovered > Incomplete`가 통계적으로/실질적으로 확인되어야 “structural relation recovery가 RCA를 개선한다”는 최종 주장을 할 수 있다.

---

# 6. 평가 지표

## 6.1 Structural Relation Recovery

\[
Precision_S=\frac{|\hat E_S\cap E_S^*|}{|\hat E_S|}
\]

\[
Recall_S=\frac{|\hat E_S\cap E_S^*|}{|E_S^*|}
\]

\[
F1_S=\frac{2Precision_SRecall_S}{Precision_S+Recall_S}
\]

여기서 triple은 `(source, relation, target)` exact match로 비교한다.

## 6.2 Incident Causal Qualification

- causal Relation Precision / Recall / F1
- relation accuracy
- predicted-positive rate
- false-positive causal retention

## 6.3 Causal Process

- Node Precision / Recall / F1
- Edge Precision / Recall / F1
- Path Reachability

## 6.4 RCA Outcome

- AnySvc
- AllSvc
- Root-service P/R/F1
- Root@1 / Root@3
- Exact root set

repository의 service-only root F1은 OpenRCA 공식 `(service, fault-kind)` Outcome F1과 동일 지표라고 주장하지 않는다.

## 6.5 Downstream Improvement

\[
\Delta EdgeF1=EdgeF1_{Recovered}-EdgeF1_{Incomplete}
\]

\[
\Delta PR=PR_{Recovered}-PR_{Incomplete}
\]

\[
\Delta Root=RootMetric_{Recovered}-RootMetric_{Incomplete}
\]

이 downstream delta가 본 연구에서 structural F1만큼 중요하다.

---

# 7. 현재까지의 실험 결과

## 7.1 Stage 1 OpenRCA Telemetry Feasibility Smoke

실제 OpenRCA 20-case telemetry에서 relation layer를 확인한 결과 다음 유형이 관찰되었다.

| Relation | 20-case 상태 |
|---|---|
| `CALLS` | 확인됨 |
| `DEPLOYED_ON` | 확인됨 |
| `RUNS_ON` | 확인됨 |
| `USES_DATABASE` | 해당 20-case에서 미확인 |
| `USES_MESSAGING` | 해당 20-case에서 미확인 |

case별 추출량은 `CALLS` 6~17, `DEPLOYED_ON` 18~21, `RUNS_ON` 21 수준이었다.

이는 **OpenRCA로 enterprise ontology 전체를 복원할 수 있다는 결과가 아니라**, 현재 Stage 1의 service/deployment/resource relation feasibility를 확인한 결과다.

Stage 1 Abduction+DeBERTa+PSL의 final structural recovery F1은 아직 독립 reference/evidence-missingness 실험을 완료하지 않았으므로 `TBD`로 둔다.

## 7.2 Stage 2 20-case Controlled Causal Relation Pilot

40% incident causal semantics masking 결과는 다음과 같다.

| Variant | Causal Rel F1 | Node F1 | Edge F1 | Path Reachability | Root@1 | Root@3 |
|---|---:|---:|---:|---:|---:|---:|
| A0 Graph-only | 0.00% | 78.86% | 72.83% | 20% | 10% | 25% |
| A1 Abduction | 29.67% | 69.02% | 61.76% | 30% | 15% | 30% |
| A2 Abduction + DeBERTa | **37.17%** | 75.68% | 67.43% | 35% | **20%** | 40% |
| A3 Abduction + PSL | **37.17%** | 75.68% | 67.43% | 35% | **20%** | 40% |
| A4 Full | **37.17%** | 75.68% | 67.43% | **40%** | 15% | **45%** |

A1→A2에서 causal Relation F1이 29.67%에서 37.17%로 증가했다. A2/A3/A4의 thresholded Relation F1은 동일하지만 A4에서 Path Reachability와 Root@3가 개선되었다. 이는 local relation classification과 global causal-process reconstruction이 동일 문제가 아님을 보여준다.

이 표는 **Structural Relation Recovery 결과가 아니다.**

## 7.3 OpenRCA Standard 150-case Intermediate

| Metric | Result |
|---|---:|
| Any Service Hit | 60.00% |
| All Service Hit | 39.33% |
| Root Service Precision | 27.89% |
| Root Service Recall | 49.67% |
| Root Service F1 | 34.18% |
| Root Exact Set | 4.67% |
| Path Reachability | 57.33% |
| Node Precision | 42.17% |
| Node Recall | 87.07% |
| Node F1 | 52.94% |
| Edge Precision | 28.87% |
| Edge Recall | 80.26% |
| Edge F1 | 38.11% |

Edge Recall에 비해 Precision이 낮다. 따라서 현재 Stage 2의 병목은 단순 candidate 부족보다 **false-positive causal relation pruning**에 가깝다.

## 7.4 500-case Final

500-case final 결과는 실제 aggregate가 완료되기 전까지 추정하지 않는다.

최종 논문에서는 최소 다음을 보고한다.

### Structural

| Missingness | S-A0 | S-A1 | S-A2 | S-A3 |
|---:|---:|---:|---:|---:|
| 20% | TBD | TBD | TBD | TBD |
| 40% | TBD | TBD | TBD | TBD |
| 60% | TBD | TBD | TBD | TBD |

### Causal / RCA

| Structure | Edge F1 | Path | AnySvc | Root@1 | Root@3 |
|---|---:|---:|---:|---:|---:|
| Incomplete | TBD | TBD | TBD | TBD | TBD |
| Recovered | TBD | TBD | TBD | TBD | TBD |
| Reference | TBD | TBD | TBD | TBD | TBD |

---

# 8. 코드-연구 정합성

현재 구현은 연구단계를 코드 수준에서 분리한다.

```text
models.py
  RelationObservation          # Stage 1 evidence
  StructuralHypothesis         # Stage 1 candidate
  Hypothesis                   # Stage 2 causal candidate

structural.py
  collect_structural_observations
  AbductiveStructuralRelationGenerator
  StructuralRelationRecovery
  recover_structural_relations
  propagation_service_edges

semantic.py
  DebertaStructuralRelationScorer
  DebertaEvidenceScorer

psl.py
  PslStructuralInference
  PslGlobalInference

masking.py
  Stage-2 causal semantic mask
  diagnostic-only structural relation-type mask
```

## 8.1 코드 불변조건

다음 조건을 regression test로 유지한다.

1. RelationObservation은 최종 relation label을 소유하지 않는다.
2. Stage 1은 causal gold/root/injection 정보를 읽지 않는다.
3. Stage-1 Abduction은 RelationObservation endpoint 밖의 global all-pairs를 생성하지 않는다.
4. ontology type-incompatible relation은 후보에서 제외한다.
5. weak generic co-observation만으로 relation fact를 자동 확정하지 않는다.
6. Structural Relation과 Incident Causal Relation은 별도 layer다.
7. Stage-2 masking 중에도 Stage-1 observations/relations는 보존된다.
8. `CALLS`의 natural direction과 failure propagation projection을 혼동하지 않는다.
9. legacy normalized JSONL은 Stage-1 필드가 없어도 load 가능하다.
10. 기존 `RcaCase` positional constructor signature를 보존한다.
11. LLM constrained adjudication은 candidate 밖의 endpoint pair를 발명할 수 없다.

현재 unit/regression suite는 **28 tests passed** 상태다. 실제 Stage-1 PSL은 dependency-free approximation과 별개로 `pslpython` synthetic smoke를 GitHub Actions에서 검증하도록 구성한다.

---

# 9. 위협 요인과 한계

## 9.1 Structural Ground Truth 제한

OpenRCA causal graph는 typed structural ontology gold가 아니다. 따라서 Stage 1의 최종 성능 주장은 독립 reference topology 또는 controlled evidence-missingness protocol이 필요하다.

## 9.2 Typed Endpoint Leakage

`service→database` pair를 제공하고 relation label만 가리는 실험은 predicate가 endpoint type으로 노출될 수 있다. 따라서 simple relation-label masking을 main Stage 1 결과로 사용하지 않는다.

## 9.3 Observation Grounding Recall Ceiling

본 연구는 all-pairs를 피하기 위해 candidate endpoint가 telemetry observation에 grounded되어야 한다. 따라서 두 객체 사이에 아무런 연관 observation도 존재하지 않으면 relation을 추론하지 않고 unknown으로 남긴다. 이 설계는 precision과 현실성을 높이는 대신 telemetry 자체가 완전히 놓친 관계에 대한 recall ceiling을 만든다.

이 한계는 의도된 trade-off이며, 향후 CMDB text, deployment manifest, code dependency, operator knowledge를 추가 observation source로 확장할 수 있다.

## 9.4 Strong Observation과 Abduction의 경계

parent-child span이나 service-pod resource attribute는 특정 relation을 강하게 암시한다. 따라서 모든 relation에서 Abduction의 난도가 동일하지 않다. 실험에서는 relation type별 성능과 evidence missingness 수준을 분리 보고해야 한다.

## 9.5 Heterogeneous Causal Evaluation

OpenRCA의 headline process metric은 주로 service-level causal graph를 평가한다. Pod/Node/Database relation을 structural graph에 보존할 수는 있지만 heterogeneous causal-process gold가 없으면 동일 수준으로 downstream causal F1을 직접 평가하기 어렵다.

## 9.6 DeBERTa Domain Shift

범용 NLI DeBERTa가 observability-specific relation language에 최적화되어 있다고 보장할 수 없다. 따라서 deterministic/abduction-only baseline과 semantic ablation을 반드시 함께 보고한다.

## 9.7 PSL Rule Sensitivity

PSL weight와 threshold 선택에 따라 precision-recall trade-off가 달라질 수 있다. full test set에서 threshold를 tuning하지 않고 개발 subset 또는 사전 고정 정책을 사용해야 한다.

## 9.8 Structural Error Propagation

Stage 1에서 중요한 relation을 놓치면 Stage 2 후보 자체가 사라질 수 있다. 반대로 Stage 1이 false relation을 많이 유지하면 Stage 2 false-positive causal path가 늘어난다. 따라서 structural metric과 downstream RCA metric을 함께 보고해야 한다.

---

# 10. 결론

본 연구가 해결하려는 문제는 단순히 “없는 graph edge를 생성하는 것”이 아니다. 실제 운영환경에서는 Service, Pod, Node, Database 등의 객체가 관찰되어도 CMDB·ontology·business logic에 이들의 관계가 완전하게 정의되어 있지 않을 수 있다. 본 연구는 이 상태를 **Incomplete Operational Relation Problem**으로 정의한다.

이를 해결하기 위해 collector evidence를 바로 relation fact로 만들지 않고 다음의 단계형 구조를 사용한다.

\[
\boxed{
Telemetry
\rightarrow Relation\ Observation
\rightarrow Abductive\ Hypotheses
\rightarrow DeBERTa\ Validation
\rightarrow PSL\ Selection
\rightarrow Recovered\ Structural\ Graph
}
\]

그 다음 별도 단계에서

\[
\boxed{
Recovered\ Structure
\rightarrow Incident\ Causal\ Qualification
\rightarrow Causal\ Process
\rightarrow LLM\ RCA
}
\]

를 수행한다.

OpenRCA 2.0에서 Node F1 62.2%와 Edge F1 43.4%, AnySvc 76.0%와 Path Reachability 61.5%의 차이는 component discovery만으로 신뢰 가능한 RCA가 완성되지 않음을 보여준다 [1]. 본 연구의 핵심 가설은 **운영 관계를 먼저 복원하고 그 위에서 causal relation을 판정하면 이러한 relation/path reasoning 병목을 줄일 수 있다**는 것이다.

최종 논문의 성공 조건은 `Structural F1` 하나가 아니다. 다음 두 조건을 동시에 만족해야 한다.

1. Abduction + DeBERTa + PSL이 incomplete observations에서 structural triple을 의미 있게 복원한다.
2. Recovered graph를 사용한 RCA가 Incomplete graph 대비 causal Edge F1, Path Reachability 또는 Root outcome을 실질적으로 개선한다.

이 두 단계가 확인될 때 본 연구는 “불완전한 운영 ontology를 telemetry로 보강하고, 그 보강이 설명 가능한 RCA 성능으로 연결된다”는 현실적이고 검증 가능한 주장을 갖게 된다.

---

# 참고문헌

[1] A. Fang, Y. Yang, J. Shang, Q. Lu, J. Xu, R. Wang, S. Zhang, Y. Zhang, B. Yu, and P. He, **OpenRCA 2.0: From Outcome Labels to Causal Process Supervision**, arXiv:2606.27154v2, 2026. https://arxiv.org/html/2606.27154v2

[2] J. R. Hobbs, M. E. Stickel, D. E. Appelt, and P. Martin, **Interpretation as Abduction**, Artificial Intelligence, vol. 63, no. 1–2, pp. 69–142, 1993. doi:10.1016/0004-3702(93)90015-4.

[3] J. Bai, Y. Wang, T. Zheng, Y. Guo, X. Liu, and Y. Song, **Advancing Abductive Reasoning in Knowledge Graphs through Complex Logical Hypothesis Generation**, Proceedings of ACL 2024, pp. 1312–1329, 2024. doi:10.18653/v1/2024.acl-long.72.

[4] P. He, X. Liu, J. Gao, and W. Chen, **DeBERTa: Decoding-enhanced BERT with Disentangled Attention**, ICLR, 2021.

[5] S. H. Bach, M. Broecheler, B. Huang, and L. Getoor, **Hinge-Loss Markov Random Fields and Probabilistic Soft Logic**, Journal of Machine Learning Research, vol. 18, no. 109, pp. 1–67, 2017.

[6] `anon-ops/ops-lite`, OpenRCA 2.0 benchmark artifact, 500 cases, 2026.
