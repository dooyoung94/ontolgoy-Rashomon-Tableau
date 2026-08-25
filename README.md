# OpenRCA Missing-Relation Reasoning

## 연구 목표

완전한 CMDB/온톨로지를 전제로 하지 않고, 관측된 telemetry에서 **누락 causal relation을 복구하고 root-cause propagation path를 추론**한다.

핵심 연구 질문:

> 불완전한 시스템 관계 그래프에서 Abductive Hypothesis Generation + DeBERTa semantic evidence scoring + Probabilistic Soft Logic global inference가 원인 관계와 RCA 경로 복원 성능을 개선하는가?

## 메인 파이프라인

```text
OpenRCA 2.0 telemetry + incomplete topology
                |
                v
      Evidence Normalization
                |
                v
 Abductive Relation Hypothesis Generation
                |
                v
      DeBERTa Semantic Scoring
                |
                v
       PSL Global Inference
                |
        +-------+-------+
        |               |
        v               v
 Missing Relation    Root Cause Path
 Recovery            Ranking
```

### 역할

- **Abduction**: 현재 증상을 설명하는 데 필요한 누락 causal relation 후보를 생성한다.
- **DeBERTa**: 각 가설이 실제 metric/log/trace evidence와 의미적으로 얼마나 부합하는지 점수화한다.
- **PSL**: 여러 noisy evidence와 후보 relation을 soft logic으로 동시에 결합해 전역적으로 가장 타당한 causal graph를 추론한다.
- **Rashomon principle**: 초기 단계에서 하나의 원인으로 조기 확정하지 않고 근접한 Top-N 가설을 유지한다. 별도 알고리즘으로 사용하지 않는다.

## 데이터셋

메인 benchmark는 **OpenRCA 2.0**이다.

### Track A — Standard OpenRCA 2.0

공식 입력/정답 조건을 유지하여 기존 결과와 직접 비교한다.

주요 지표:

- Node-F1
- Edge-F1
- Path Accuracy
- Root-cause hit metrics
- Fault-type accuracy

### Track B — Incomplete-Relation Stress Test

Gold causal graph의 edge 일부를 입력 topology에서만 mask한다. Gold label은 평가에만 사용한다.

Mask ratio:

```text
0% / 20% / 40% / 60% / 80%
```

핵심 지표:

- Missing-edge Precision / Recall / F1
- Edge-F1
- Path Accuracy
- Root Cause Top-1 / Top-3
- 성능 저하율 vs. missing-edge ratio

## 핵심 가설

- **H1 — Missing Relation Recovery**: Abduction을 사용하면 graph-only baseline보다 누락 causal edge recall이 높아진다.
- **H2 — Semantic Evidence**: DeBERTa scoring은 구조 후보만 사용하는 abduction보다 false hypothesis를 줄인다.
- **H3 — Global Consistency**: PSL은 local semantic score만으로 ranking하는 방법보다 Edge-F1과 Path Accuracy를 개선한다.
- **H4 — Robust RCA**: relation masking 비율이 증가할수록 baseline보다 full model의 RCA 성능 저하가 작다.

## 필수 Ablation

```text
A0  Existing graph only
A1  Abduction only
A2  Abduction + DeBERTa
A3  Abduction + PSL
A4  Abduction + DeBERTa + PSL   <- Full
```

추가 비교:

- Tableau hard-logic verifier
- DeBERTa-only local ranking
- graph shortest/reachable path baseline
- 공개 가능한 OpenRCA 2.0 baseline / leaderboard 결과

## 원칙

- Gold causal edge/path는 hypothesis generation이나 scoring에 사용하지 않는다.
- relation masking은 입력 graph에만 적용한다.
- test set을 보고 PSL rule/weight 또는 DeBERTa threshold를 조정하지 않는다.
- 개발/검증/시험 split을 분리한다.
- 표준 OpenRCA 2.0 결과와 relation-masking 결과를 같은 숫자로 직접 비교하지 않는다.

## 이전 연구

MAGIC, WN18RR, WebQSP, Rashomon Worlds, Tableau, BADP 기반 이전 연구와 실험 결과는 [`STUDY_CASE.md`](STUDY_CASE.md)에만 보존한다.

전체 전환 전 코드는 브랜치 `archive/pre-openrca2-rewrite-20260825`에서 확인할 수 있다.
