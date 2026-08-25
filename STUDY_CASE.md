# Study Case — Previous Research Track

이 문서는 2026-08-25 이전 연구 방향을 보존하기 위한 기록이다. 현재 메인 연구의 설계 근거로만 사용하며, 신규 실험의 기준 문서는 아니다.

## 1. 이전 연구 질문

- 불완전한 지식그래프에서 여러 가능한 설명을 유지하면 조기 단일 해석보다 유효한 multi-hop evidence를 더 잘 보존할 수 있는가?
- semantic scorer와 symbolic reasoning을 결합하면 conflict identification/localization을 개선할 수 있는가?
- 고정 Top-K pruning 경계에서 유효 경로가 사라지는 문제를 adaptive retention으로 줄일 수 있는가?

## 2. 사용했던 데이터셋

- MAGIC multi-hop conflict: 588 rows / 1,056 conflict queries
- WN18RR: iterative multi-hop pruning 실험
- WebQSP: 실제 QA 연결 검증
- DAFNA-EA Books: truth discovery / possible-world adjudication

## 3. 주요 결과

### MAGIC structured diagnostic

| 방법 | Row conflict recall | Query conflict recall | Structured exact localization |
|---|---:|---:|---:|
| Weak lexical world scoring | 22.79% | 16.86% | 7.14% |
| DeBERTa-v3 world scoring | 41.50% | 31.53% | 15.48% |

- 동일 candidate-world 생성 구조에서 scorer만 weak lexical → `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`로 변경한 결과다.
- 따라서 위 결과는 DeBERTa 단독 성능이 아니라 Rashomon-style candidate worlds + DeBERTa semantic scoring + logical verification 구조에서 scorer 효과를 측정한 것이다.
- DeBERTa가 paired gold conflict path를 선택한 query 비율은 22.06%였다.

### Previous interpretation

- semantic scoring 품질은 multi-hop conflict path 선택에 큰 영향을 준다.
- possible-world retention은 유효 설명을 보존하는 데 유리했으나 최종 world ranking이 병목이었다.
- Tableau는 relation semantics가 충분히 grounding되지 않은 경우 많은 후보를 `UNRESOLVED`로 남겨 독립적 검증기의 가치가 제한되었다.
- BADP/Conditional BADP는 pruning-regret 연구로 분리 가능하지만 현재 RCA 연구에서는 메인 기여에서 제외한다.

## 4. 왜 연구 방향을 변경했는가

실제 RCA 문제에서는 ontology/CMDB가 완전하지 않으며, 특히 causal relation이 누락되어 있는 경우가 많다. 기존 구조는 이미 존재하는 relation을 여러 world로 해석하는 데 초점을 두었고, 다음 핵심 질문을 직접 풀지 못했다.

> 관측된 장애 evidence를 설명하기 위해 어떤 누락 causal relation이 존재해야 하는가?

따라서 현재 연구는 다음 구조로 전환한다.

1. **Abductive Hypothesis Generation** — 관측 결과를 설명하는 missing causal relation 후보 생성
2. **DeBERTa Semantic Evidence Scoring** — 후보 가설과 telemetry evidence의 의미 적합도 평가
3. **Probabilistic Soft Logic (PSL) Global Inference** — 불확실한 evidence와 가설을 전역적으로 결합해 causal graph/path 추론
4. **OpenRCA 2.0** — 표준 RCA 성능과 relation-masking robustness를 평가

Rashomon은 별도 알고리즘이 아니라 여러 근접 설명을 조기 확정하지 않는 설계 원칙으로만 유지한다. Tableau는 비교/ablation 대상으로 남길 수 있으나 메인 추론기는 PSL로 전환한다.

## 5. 보존 위치

전환 직전 전체 코드는 다음 브랜치에 보존한다.

`archive/pre-openrca2-rewrite-20260825`
