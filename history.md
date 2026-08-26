# 연구 진행 기록

## 기록 목적

이 문서는 현재 논문의 연구 과정만 날짜순으로 요약한다. 상세한 이전 연구와 폐기된 아이디어는 [`studycase.md`](studycase.md)에 보존한다.

### 기록 원칙

- 문제정의, 방법, 데이터, 코드, 실험 결과가 바뀔 때만 기록한다.
- 실험 결과는 실행 링크 또는 commit과 함께 기록한다.
- 성공한 결과뿐 아니라 실패, 오류, 폐기 이유도 남긴다.
- 예상값과 실제값을 구분하고, 실행하지 않은 결과는 기록하지 않는다.
- 논문에 사용할 수 있는 결과인지 `주 결과 / 예비 결과 / 제외`로 표시한다.

---

## 현재 연구 기준선

- **연구 문제:** 운영 온톨로지에서 누락된 `CALLS_API`, `USES_DB`, `DEPLOYED_ON`, `RUNS_ON` 등의 관계 복원
- **제안 방법:** Abduction → DeBERTa → PSL → Recovered Ontology → LLM RCA
- **Track A:** 마스킹된 타입 관계의 복원 성능 평가
- **Track B:** 복원 관계 효과와 LLM 추가 효과 및 결합 시너지 평가
- **마스킹:** 노드와 telemetry는 유지하고 관계만 20%, 40%, 60% 제거
- **주요 RCA 지표:** Root F1, Path Reachability, Node F1, Edge F1
- **핵심 주장:** 완벽한 관계 복원이 아니라 불완전한 복원 관계가 손실된 RCA 성능을 얼마나 회복하는지 검증

---

## 진행 이력

### 2026-08-25 — 연구 문제 재정의

- **변경:** 기존 causal label 또는 수집 증거 마스킹에서 운영 토폴로지의 타입 관계 마스킹으로 주 실험 변경
- **대상:** `CALLS`, `USES_DATABASE`, `DEPLOYED_ON`, `RUNS_ON`, `USES_MESSAGING`, `HAS_SERVICE`
- **유지:** 노드, 로그, 메트릭, 트레이스, 자원 관측
- **이유:** 실제 프로젝트에서 객체보다 객체 간 의미 관계를 구성·유지하는 문제가 더 직접적임
- **상태:** 주 결과 설계로 확정

### 2026-08-26 — Track A/B 확정

- **Track A:** 귀추 + DeBERTa + PSL로 마스킹 관계 복원
- **Track B:** 복원 관계를 LLM이 활용할 때 RCA 성능이 얼마나 추가 개선되는지 검증
- **핵심 비교:** 관계 복원 효과, LLM 효과, 복원×LLM 결합 시너지
- **외부 기준:** 토폴로지를 제공하지 않는 OpenRCA 2.0 LLM Agent 조건
- **상한선:** 완전 토폴로지 + LLM
- **상태:** 연구 명제 및 실험 구조로 확정

### 2026-08-26 — 문서 구조 개편

- **README:** Track A/B, H1~H4, B0~B4 및 효과 분해식 반영
- **paper.md:** OpenRCA 2.0의 실제 결과와 Edge RCA 한계에서 연구 동기를 시작하도록 재작성
- **history.md:** 현재 연구 과정 기록 시작
- **주의:** OpenRCA 2.0의 공식 no-topology 조건과 ontology-augmented Track B를 별도 트랙으로 구분
- **상태:** 문서 반영

### 2026-08-26 — 연구 브랜치 검증

- **브랜치:** `research/structural-relation-recovery`
- **PR:** #13 `Research/structural relation recovery`
- **CI:** GitHub Actions `Topology Relation Recovery and RCA` Run 32956705800 성공
- **병합:** PR #13을 merge commit `1cdfff2ba343615926256600510ee582988385e3`으로 main에 반영
- **상태:** main 연구 기준선으로 승격 완료

### 2026-08-26 — 연구 프로토콜 안전장치 추가

- **문제:** telemetry observation으로 만든 topology를 동일 observation으로 재복원하면 정답 생성과 모델 입력이 순환하여 Track A 성능이 과대평가될 수 있음
- **변경:** 독립 reference provenance를 기본 필수로 지정하고 derived reference는 `diagnostic_only`로 격리
- **마스킹:** 사건별 mask에서 topology group별 nested mask로 변경
- **지표:** 제거 관계 0건 사례의 macro 평균 제외, realized mask ratio와 Candidate Recall Ceiling 추가
- **판정:** 연구 결과 산출 전 필수 프로토콜 수정

---

## 다음 연구 작업

1. OpenRCA 2.0 공식 500-case artifact와 현재 snapshot의 데이터 버전 확인
2. typed relation reference topology 생성 규칙과 provenance 확정
3. nested masking 20% / 40% / 60% 및 복수 seed 구현
4. Track A A0~A4 전체 ablation 실행
5. LLM RCA 입력 계약과 관계 confidence 표현 확정
6. Track B O0 및 B0~B4 자동 평가 구현
7. paired bootstrap, McNemar, interaction effect 계산
8. 20-case smoke test 후 500-case 최종 실험

---

## 이후 기록 템플릿

### YYYY-MM-DD — 작업명

- **가설/목적:**
- **변경 파일:**
- **데이터·버전:**
- **실행 명령 또는 Run:**
- **핵심 결과:**
- **오류·한계:**
- **판정:** 주 결과 / 예비 결과 / 제외
- **다음 작업:**
