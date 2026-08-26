# 불완전 운영 온톨로지의 관계 복원과 LLM 기반 RCA

> 저장소 이름의 `Rashomon-Tableau`는 초기 연구 이력에서 남은 이름이다. 현재 주 연구는
> **독립 기준 토폴로지에 대한 typed relation recovery와 downstream LLM RCA 효과 검증**이며,
> Rashomon Worlds와 Tableau 실험은 `studycase.md`의 선행 탐색 기록으로만 유지한다.

## 연구의 최종 명제

운영 환경에서는 로그·메트릭·트레이스가 수집되더라도 CMDB 또는 온톨로지의 관계 토폴로지가 완전하지 않을 수 있다. 특히 `CALLS_API`, `USES_DB`와 같은 의미 관계가 누락되면 원인 노드는 찾더라도 장애 전파 경로와 원인 간선을 정확하게 설명하기 어렵다.

본 연구의 최종 명제는 다음과 같다.

> **귀추 추론으로 누락 관계 후보를 생성하고, DeBERTa로 수집 증거와의 의미 적합성을 평가하며, PSL로 온톨로지 제약과 전역 일관성을 반영하면 불완전한 운영 관계를 복원할 수 있다. 또한 완벽하지 않은 복원 결과라도 LLM이 관계 신뢰도와 장애 증거를 함께 활용하면 OpenRCA 2.0 기준의 원인 노드·원인 간선·전파 경로 성능을 추가로 향상시킬 수 있다.**

이 연구는 관계가 완벽하게 복원된다고 주장하지 않는다. 핵심은 다음 두 효과를 분리하여 검증하는 것이다.

1. 관계 복원 자체가 RCA 성능을 얼마나 회복시키는가?
2. 복원된 관계를 LLM이 활용할 때 RCA 성능이 얼마나 추가 향상되는가?

---

## 연구 가설

- **H1 — 관계 복원 효과:** 귀추 + DeBERTa + PSL은 복원하지 않은 불완전 토폴로지와 개별 구성요소 대비 누락 관계 F1을 향상시킨다.
- **H2 — RCA 회복 효과:** 복원 토폴로지는 마스킹 토폴로지보다 원인 서비스 F1, Process Path Reachability, Node F1, Edge F1을 향상시킨다.
- **H3 — LLM 추가 효과:** 동일한 복원 토폴로지에서 LLM RCA는 비-LLM RCA보다 원인 노드·간선·경로 성능을 추가로 향상시킨다.
- **H4 — 결합 시너지:** LLM은 마스킹 토폴로지보다 신뢰도 기반 복원 토폴로지에서 더 큰 성능 향상을 보이며, 완전 토폴로지 + LLM의 상한선에 근접한다.

H1~H4는 결론이 아니라 실험으로 검증할 명제다. 결과가 성립하지 않는 마스킹 비율과 관계 유형도 함께 보고한다.

---

## 대상 관계와 코드 표현

마스킹 대상은 단순 인과 라벨이 아니라 실제 운영 온톨로지·CMDB에서 사용하는 타입 관계다.

| 의미 관계 | 코드 관계 | 예시 |
|---|---|---|
| `CALLS_API` | `CALLS` | frontend → order-api |
| `USES_DB` | `USES_DATABASE` | order-api → orders-db |
| 배포 관계 | `DEPLOYED_ON` | service → pod |
| 실행 관계 | `RUNS_ON` | pod → node |
| 메시징 사용 | `USES_MESSAGING` | service → kafka |
| 서비스 포함 | `HAS_SERVICE` | system → service |

노드는 유지하고 관계만 제거한다. 제거된 관계와 정답 관계는 모델에 공개하지 않는다.

---

## 전체 연구 구조

```text
완전한 기준 토폴로지
        ↓
관계만 20% / 40% / 60% 마스킹
        ↓
불완전한 운영 토폴로지 + 동일한 수집 데이터
        ↓
Track A: 귀추 → DeBERTa → PSL → 신뢰도 기반 관계 복원
        ↓
Track B: 복원 토폴로지 + OpenRCA 2.0 방식의 LLM RCA
        ↓
원인 노드·원인 간선·장애 전파 경로 평가
```

Track A와 Track B는 별도 주제가 아니다. Track A의 복원 결과가 Track B의 입력이 되는 순차 연구 구조다.

---

## Track A — 마스킹된 온톨로지 관계 복원

### 연구 질문

> 수집 데이터는 존재하지만 기존 토폴로지에 객체 간 관계가 없을 때, 귀추 + DeBERTa + PSL로 누락된 타입 관계를 얼마나 복원할 수 있는가?

### 통제 조건

- 완전 기준 토폴로지는 모델 입력 observation과 독립된 버전 관리 원천에서 가져온다.
- 토폴로지 관계만 20%, 40%, 60% 제거한다.
- 동일 시스템의 모든 장애 사례에는 동일한 topology-group mask를 적용한다.
- 노드와 수집 데이터는 제거하지 않는다.
- 제거된 관계의 위치나 타입을 모델에 알려주지 않는다.
- OpenRCA 2.0의 원인 정답과 원인 경로는 평가기에만 제공한다.

### 관계 복원 Ablation

| 실험군 | 구성 | 검증 목적 |
|---|---|---|
| A0 | 복원 없음 | 불완전 토폴로지 기준선 |
| A1 | 귀추 | 후보 생성 효과 |
| A2 | 귀추 + DeBERTa | 의미 증거 점수 효과 |
| A3 | 귀추 + PSL | 온톨로지 제약·전역 일관성 효과 |
| A4 | 귀추 + DeBERTa + PSL | 전체 제안 방법 |
| A5 | 완전 토폴로지 | 통제된 상한선 |

### 복원 출력

복원 결과는 관계 존재 여부만이 아니라 관계 유형, 신뢰도, 근거를 포함한다.

$$
\hat{G}=\{(u,r,v,p_{uv}^{r},e_{uv})\}
$$

- $u,v$: 출발·도착 객체
- $r$: 관계 유형
- $p_{uv}^{r}$: 복원 신뢰도
- $e_{uv}$: 복원에 사용한 수집 증거와 규칙 근거

현재 PSL의 visible-topology 제약은 snapshot에서 기능성이 명확한 `RUNS_ON`(Pod→Node)과
`HAS_SERVICE`(Service의 시스템 소속)에만 적용한다. `CALLS`, `DEPLOYED_ON`, `USES_DATABASE`,
`USES_MESSAGING`은 다중 대상이 정상일 수 있으므로 임의의 단일성 제약을 적용하지 않는다.

### 평가 지표

남아 있는 관계 때문에 전체 점수가 높아지는 착시를 피하기 위해 실제로 제거한 관계만 주 지표로 평가한다.

- Missing Relation Precision / Recall / F1
- 관계 유형별 F1
- Candidate Recall Ceiling
- 잘못된 관계 삽입률
- PSL 적용 전후 논리적 모순률
- 복원 후 전체 토폴로지 F1은 보조 지표

MRR·Hits@K는 query별 negative candidate universe가 확정되기 전에는 주 지표로 보고하지
않는다. 현재 코드의 후보 공간은 telemetry로 관측된 endpoint pair로 제한되므로, 후보 생성
단계가 정답 관계를 포함할 수 있는 최대치인 Candidate Recall Ceiling을 먼저 기록한다.

---

## Track B — 복원 관계를 활용한 LLM RCA 성능 향상

### 연구 질문

> Track A에서 복원한 관계와 신뢰도를 LLM이 장애 증거와 함께 사용하면, 복원 관계만 사용한 RCA보다 원인 노드·원인 간선·전파 경로 성능을 얼마나 추가 향상시킬 수 있는가?

### 2×2 요인 실험

관계 복원 효과와 LLM 효과를 분리하기 위해 다음 조건을 비교한다.

| 실험군 | 토폴로지 입력 | RCA 방법 | 검증 목적 |
|---|---|---|---|
| O0 | 토폴로지 없음 | OpenRCA 2.0 LLM Agent | 공식 no-topology 기준선 |
| B0 | 마스킹 토폴로지 | 비-LLM RCA | 최저 기준선 |
| B1 | A4 복원 토폴로지 | 비-LLM RCA | 순수 관계 복원 효과 |
| B2 | 마스킹 토폴로지 | LLM RCA | 불완전 관계에서의 순수 LLM 효과 |
| B3 | A4 복원 토폴로지 | LLM RCA | 전체 제안 방법 |
| B4 | 완전 토폴로지 | LLM RCA | 통제된 상한선 |

O0는 OpenRCA 2.0의 원 조건을 재현하기 위한 외부 기준선이다. OpenRCA 2.0은 평가용 정답 그래프를 제공하지만 에이전트 입력에는 서비스 의존 토폴로지를 주지 않고 trace에서 관계를 추론하게 한다. 따라서 B2~B4는 공식 leaderboard 조건과 동일한 비교가 아니라, 온톨로지 관계 정보의 추가 효과를 측정하는 통제 확장 실험으로 보고한다.

최종 제안 파이프라인은 다음과 같다.

```text
Abduction → DeBERTa → PSL → Recovered Ontology → OpenRCA 2.0 LLM RCA
```

### LLM의 역할

LLM은 Track A의 관계 정답을 다시 만드는 평가기가 아니다. 다음 기능으로 RCA를 고도화한다.

- 장애 증거와 관련된 복원 관계 선택
- 관계 신뢰도를 반영한 원인 후보 재순위화
- 저신뢰 또는 상충 관계의 RCA 사용 여부 판단
- 원인 노드에서 장애 현상까지의 전파 경로 추론
- 로그·메트릭·트레이스·온톨로지 관계를 결합한 장애 유형 판단
- 선택한 원인과 경로에 대한 근거 생성

Track A의 복원 점수는 고정한 뒤 LLM에 제공한다. LLM이 복원 그래프를 임의로 수정하게 하지 않아야 관계 복원 효과와 LLM 추론 효과를 분리할 수 있다.

### 효과 분해

관계 복원으로 얻은 순수 효과:

$$
\Delta_{Recovery}=M(B1)-M(B0)
$$

마스킹 토폴로지에서의 LLM 효과:

$$
\Delta_{LLM,masked}=M(B2)-M(B0)
$$

복원 토폴로지에서 LLM이 추가한 효과:

$$
\Delta_{LLM,recovered}=M(B3)-M(B1)
$$

복원과 LLM의 결합 시너지:

$$
S_{interaction}=[M(B3)-M(B1)]-[M(B2)-M(B0)]
$$

- $S_{interaction}>0$: LLM이 복원 관계를 유효한 RCA 정보로 활용함
- $S_{interaction}\approx0$: 관계 복원과 LLM의 효과가 독립적임
- $S_{interaction}<0$: 오복원 관계가 LLM 추론을 방해할 가능성이 있음

완전 토폴로지 대비 성능 회복률:

$$
Recovery\ Ratio=\frac{M(B3)-M(B2)}{M(B4)-M(B2)}
$$

완전 복원 여부보다 마스킹으로 손실된 RCA 성능을 어느 정도 회복했는지를 핵심 결과로 보고한다.

### OpenRCA 2.0 기반 평가 지표

- Any-Service Hit / All-Service Hit
- Root Cause Precision / Recall / F1
- Root Cause Exact Match
- Root Cause Hit@1 / Hit@3
- Process Path Reachability
- Node Precision / Recall / F1
- Edge Precision / Recall / F1

주요 결과는 Root F1, Path Reachability, Node F1, Edge F1의 변화량으로 제시한다. 특히 OpenRCA 계열 방법의 약점인 Edge F1과 원인 전파 경로 회복을 핵심 지표로 본다.

---

## 누수 방지 원칙

- 완전 토폴로지는 마스킹 생성과 상한선 평가에만 사용하며, 반드시 독립 provenance를 가진다.
- recovery 입력 observation으로 생성한 관계 집합을 다시 정답으로 사용하는 순환 평가는 금지한다.
- 제거된 관계는 후보 생성, DeBERTa, PSL, LLM 입력에 제공하지 않는다.
- Gold causal graph, injection label, gold root는 평가기에만 제공한다.
- 모든 B0~B4 조건에서 장애 사례와 수집 증거는 동일하게 유지한다.
- 비교 조건에서는 토폴로지와 LLM 사용 여부만 변경한다.
- LLM 프롬프트, 모델, temperature, 출력 형식, 호출 횟수를 고정한다.

### 연구 실행 게이트

- 기본 실행은 별도 `--reference-data`가 없으면 중단한다.
- contract-v1 reference는 topology·relation별 provenance와 case의 명시적 `topology_id`가 필요하다.
- 기존 case JSONL reference를 사용할 때는 case별 `reference_topology_provenance`에 `source`,
  `version`, `independent_of_model_observations=true`, `evaluator_only=true`가 필요하다.
- 기존 telemetry-derived embedded topology는 `--allow-derived-reference`를 붙인 CI·단위검증에서만
  허용하며, 산출물은 자동으로 `claim_scope=diagnostic_only`가 된다.
- 제거 관계가 0개인 사례는 missing-relation macro 평균에서 제외한다.

### 독립 Reference Topology 계약

논문용 정답은 기존 case JSONL의 `structural_relations`에 직접 넣지 않고
[`config/reference_topology_contract.yaml`](config/reference_topology_contract.yaml)의 v1 계약으로 관리한다.
작성 형식은 [`config/reference_topology_example.json`](config/reference_topology_example.json)에서 확인한다.
각 topology snapshot에는 `topology_id`, 시스템, 배포 버전, 유효 시간, entity, typed relation과
독립 provenance가 들어가야 한다. 각 관계 상태는 다음 셋 중 하나다.

| 상태 | 평가 의미 |
|---|---|
| `VERIFIED_POSITIVE` | 마스킹·Recall 정답으로 사용 |
| `VERIFIED_NEGATIVE` | 해당 관계를 예측하면 False Positive |
| `UNKNOWN` | 확인 불가능하므로 FP에서 제외하고 별도 비율로 보고 |

artifact에 없는 관계도 `UNKNOWN`으로 취급한다. 따라서 독립 자료에서 확인하지 못한 관계를
임의로 음성 정답으로 바꾸지 않는다. 대신 `verified_prediction_coverage`와
`unknown_edge_insertion_rate`를 함께 공개하여 precision의 감사 가능 범위를 표시한다.

Primary 실행에서는 각 case의 `metadata.topology_id`가 reference snapshot의 `topology_id`와
정확히 일치해야 한다. `system` 이름만으로 유일한 snapshot을 찾는 fallback은 파일 점검에는
사용할 수 있지만 배포 버전 혼합 위험 때문에 논문 결과로 승격하지 않는다.

독립적으로 작성한 JSON/JSONL manifest를 정규화하고 감사한다.

```bash
python scripts/build_reference_topology.py \
  --manifest artifacts/reference_manifest.json \
  --out artifacts/reference_topology.jsonl \
  --audit-out results/reference_topology_audit.json

python scripts/audit_reference_topology.py \
  --reference-data artifacts/reference_topology.jsonl
```

`build_reference_topology.py`는 입력 manifest를 정규화할 뿐, telemetry·trace에서 정답 관계를
추론하지 않는다. 실제 manifest는 source/deployment repository, service catalog, Kubernetes
control-plane snapshot 등 모델 관측과 독립된 원천에서 작성해야 한다.

---

## 데이터와 해석 범위

- OpenRCA 2.0의 장애 사례와 단계별 원인 전파 정답을 RCA 평가에 사용한다.
- OpenRCA 2.0이 완전한 영구 토폴로지 정답을 제공한다고 가정하지 않는다.
- 기존 수집 데이터 기반 구조는 diagnostic smoke test에만 사용한다.
- 논문용 완전 기준 토폴로지는 독립 source/deployment snapshot으로 별도 구축하며 아직 데이터 수집 전이다.
- 공개 mirror 또는 snapshot을 사용하면 dataset ID와 버전을 결과에 기록한다.
- 결과는 통제된 관계 누락 환경에서의 복원 및 LLM-RCA 효과로 한정하여 해석한다.

---

## 구현 상태

### 현재 구현

- topology group 단위 nested 관계 마스킹 20% / 40% / 60%
- 귀추 / DeBERTa / PSL 관계 복원 Ablation
- 마스킹·복원·완전 토폴로지의 비-LLM RCA 비교
- Root / Path / Node / Edge 지표와 변화량 계산
- 누수 방지형 OpenRCA 사례 로더와 자동 검증
- 독립 reference provenance 검사와 순환 reference 차단
- empty-denominator macro 제외, 실제 마스킹 비율 및 candidate ceiling 기록
- PSL이 visible topology의 기능적 관계 제약을 실제 추론 입력으로 사용
- Reference Topology v1 계약, 관계별 provenance와 3상태 판정
- 독립성·domain/range·시간·버전·중복 검증 및 감사 CLI
- `UNKNOWN`을 FP에서 제외하는 open-world Track A 평가

### 다음 구현

- OpenRCA 대상 시스템별 독립 source/deployment snapshot 수집 및 manifest 작성
- 동일 복원 그래프에 대한 LLM RCA 인터페이스
- B0~B4 2×2 요인 실험 자동화
- LLM 추가 효과와 결합 시너지 계산
- 20건 검증 후 OpenRCA 2.0 전체 사례 확장

README의 Track B는 최종 연구 명제와 실험 설계다. LLM 평가가 완료되기 전 결과가 확보된 것처럼 표현하지 않는다.

---

## 코드 구조

```text
수집 데이터에서 관계 단서 생성
src/openrca_mr/structural.py

토폴로지 관계 제거 / 복원
src/openrca_mr/topology_recovery.py

관계 복원 평가
src/openrca_mr/stage1_eval.py

토폴로지 + OpenRCA 장애 원인 분석 통합 평가
src/openrca_mr/topology_rca_eval.py

관계 복원 실행
scripts/run_structural_recovery.py

통합 평가 실행
scripts/run_topology_rca_evaluation.py

자동 검증 및 실제 20건 실험
.github/workflows/openrca2-smoke.yml
```

### Track A 실행

```bash
python scripts/run_structural_recovery.py \
  --data artifacts/topology_cases.jsonl \
  --reference-data artifacts/reference_topology.jsonl \
  --out results/a4_40.json \
  --variant abduction_deberta_psl \
  --topology-missing-ratio 0.40 \
  --seed 42
```

### 현재 Track A + 비-LLM RCA 통합 평가

```bash
python scripts/run_topology_rca_evaluation.py \
  --data artifacts/topology_cases.jsonl \
  --reference-data artifacts/reference_topology.jsonl \
  --out results/topology_rca_40.json \
  --topology-variant abduction_deberta_psl \
  --rca-variant full \
  --topology-missing-ratio 0.40 \
  --seed 42
```

`--rca-variant full`은 현재 귀추 + DeBERTa + PSL 기반 RCA 구성으로, LLM 실행을 의미하지 않는다. 최종 Track B에서는 고정된 복원 토폴로지를 OpenRCA 2.0 방식의 LLM 에이전트에 추가 입력하여 B2~B4를 평가한다.

---

## 최종 논문 기여

1. CMDB·온톨로지의 타입 관계가 누락된 운영 환경을 관계 마스킹 실험으로 정의한다.
2. 귀추 + DeBERTa + PSL을 결합한 신경-기호 관계 복원 방법을 제안한다.
3. 관계 복원 성능과 최종 RCA 성능을 분리하여 평가한다.
4. 복원 관계가 LLM의 원인 노드·간선·전파 경로 추론을 얼마나 추가 향상시키는지 정량화한다.
5. 완벽한 관계 복원이 아니어도 완전 토폴로지에 근접한 RCA 성능을 낼 수 있는 조건을 분석한다.

이전 MAGIC, WN18RR, WebQSP, Rashomon Worlds, Tableau, BADP 기반 연구와 실험은 [`studycase.md`](studycase.md)에 보존한다.
