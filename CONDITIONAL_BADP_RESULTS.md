# Conditional BADP 확대 실험 결과

## 1. WebQSP n=20

성공 run: `32829786375`, artifact: `webqsp-conditional-badp-20`.

| 정책 | Search Success | Hit@1 | Retrieval F1 | Answer Recall | Pruning Regret | Avg Width | Avg Expanded |
|---|---:|---:|---:|---:|---:|---:|---:|
| Top-3 | 35% | 20% | **10.42%** | 27.08% | **15%** | **3.00** | 33.05 |
| Top-5 | 35% | 20% | 7.14% | 27.08% | 20% | 5.00 | 46.35 |
| Relative-loss .50 | **45%** | 20% | 7.25% | 32.42% | 20% | 8.90 | 68.80 |
| Always BADP Top-3 .005 | 35% | 20% | 8.18% | 27.08% | 20% | 4.25 | 45.65 |
| Conditional Top-3 tau=.005, delta=.005 | 35% | 20% | 8.18% | 27.08% | 20% | 4.25 | 45.65 |
| Conditional Top-3 tau=.010, delta=.005 | 35% | 20% | 8.18% | 27.08% | 20% | 4.25 | 45.65 |
| Conditional Top-5 tau=.010, delta=.010 | 35% | 20% | 5.49% | 27.08% | 20% | 7.38 | 64.45 |

### Conditional activation diagnostics

| 정책 | Boundary checks | Activation rate | Extra selected / activation | Mean margin |
|---|---:|---:|---:|---:|
| Top3 tau=.005 delta=.005 | 40 | 60.0% | 2.08 | 0.00965 |
| Top3 tau=.010 delta=.005 | 40 | 72.5% | 1.72 | 0.00965 |
| Top3 tau=.020 delta=.010 | 40 | 87.5% | 2.49 | 0.00819 |
| Top5 tau=.010 delta=.010 | 40 | 92.5% | 2.57 | 0.00993 |
| Top5 tau=.020 delta=.010 | 40 | 97.5% | 2.44 | 0.00993 |

### 해석

현재 WebQSP 설정에서는 Conditional BADP가 Top-3를 이기지 못했다. 특히 `tau=.005, delta=.005`는 search success가 동일한 35%이면서 평균 폭이 3.00에서 4.25로 증가했고 Retrieval F1은 10.42%에서 8.18%로 감소했다. 즉 현재 tau/delta는 너무 자주 발동하며, 실제 위험 경계와 불필요한 near-tie를 충분히 구분하지 못한다.

Relative-loss .50은 45% search success로 가장 높았지만 평균 폭 8.90, 평균 확장 68.80으로 비용이 매우 크므로 효율 우위로 보기는 어렵다.

## 2. WN18RR n=50

Run `32829825452`에서 50개 질의 평가 계산 자체는 완료되었으나 workflow summary가 결과 JSON의 `summary` 키를 읽도록 잘못 작성되어 `KeyError: 'summary'`로 실패했다. 실제 결과 파일의 정책 키는 `policies`이다.

평가 로그에서 확인 가능한 핵심 결과:

| 정책 | Search Success | Avg Expanded |
|---|---:|---:|
| Top-3 | 40% | 24.38 |
| Boundary Top-3 .001 | 42% | 25.08 |
| Boundary Top-3 .005 | 46% | 25.42 |
| Conditional Top-3 tau=.005 delta=.005 | 46% | 25.42 |
| Top-5 | 56% | 29.00 |
| Boundary Top-5 .001 | 58% | 29.50 |
| Boundary Top-5 .010 | 60% | 31.08 |
| Conditional Top-5 tau=.010 delta=.010 | 60% | 31.08 |
| Boundary Top-5 .050 | 62% | 34.88 |

Budget-matched 결과에서는 Top-3 대비 Boundary Top-3 .001이 +2%p success / -2%p regret, 평균 확장 +0.70이었고, Top-5 대비 Boundary Top-5 .001이 +2%p success / -2%p regret, 평균 확장 +0.50이었다.

### 해석

WN18RR에서는 경계 보존이 작은 추가 비용으로 search success와 pruning regret을 개선하는 일관된 신호가 있다. 다만 현재 Conditional 설정은 동일 delta의 always-on BADP와 동일 결과가 나와, 실제로 조건부 gating이 비용을 줄였다는 증거는 아직 없다. 즉 현재 tau가 충분히 선택적이지 않거나, 작은 margin 상태가 대부분의 유효 경계에서 발생하고 있을 가능성이 있다.

## 3. 현재 결론

현재 결과는 `Conditional BADP가 일반적으로 Top-K보다 우수하다`는 가설을 지지하지 않는다.

더 정확한 결론은 다음과 같다.

1. WN18RR 구조 스트레스테스트에서는 boundary-local preservation 자체의 효과가 반복해서 관찰된다.
2. WebQSP 실제 질의 연결에서는 현재 Conditional BADP가 Top-3보다 비용 대비 열세다.
3. Conditional gating이 always-on BADP보다 비용을 절약하지 못했다.
4. 따라서 다음 단계는 tau를 임의 grid로 늘리는 것이 아니라, `Pruning Regret` 발생 구간의 boundary margin 분포를 직접 분석하여 activation criterion을 재설계하는 것이다.

현재 가장 중요한 다음 검증은 다음 조건부 확률 비교이다.

$$
P(PR=1\mid\Delta_K\le\tau)
\quad\text{vs}\quad
P(PR=1\mid\Delta_K>\tau)
$$

그리고 branching을 함께 통제하여 margin 자체가 독립적인 위험 신호인지 확인해야 한다.
