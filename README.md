# Rashomon-Tableau

## Provenance-Aware Logical Conflict Localization and Truth Resolution from Conflicting Sources

> **핵심 연구 질문:** 서로 상충하는 여러 source를 하나로 먼저 합치거나 하나를 버리지 않고, 각 claim의 논리적 의미와 provenance를 유지한 채 conflict를 분석하면 실제 truth를 더 잘 찾을 수 있는가?

Rashomon-Tableau는 세 단계를 분리한다.

```text
1. Logical Reasoning
   explicit claim + ontology/rules
              ↓
   implicit entailment / contradiction

2. Conflict Localization
   Source → Claim → Rule → Derived Claim → Conflict
              ↓
   exact / partial / conflict

3. Rashomon Truth Resolution
   source reliability
        + proposition support
        + logical compatibility
        + provenance
              ↓
   candidate truth + confidence
```

여기서 **Rashomon**은 Machine Learning의 “near-optimal model set”을 의미하지 않는다. 동일 사건에 대한 상충된 관점을 성급히 제거하지 않고 함께 분석하여 더 정당화 가능한 truth에 접근한다는 문제의식을 의미한다.

---

## Current Evidence

### Real-world Truth Discovery — DAFNA-EA Books

공개 DAFNA-EA Books의 실제 온라인 source claim과 독립 gold truth를 사용한다.

- Gold books: **100**
- Source-object claims: **1,999**
- Sources: **227**

| Method | Exact Truth Accuracy | Mean Author F1 | Conflict Localization Macro-F1 |
|---|---:|---:|---:|
| Whole-Claim Majority | 44.00% | 73.57% | 49.04% |
| Reliability-Weighted Whole Claim | 45.00% | 75.24% | 50.37% |
| **Provenance-Aware Atomic Resolution** | **61.00%** | **82.88%** | **74.58%** |

제안 방식은 reliability-weighted baseline 대비:

- Exact truth accuracy: **+16.0 pp**
- Mean author F1: **+7.64 pp**
- Conflict localization Macro-F1: **+24.21 pp**

중요한 차이는 multi-valued claim을 하나의 문자열로 보지 않는 것이다.

```text
Gold candidate = {A, B}

Source 1 = {A, B} → exact
Source 2 = {A}    → partial support
Source 3 = {C}    → conflict
```

즉 `{A}`와 `{A,B}`를 무조건 서로 다른 false/true 후보로 처리하지 않고 atomic proposition 수준에서 support와 conflict를 구분한다.

Measured result:

- [`results/truth_discovery_books_metrics.json`](./results/truth_discovery_books_metrics.json)
- CI Run: `32706842910`

### Logical Core — FOLIO

현재 parser가 엄격하게 지원하는 FOLIO validation 28/204 fragment에서:

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Forward Horn | 75.00% | 74.18% |
| Semantic Clause Tableau | **96.43%** | **96.33%** |

**주의:** 96.43%는 full FOLIO 결과가 아니다. 현재 grammar coverage는 13.73%이다.

### Dual-Direction Contradiction — LogicNLI

공식 structured `test_logic` 2,000 statements:

| Method | Accuracy | Macro-F1 | Paradox F1 |
|---|---:|---:|---:|
| Single-Path Forward | 74.00% | 65.78% | 0.00% |
| Dual-Direction Proof Check | **98.40%** | **98.40%** | **97.92%** |

이는 end-to-end NLP 결과가 아니라 symbolic reasoning-layer 평가다.

---

## Research Positioning

이 연구는 다음을 **최초라고 주장하지 않는다**.

- multi-perspective reasoning → Standpoint Logic, Multi-Context Systems 선행연구 존재
- multiple logical justification → Axiom Pinpointing 선행연구 존재
- conflicting-source truth discovery → TruthFinder, CATD 등 선행연구 존재
- logic-constrained truth discovery → Constrained Truth Discovery 선행연구 존재
- ontology-aware truth finding → semantic/ontology truth-discovery 선행연구 존재

차별화하려는 지점은 다음이다.

> **Source provenance를 logical derivation에서 분리하지 않고 `Source → Claim → Rule/Ontology → Derived Claim → Conflict` 경로로 유지하고, 이 localized conflict evidence를 다시 truth resolution에 사용한다.**

| Approach | Source Reliability | Logic/Semantics | Explicit Derivation Provenance | Conflict Localization | Truth Resolution |
|---|---:|---:|---:|---:|---:|
| Tableau | X | O | proof | O | X |
| Axiom Pinpointing | X | O | O | O | X |
| Standpoint Logic | X | O | perspective | O | X |
| TruthFinder / CATD | O | 제한적 | X | 제한적 | O |
| Constrained Truth Discovery | O | O | constraint 중심 | 제한적 | O |
| **Rashomon-Tableau** | **O** | **O** | **O** | **O** | **O** |

이 표는 개별 구성요소가 모두 새롭다는 뜻이 아니라, **provenance-aware conflict path를 truth adjudication까지 연결하는 operational architecture**가 연구 대상이라는 의미다.

---

## Repository

```text
src/rashomon_tableau/
├── clause_tableau.py       # semantic SAT / refutation core
├── tableau.py              # relational tableau-style reasoner
├── ontology.py             # ontology closure / derivations
├── rashomon.py             # multiple justification utilities
└── truth_resolution.py     # real-data source reliability + atomic truth resolution

scripts/
├── evaluate_folio_fragment.py
├── evaluate_logicnli.py
└── evaluate_truth_discovery_books.py

results/
├── folio_fragment_metrics.json
├── logicnli_metrics.json
└── truth_discovery_books_metrics.json
```

---

## Paper

실제 논문 형식의 연구 초안:

- **[`paper.md`](./paper.md)** — 현재 연구 방향 기준
- [`report.md`](./report.md) — 과거 개발/실험 기록 성격의 문서

`paper.md`에서는 연구를 다음 3개의 RQ로 정리한다.

1. **RQ1 Logical Reasoning** — implicit entailment/conflict를 논리적으로 복원할 수 있는가?
2. **RQ2 Conflict Localization** — 어떤 source/claim/rule이 truth와 충돌하거나 부분 지지하는지 찾을 수 있는가?
3. **RQ3 Rashomon Truth Resolution** — conflict provenance와 source reliability를 이용해 실제 truth를 더 정확히 복원할 수 있는가?

---

## Reproduce

```bash
pip install -e .
python scripts/evaluate_folio_fragment.py
python scripts/evaluate_logicnli.py
python scripts/evaluate_truth_discovery_books.py
```

GitHub Actions에서도 동일 benchmark를 실행하고 result JSON을 artifact로 저장한다.

---

## Current Limitations

- FOLIO 전체 문법을 지원하지 않음.
- LogicNLI는 structured logic representation으로 평가함.
- DAFNA Books는 real conflicting-source + gold truth를 제공하지만 rich ontology rule은 제공하지 않음.
- 현재 reliability baseline은 reproducible local baseline이며 공식 TruthFinder/CATD 재현 구현이 아님.
- strong venue 수준의 비교를 위해 공식 DAFNA truth-discovery algorithms와 Constrained Truth Discovery의 동일 조건 baseline이 추가로 필요함.
- entity normalization과 truth-score threshold는 향후 dev/test 분리로 검증해야 함.
