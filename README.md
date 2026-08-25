# OpenRCA Missing-Relation Reasoning

## 연구 목표

완전한 CMDB/온톨로지를 전제로 하지 않고, 관측된 telemetry에서 **누락 causal relation을 복구하고 root-cause propagation path를 추론**한다.

핵심 연구 질문:

> 불완전한 시스템 관계 그래프에서 Abductive Hypothesis Generation + DeBERTa semantic evidence scoring + Probabilistic Soft Logic inference가 원인 관계와 RCA 경로 복원 성능을 개선하는가?

## 메인 파이프라인

```text
OpenRCA 2.x telemetry + incomplete observed structure
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
         PSL Inference
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
- **PSL**: noisy evidence와 후보 relation을 soft logic으로 결합한다. 실제 cross-edge path constraint가 포함된 경우에만 `global inference`라고 부른다.
- **Rashomon principle**: 초기 단계에서 하나의 원인으로 조기 확정하지 않고 근접한 Top-N 가설을 유지한다. 별도 알고리즘으로 사용하지 않는다.

## 데이터 및 평가 트랙

### Track A — OpenRCA 2.0 standard protocol

공식 OpenRCA 2.0 평가와 비교할 때는 **agent 입력에 ground-truth topology/causal graph를 제공하지 않는다.** 모델-visible dependency는 traces에서만 관찰해야 한다.

공식 비교 지표:

- Root-cause exact/F1 및 AnySvc
- Node-F1
- Edge-F1: 정규화된 `(source service, target service)` directed pair 기준
- Path Reachability: 올바른 root service를 실제로 예측했고, 그 root에서 gold alarm service까지 predicted path가 있을 때만 성공

### Track B — Incomplete-Relation Stress Test

모델-visible structural graph의 일부 edge를 입력에서만 mask한다. 이 트랙은 **통제된 missing-relation 내성 실험**이며 공식 standard leaderboard 숫자와 동일 조건으로 직접 비교하지 않는다.

Mask ratio:

```text
0% / 20% / 40% / 60% / 80%
```

핵심 지표:

- Missing-edge Precision / Recall / F1 (service-pair 기준)
- Node-F1 / Edge-F1
- Process Path Reachability
- Root Cause Top-1 / Top-3
- 성능 저하율 vs. missing-edge ratio

## 필수 Ablation

```text
A0  Observed graph only
A1  Abduction only
A2  Abduction + DeBERTa
A3  Abduction + PSL
A4  Abduction + DeBERTa + PSL   <- Full
```

## 데이터셋 버전 원칙

- 논문 OpenRCA 2.0 PAVE 500-case 공식 artifact가 확보되면 Track A의 최종 수치는 그 버전에서 산출한다.
- 공개 mirror/snapshot으로 수행한 실험은 반드시 정확한 dataset ID/version을 결과에 기록하고, 공식 PAVE 결과와 동일 데이터라고 가정하지 않는다.
- Gold `causal_graph.json` / injection labels는 evaluator에서만 읽는다. 후보 생성·DeBERTa·PSL 입력으로 사용하지 않는다.

## 이전 연구

MAGIC, WN18RR, WebQSP, Rashomon Worlds, Tableau, BADP 기반 이전 연구와 실험 결과는 [`studycase.md`](studycase.md)에 보존한다.

전체 전환 전 코드는 브랜치 `archive/pre-openrca2-rewrite-20260825`에서 확인할 수 있다.
