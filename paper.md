# 불완전 운영 온톨로지의 관계 복원과 LLM 기반 근본원인분석 성능 향상

## Abduction, DeBERTa, PSL을 이용한 신경-기호 관계 복원과 OpenRCA 2.0 기반 평가

> 문서 상태: 연구 프로토콜 및 논문 초안. OpenRCA 2.0 수치는 선행연구가 보고한 결과이며, 본 제안 방법의 최종 실험 결과는 아직 산출하지 않았다.

## 초록

대규모 소프트웨어 시스템의 근본원인분석(Root Cause Analysis, RCA)은 로그, 메트릭, 트레이스와 같은 이질적인 관측 데이터에서 장애 원인과 전파 과정을 함께 식별해야 한다. OpenRCA 2.0은 3개 마이크로서비스 시스템, 27개 장애 유형, 500개 장애 사례에 단계별 인과 전파 경로를 주석하고 LLM 에이전트의 결과 수준과 과정 수준 성능을 함께 평가하였다. 11개 LLM의 평균 성능은 Exact Match 20.7%, 원인 F1 34.1%, Any-Service Hit 76.0%, Path Reachability 61.5%, Node F1 62.2%, Edge F1 43.4%였다. 특히 Edge F1이 Node F1보다 18.8%p 낮아, 원인 또는 관련 서비스 식별보다 서비스 사이의 방향성 관계와 장애 전파 경로 추론이 더 어렵다는 점이 확인되었다.

그러나 실제 운영 프로젝트에서는 LLM 추론 이전에 또 다른 문제가 존재한다. CMDB 또는 운영 온톨로지의 객체가 존재하더라도 `CALLS_API`, `USES_DB`, `DEPLOYED_ON`, `RUNS_ON`과 같은 타입 관계가 누락되거나 최신 실행 상태와 일치하지 않을 수 있다. 정적 설계 정보, 동적으로 변하는 배포 구조, 부분적으로 관측된 트레이스, 서로 다른 식별자를 사용하는 로그·메트릭·자원 정보 사이를 연결하여 의미 관계를 형성하는 작업은 비용이 크고 불완전하다.

본 연구는 이러한 상황을 불완전 운영 온톨로지의 관계 복원 문제로 정의한다. 완전한 기준 토폴로지에서 관계만 20%, 40%, 60% 마스킹하고 노드와 수집 증거는 유지한다. 귀추 추론으로 관측 가능한 객체 쌍의 관계 후보를 생성하고, DeBERTa로 후보와 수집 증거의 의미 적합성을 평가하며, Probabilistic Soft Logic(PSL)으로 온톨로지 타입 제약과 관계 일관성을 결합한다. 평가는 Track A와 Track B로 구성한다. Track A는 실제 마스킹 관계의 Precision, Recall, F1과 관계 유형별 성능을 측정한다. Track B는 복원 토폴로지와 LLM의 효과를 2×2 요인 실험으로 분리하여, 관계 복원 효과, LLM 추가 효과, 두 요소의 결합 시너지를 OpenRCA 2.0의 Root F1, Path Reachability, Node F1, Edge F1로 평가한다. 본 연구는 완벽한 관계 복원을 주장하지 않으며, 불완전한 복원 관계가 완전 토폴로지에 근접한 RCA 성능을 제공할 수 있는 조건을 밝히는 것을 목적으로 한다.

**주요어:** 근본원인분석, 운영 온톨로지, 토폴로지 복원, 귀추 추론, DeBERTa, Probabilistic Soft Logic, 대규모 언어모델, OpenRCA 2.0

---

## 1. 서론

### 1.1 OpenRCA 2.0의 문제정의

마이크로서비스 장애는 최초 장애 지점과 관측 증상 지점이 다를 수 있다. 하나의 서비스 또는 인프라에서 발생한 장애가 RPC 호출, 메시징, 공유 데이터베이스, 동일 호스트 자원 등을 통해 여러 서비스로 전파되기 때문이다. RCA 에이전트는 로그, 메트릭, 트레이스에서 원인을 역추론하고, 해당 원인이 관측 증상까지 어떻게 전파되었는지 설명해야 한다.

기존 RCA 벤치마크는 주로 최종 원인 라벨만 평가하여, 올바른 서비스를 우연히 선택했지만 잘못된 전파 경로를 제시하는 문제를 드러내지 못했다. OpenRCA 2.0은 PAVE(Path Annotation via Verified Effects)를 통해 알려진 장애 주입 지점에서 관측 효과 방향으로 전파 경로를 검증하고, 이를 과정 수준 정답 그래프로 제공한다 [1].

OpenRCA 2.0의 LLM 에이전트는 서비스 의존 토폴로지를 입력으로 받지 않는다. 에이전트는 parquet 형식의 로그·메트릭·트레이스를 도구로 조회하고, 서비스 관계와 원인 경로를 직접 추론하여 구조화된 CausalGraph를 출력한다. 즉 OpenRCA 2.0은 토폴로지 비제공 조건에서 LLM의 조사 능력을 평가하며, 평가용 정답 그래프와 에이전트 입력을 분리한다.

### 1.2 OpenRCA 2.0의 실제 결과와 한계

OpenRCA 2.0은 TrainTicket, OpenTelemetry Demo, DeathStarBench Hotel Reservation에서 수집한 500개 장애 사례를 포함하며, 사례당 평균 7.5개의 검증된 인과 간선을 제공한다 [1]. 11개 frontier LLM을 동일한 도구 기반 에이전트 구조로 평가한 주요 결과는 표 1과 같다.

**표 1. OpenRCA 2.0 선행연구의 500개 사례 통합 결과**

| 구분 | EM | 원인 F1 | AnySvc | Path Reachability | Node F1 | Edge F1 |
|---|---:|---:|---:|---:|---:|---:|
| 11개 모델 평균 | 20.7 | 34.1 | 76.0 | 61.5 | 62.2 | 43.4 |
| 보고된 열별 최고 | 29.4 | 43.8 | 82.6 | 71.8 | 67.9 | 50.4 |

주: 단위는 %, 열별 최고값은 서로 다른 모델에서 산출될 수 있다.

다음 세 가지 한계가 본 연구의 출발점이다.

1. **정답 노드와 경로의 격차:** AnySvc 평균은 76.0%지만 검증된 경로를 요구하는 Path Reachability는 61.5%다. 일부 모델은 올바른 서비스를 찾고도 타당한 경로를 구성하지 못한다.
2. **노드와 간선의 격차:** 평균 Node F1은 62.2%, Edge F1은 43.4%로 18.8%p 차이가 난다. 서비스 식별보다 방향성 관계 구성의 난도가 높다.
3. **운영 지식 입력의 부재:** 공식 에이전트는 토폴로지를 받지 않고 trace에서 관계를 추론한다. 이는 공정한 investigative benchmark라는 장점이 있지만, 실제 운영에서 구축한 CMDB·온톨로지 관계가 LLM RCA에 제공하는 가치와 불완전한 관계의 영향을 직접 평가하지 않는다.

### 1.3 실제 운영 온톨로지에서 관계 형성이 어려운 이유

운영 온톨로지는 단순 그래프 파일이 아니라 객체 유형, 허용 관계, 속성, 제약을 정의하는 의미 계층이다. 온톨로지 스키마가 존재하더라도 특정 시점의 실제 관계 인스턴스는 수집 데이터에서 별도로 연결해야 한다.

- **동적 변화:** 오토스케일링, 롤링 업데이트, 신규 API 및 데이터베이스 연결은 실행 토폴로지를 계속 변경한다.
- **부분 관측:** trace는 실제로 계측·샘플링된 요청 경로만 보여주며, 모든 잠재 관계를 항상 관측하지 않는다.
- **식별자 불일치:** CMDB 서비스명, APM 인스턴스명, Kubernetes pod, trace span, DB 접속명 사이의 식별자가 다를 수 있다.
- **관계 유형 모호성:** 두 객체가 같은 시간에 관측되었다는 사실만으로 `CALLS_API`, `USES_DB`, `DEPLOYED_ON` 중 어떤 의미 관계인지 확정하기 어렵다.
- **방향성 문제:** 장애 전파 방향, 호출 방향, 의존 방향이 서로 반대일 수 있어 단순 동시 발생 또는 유사도만으로 간선을 정하기 어렵다.
- **정적·동적 정보의 시차:** 사람이 관리하는 CMDB와 실제 실행 흔적 사이에 configuration drift가 발생한다.

최근 연구는 동적 서비스 의존성 [6], topology-aware RCA [7], 객체 중심의 관측 데이터 온톨로지 [8]의 필요성을 제시한다. 하지만 불완전한 타입 관계를 통제된 방식으로 마스킹하고 복원 성능과 LLM RCA 성능을 단계적으로 연결한 평가는 아직 제한적이다.

### 1.4 연구 목적과 기여

본 연구의 목적은 LLM 자체가 관계를 무제한 생성하게 하는 것이 아니라, 수집 증거와 온톨로지 제약으로 복원한 신뢰도 기반 관계가 LLM RCA의 간선 및 전파 경로 추론을 얼마나 향상시키는지 검증하는 것이다.

본 연구의 기여는 다음과 같다.

1. 노드가 아닌 운영 온톨로지의 타입 관계 누락을 별도의 RCA 선행 문제로 정의한다.
2. 귀추, DeBERTa, PSL을 결합한 증거 기반 관계 복원 방법을 제안한다.
3. 실제 제거한 관계만 평가하여 잔존 관계로 인한 성능 착시를 방지한다.
4. 관계 복원 효과와 LLM 추가 효과를 요인 실험으로 분해한다.
5. OpenRCA 2.0의 outcome·process 지표를 이용하여 완벽하지 않은 관계 복원이 실제 RCA 성능을 얼마나 회복하는지 측정한다.

---

## 2. 관련 연구

### 2.1 LLM 기반 RCA와 과정 수준 평가

OpenRCA는 335개 장애와 68GB 이상의 로그·메트릭·트레이스를 이용하여 LLM 기반 RCA를 평가했으며, 전용 RCA Agent를 사용한 최상위 결과도 낮아 복합 운영 데이터 추론의 어려움을 보여주었다 [2]. OpenRCA 2.0은 최종 원인 라벨에서 단계별 인과 과정 감독으로 평가 범위를 확장하고, Path Reachability, Node F1, Edge F1을 도입하였다 [1]. 본 연구는 OpenRCA 2.0의 공식 지표와 no-topology 에이전트를 비교 기준으로 사용한다.

### 2.2 그래프·토폴로지 기반 RCA

CHASE는 trace 기반 호출 토폴로지에 로그와 메트릭 노드를 결합한 이질 그래프로 RCA를 수행한다 [10]. DynaCausal은 시간에 따라 변하는 서비스 관계와 장애 전파를 함께 모델링한다 [6]. TopoEvo는 topology drift와 topology-agnostic LLM의 downstream symptom 편향을 문제로 제시한다 [7]. 이러한 연구는 그래프 구조가 RCA에 중요함을 보여주지만, 본 연구는 주어진 그래프 사용보다 누락된 의미 관계의 복원과 그 복원 품질이 LLM에 미치는 영향을 중심으로 한다.

### 2.3 온톨로지 기반 관측 데이터 구성

UModel은 로그·메트릭·트레이스와 운영 객체를 가상 온톨로지 계층으로 표준화하고 관계 그래프로 연결하는 object-centric observability를 제안한다 [8]. MetaRCA는 구성요소 유형과 연결 관계를 표현하는 Meta Causal Graph를 사용한다 [9]. 이들은 의미 계층의 필요성을 보여주지만, 실제 관계가 일부 없는 상황에서 관계 유형별 복원 정확도와 downstream LLM 효과를 분리하여 평가하지는 않는다.

### 2.4 귀추·DeBERTa·PSL

귀추 추론은 관측 결과를 설명할 수 있는 가설을 생성하는 추론 방식이다 [3]. DeBERTa는 disentangled attention을 이용하여 문장 표현과 의미 관계 판단 성능을 향상시킨 언어모델이다 [4]. PSL은 연속값 논리 변수와 soft constraint를 이용하여 불확실한 사실과 규칙을 결합한다 [5]. 본 연구에서는 귀추를 후보 생성기, DeBERTa를 의미 적합도 평가기, PSL을 전역 제약 추론기로 역할 분리한다.

---

## 3. 문제 정의

### 3.1 온톨로지 스키마와 런타임 토폴로지

운영 온톨로지 스키마를 다음과 같이 정의한다.

$$
\Omega=(\mathcal{T},\mathcal{R},\mathcal{C})
$$

- $\mathcal{T}$: Service, API, Database, Pod, Node 등의 객체 유형
- $\mathcal{R}$: `CALLS_API`, `USES_DB`, `DEPLOYED_ON`, `RUNS_ON` 등의 관계 유형
- $\mathcal{C}$: domain, range, cardinality, 방향성 및 금지 관계 제약

시점 $t$의 런타임 토폴로지는 다음과 같다.

$$
G_t=(V_t,E_t), \qquad E_t\subseteq V_t\times\mathcal{R}\times V_t
$$

온톨로지는 가능한 의미 구조를 규정하고, 토폴로지는 특정 시점에 관측·확정된 관계 인스턴스를 표현한다.

### 3.2 관계 마스킹

완전 기준 관계 집합 $E$에서 마스킹 비율 $\rho$에 따라 관계 집합 $M_\rho$를 제거한다.

$$
\rho\in\{0.2,0.4,0.6\}, \qquad E_\rho=E\setminus M_\rho
$$

수집 관측 집합 $O$와 노드 집합 $V$는 유지한다.

$$
O_\rho=O, \qquad V_\rho=V
$$

따라서 본 연구는 telemetry masking이나 node discovery가 아니라 typed relation recovery를 다룬다.

### 3.3 연구 목표

Track A의 목표는 불완전 토폴로지 $E_\rho$와 수집 관측 $O$에서 누락 관계를 복원하는 것이다.

$$
\hat{M}_\rho=f_{A+D+P}(E_\rho,O,\Omega)
$$

$$
\hat{E}_\rho=E_\rho\cup\hat{M}_\rho
$$

Track B의 목표는 토폴로지 조건 $G_x$와 동일한 장애 증거 $D_q$를 LLM RCA에 제공하여 원인 및 경로 그래프를 예측하는 것이다.

$$
\hat{Y}_{q,x}=LLM(D_q,G_x,C)
$$

여기서 $C$는 고정 프롬프트와 출력 계약이며, $G_x$는 no-topology, masked, recovered, complete 조건 중 하나다.

### 3.4 연구 가설

- **H1:** 귀추 + DeBERTa + PSL은 복원 없음과 구성요소 ablation보다 Missing Relation F1을 향상시킨다.
- **H2:** 복원 토폴로지는 마스킹 토폴로지보다 비-LLM RCA 성능을 향상시킨다.
- **H3:** 동일한 복원 토폴로지에서 LLM RCA는 비-LLM RCA보다 Root F1, Path Reachability, Node F1, Edge F1을 향상시킨다.
- **H4:** 복원 토폴로지에서의 LLM 향상 폭은 마스킹 토폴로지에서의 LLM 향상 폭보다 크다.
- **H5:** 관계 복원이 완전하지 않아도 복원 토폴로지 + LLM은 완전 토폴로지 + LLM의 RCA 성능에 통계적으로 근접할 수 있다.

---

## 4. 제안 방법

### 4.1 수집 관측의 표준화

로그, 메트릭, 트레이스, 자원 정보에서 객체 쌍과 관측 근거를 다음 형식으로 표준화한다.

$$
o_k=(u,v,type_k,text_k,c_k,t_k,provenance_k)
$$

관측은 최종 관계가 아니라 관계 후보를 지지하는 증거다. trace parent-child, DB client span, pod-node 자원 속성, deployment metadata 등 출처별 provenance를 유지한다.

### 4.2 귀추 기반 후보 생성

수집 관측이 존재하고 온톨로지의 domain-range 제약을 만족하는 객체 쌍에 대해서만 후보를 생성한다.

$$
\mathcal{H}(O,\Omega)=\{(u,r,v)\mid observed(u,v,O)\land allowed_\Omega(u,r,v)\}
$$

모든 노드 쌍을 조합하지 않으므로 계산량과 허위 관계 생성을 제한한다.

### 4.3 DeBERTa 의미 점수

관측 문장과 관계 가설을 자연어 명제로 직렬화하고 entailment 기반 의미 점수를 계산한다.

$$
s^{sem}_{uvr}=P_\theta(y=entail\mid text(O_{uv}),hypothesis(u,r,v))
$$

예를 들어 `payment-api span에서 PostgreSQL payment-db 접근이 관측됨`이라는 증거가 `payment-api USES_DB payment-db`를 얼마나 지지하는지 평가한다.

### 4.4 PSL 전역 추론

후보 관계의 연속 진릿값을 $y_i\in[0,1]$로 두고, 귀추·의미 점수·온톨로지 규칙을 hinge-loss potential로 결합한다.

$$
\mathbf{y}^{*}=\arg\min_{\mathbf{y}\in[0,1]^m}\sum_{k=1}^{K}w_k\left(\max\{\ell_k(\mathbf{y}),0\}\right)^{p_k}
$$

규칙 예시는 다음과 같다.

- Service가 DB client span에서 Database에 접근하면 `USES_DB(Service, Database)`를 지지한다.
- API의 downstream span이 다른 Service에서 실행되면 `CALLS_API(API, Service)`를 지지한다.
- Service가 Pod에 배포되고 Pod가 Node에서 실행되면 Service와 Node의 실행 위치 일관성이 유지되어야 한다.
- 동일 관계에 상반된 방향 후보가 존재하면 trace parent-child와 ontology direction을 우선한다.

### 4.5 신뢰도·근거 기반 복원 그래프

임계값 $\tau$ 이상인 관계를 기존 토폴로지와 병합한다.

$$
\hat{E}_\rho=E_\rho\cup\{h_i\in\mathcal{H}\mid y_i^{*}\ge\tau\}
$$

각 관계에는 confidence와 provenance를 유지하여 LLM이 저신뢰 관계를 확정 사실로 오인하지 않도록 한다.

### 4.6 복원 그래프 기반 LLM RCA

LLM은 동일한 telemetry와 함께 다음 구조화 컨텍스트를 받는다.

- 마스킹 또는 복원된 관계 목록
- 관계 유형과 방향
- PSL 최종 신뢰도
- 관계를 지지하는 trace·metric·log 근거
- 온톨로지에서 허용한 관계 제약

LLM은 관계를 임의로 수정하는 대신 장애 증거와 관련된 관계 선택, 원인 후보 재순위화, 전파 경로 구성, 근거 연결을 수행한다. Track A의 복원 결과는 Track B에서 고정하여 관계 복원 효과와 LLM 추론 효과가 섞이지 않도록 한다.

---

## 5. 실험 설계

### 5.1 데이터셋

OpenRCA 2.0의 500개 장애 사례와 과정 수준 정답을 사용한다. 공식 데이터 확보 전 공개 snapshot 또는 mirror를 사용할 경우 dataset ID, commit, 사례 수를 결과에 명시하고 공식 500개 결과와 동일 데이터라고 가정하지 않는다.

OpenRCA 2.0의 causal graph와 injection label은 평가기에만 제공한다. 기준 구조 관계는 수집 가능한 전체 정보에서 구성하며, 독립 검증되지 않은 관계는 통제 실험용 reference topology로 명시한다.

### 5.2 Track A: 관계 복원 실험

| 실험군 | 방법 |
|---|---|
| A0 | 복원 없음 |
| A1 | 귀추 |
| A2 | 귀추 + DeBERTa |
| A3 | 귀추 + PSL |
| A4 | 귀추 + DeBERTa + PSL |
| A5 | 완전 토폴로지 상한선 |

각 방법은 관계 마스킹 20%, 40%, 60%에서 동일 사례와 동일 마스크 seed로 평가한다. 마스킹은 고정 순서를 사용하여 20%에서 제거한 관계가 40%와 60%에도 포함되는 nested masking으로 구성한다.

주 지표는 실제 제거 관계 $M_\rho$에 대한 Precision, Recall, F1이다.

$$
P=\frac{|\hat{M}_\rho\cap M_\rho|}{|\hat{M}_\rho|},\qquad
R=\frac{|\hat{M}_\rho\cap M_\rho|}{|M_\rho|},\qquad
F1=\frac{2PR}{P+R}
$$

관계 유형별 F1, MRR, Hits@K, 허위 관계 삽입률, 논리 모순률을 함께 보고한다. 복원 후 전체 토폴로지 F1은 잔존 관계의 영향을 받으므로 보조 지표로만 사용한다.

### 5.3 Track B: 관계 복원 × LLM 요인 실험

| 실험군 | 토폴로지 | RCA 방식 | 목적 |
|---|---|---|---|
| O0 | 없음 | 공식 OpenRCA 2.0 LLM Agent | no-topology 외부 기준선 |
| B0 | 마스킹 | 비-LLM RCA | 최저 기준선 |
| B1 | A4 복원 | 비-LLM RCA | 관계 복원 효과 |
| B2 | 마스킹 | LLM RCA | 불완전 관계에서의 LLM 효과 |
| B3 | A4 복원 | LLM RCA | 전체 제안 방법 |
| B4 | 완전 | LLM RCA | 통제된 상한선 |

O0는 공식 프로토콜 재현용이다. B2~B4는 에이전트에 토폴로지를 추가하므로 공식 leaderboard와 동일 조건이 아니며 ontology-augmented controlled track으로 구분한다.

관계 복원 효과는 다음과 같다.

$$
\Delta_{Recovery}=M(B1)-M(B0)
$$

복원 토폴로지에서 LLM이 추가한 효과는 다음과 같다.

$$
\Delta_{LLM,recovered}=M(B3)-M(B1)
$$

결합 시너지는 차이의 차이로 계산한다.

$$
S_{interaction}=[M(B3)-M(B1)]-[M(B2)-M(B0)]
$$

완전 토폴로지 대비 관계 복원 성능 회복률은 동일한 LLM 조건에서 계산한다.

$$
Recovery\ Ratio=\frac{M(B3)-M(B2)}{M(B4)-M(B2)}
$$

### 5.4 평가 지표

OpenRCA 2.0의 공식 정의를 따라 다음을 기록한다.

- Outcome: EM, F1, Precision, Recall, AnySvc
- Process: Path Reachability, Node F1, Edge F1
- Evidence: SQL Exec

Track A의 typed relation은 관계 유형까지 정확히 일치해야 정답으로 처리한다. Track B의 OpenRCA 2.0 primary metric은 서비스 수준으로 정규화한 directed pair를 사용한다. API·DB·Pod·Node 관계는 서비스 수준 causal path로 투영한 결과와 ontology-specific typed-edge 결과를 분리 보고한다.

### 5.5 통계 검증

- 동일 장애 사례의 paired 결과를 사용한다.
- 연속형 F1 차이는 paired bootstrap 95% 신뢰구간으로 보고한다.
- Hit, EM, Reachability와 같은 이진 지표는 paired proportion difference와 McNemar 검정을 사용한다.
- 마스킹 seed별 결과와 평균·표준편차를 보고한다.
- 관계 유형, 마스킹 비율, 시스템별 하위 분석을 수행한다.
- 다중 비교 시 Holm 보정을 적용한다.

### 5.6 누수 방지

- 마스킹 관계와 gold causal graph는 후보 생성·DeBERTa·PSL·LLM 입력에서 제외한다.
- B0~B4에서 telemetry, 장애 질의, 모델, 프롬프트, temperature, 도구, 호출 예산을 고정한다.
- LLM은 Track A의 복원 그래프를 수정하지 않고 RCA에 선택적으로 활용한다.
- 임계값은 test set이 아닌 validation split에서 고정한다.

---

## 6. 결과 보고 계획

본 절의 제안 방법 결과는 실험 완료 후 기록한다. 현재 시점에는 수치를 기입하지 않는다.

### 6.1 Track A 결과표

| Mask | Method | Missing P | Missing R | Missing F1 | Typed F1 | False-edge Rate |
|---:|---|---:|---:|---:|---:|---:|
| 20% | A0~A4 | — | — | — | — | — |
| 40% | A0~A4 | — | — | — | — | — |
| 60% | A0~A4 | — | — | — | — | — |

### 6.2 Track B 결과표

| Mask | Condition | Root F1 | PR | Node F1 | Edge F1 | SQL Exec |
|---:|---|---:|---:|---:|---:|---:|
| 20% | O0, B0~B4 | — | — | — | — | — |
| 40% | O0, B0~B4 | — | — | — | — | — |
| 60% | O0, B0~B4 | — | — | — | — | — |

다음 세 결과를 최종 기여 판단 기준으로 사용한다.

1. A4가 Missing Relation F1에서 ablation보다 우수한가?
2. $\Delta_{LLM,recovered}$가 양수이며 신뢰구간이 0을 넘는가?
3. B3가 B4보다 다소 낮더라도 B2 대비 높은 Recovery Ratio를 보이는가?

---

## 7. 논의

### 7.1 완벽한 관계 복원이 필요하지 않을 가능성

모든 누락 관계가 RCA에 동일하게 중요하지는 않다. 원인과 증상을 연결하는 bridge edge, 높은 fan-in을 갖는 공용 서비스 관계, 서비스-DB와 같은 수직 전파 관계는 일부만 복원되어도 경로 도달률을 크게 개선할 수 있다. 반대로 RCA 경로와 무관한 주변 관계를 많이 복원해도 downstream 성능은 거의 변하지 않을 수 있다. 따라서 Track A의 F1과 Track B의 Edge F1 향상을 함께 분석해야 한다.

### 7.2 오복원 관계가 LLM에 미치는 위험

잘못 복원된 고신뢰 관계는 LLM에 강한 구조적 편향을 줄 수 있다. $S_{interaction}<0$이면 LLM 자체의 실패라기보다 오복원 관계의 증폭 효과일 수 있다. 관계 confidence calibration과 provenance 제공은 이 위험을 분석하기 위한 필수 요소다.

### 7.3 OpenRCA 2.0과의 비교 해석

O0만 공식 no-topology 조건과 직접 비교할 수 있다. B2~B4는 온톨로지 정보를 추가한 통제 실험이므로 공식 수치를 넘어섰다는 leaderboard 주장보다, 동일 사례에서 정보 조건 변화가 만든 paired delta를 핵심 결과로 제시해야 한다.

---

## 8. 타당성 위협 및 한계

- **기준 토폴로지 편향:** 수집 데이터에서 만든 완전 구조가 실제 운영 정답과 다를 수 있다.
- **마스킹 현실성:** 균등 무작위 마스킹은 실제 CMDB 누락 패턴과 다를 수 있으므로 관계 유형별·구조별 마스킹이 필요하다.
- **데이터셋 일반화:** 3개 공개 마이크로서비스 시스템의 결과가 기업 운영 환경 전체를 대표하지 않는다.
- **LLM 변동성:** 모델 버전, temperature, 도구 호출 순서에 따라 성능이 달라질 수 있다.
- **지표 투영:** ontology typed edge와 OpenRCA service-level causal edge의 의미가 완전히 동일하지 않다.
- **비용:** LLM 호출과 DeBERTa·PSL 추론의 실행 비용 및 지연을 별도 보고해야 한다.

---

## 9. 결론

OpenRCA 2.0은 LLM이 원인 서비스를 부분적으로 찾더라도 방향성 간선과 검증 가능한 전파 경로 구성에는 큰 약점이 있음을 보여준다. 실제 운영에서는 여기에 CMDB·온톨로지 관계 자체의 누락과 시차가 추가된다. 본 연구는 이 문제를 관계 마스킹, 신경-기호 복원, LLM RCA의 두 트랙으로 분리한다. 귀추는 설명 가능한 후보를 생성하고, DeBERTa는 수집 증거의 의미 적합성을 평가하며, PSL은 온톨로지 제약과 전역 일관성을 반영한다. 이후 LLM이 복원 관계와 증거를 이용해 원인과 경로를 추론한다. 최종 목표는 관계 복원의 완벽성을 주장하는 것이 아니라, 불완전한 관계를 신뢰도와 근거를 포함해 복원했을 때 OpenRCA 2.0의 Edge F1과 Path Reachability를 얼마나 회복할 수 있는지 정량적으로 밝히는 것이다.

---

## 참고문헌

[1] A. Fang et al., “OpenRCA 2.0: From Outcome Labels to Causal Process Supervision,” arXiv:2606.27154, 2026. https://arxiv.org/abs/2606.27154

[2] J. Xu et al., “OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures?” ICLR, 2025. https://openreview.net/forum?id=M4qNIzQYpd

[3] J. R. Hobbs et al., “Interpretation as Abduction,” Artificial Intelligence, vol. 63, 1993.

[4] P. He et al., “DeBERTa: Decoding-enhanced BERT with Disentangled Attention,” ICLR, 2021. https://openreview.net/forum?id=XPZIaotutsD

[5] S. H. Bach et al., “Hinge-Loss Markov Random Fields and Probabilistic Soft Logic,” Journal of Machine Learning Research, vol. 18, 2017. https://www.jmlr.org/papers/v18/15-631.html

[6] S. Zhang et al., “DynaCausal: Dynamic Causality-Aware Root Cause Analysis for Distributed Microservices,” arXiv:2510.22613, 2025. https://arxiv.org/abs/2510.22613

[7] J. Wang et al., “TopoEvo: A Topology-Aware Self-Evolving Multi-Agent Framework for Root Cause Analysis in Microservices,” arXiv:2605.15611, 2026. https://arxiv.org/abs/2605.15611

[8] C. Pei et al., “UModel: An Agent-Ready Observability Data Modeling Method at Scale,” arXiv:2606.04799, 2026. https://arxiv.org/abs/2606.04799

[9] S. Liang et al., “MetaRCA: A Generalizable Root Cause Analysis Framework for Cloud-Native Systems Powered by Meta Causal Knowledge,” arXiv:2603.02032, 2026. https://arxiv.org/abs/2603.02032

[10] Z. Zhao et al., “CHASE: A Causal Heterogeneous Graph based Framework for Root Cause Analysis in Multimodal Microservice Systems,” arXiv:2406.19711, 2024. https://arxiv.org/abs/2406.19711
